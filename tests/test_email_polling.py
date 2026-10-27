import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from redis import Redis
from app.core.config import settings
from app.services.email_polling_service import PollCoordinator, enqueue_email_poll
from app.tasks.polling_tasks import poll_gmail


class EmailPollingTests(unittest.TestCase):
    def setUp(self):
        self.redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
        self.prefix = 'test:gmail-poll:' + str(uuid4())
        self.coordinator = PollCoordinator(self.redis, self.prefix)

    def tearDown(self):
        keys = list(self.redis.scan_iter(self.prefix + '*'))
        if keys:
            self.redis.delete(*keys)
        self.redis.close()

    def test_concurrent_reservations_have_one_winner(self):
        ids = [str(uuid4()) for _ in range(12)]
        with ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(self.coordinator.reserve, ids))
        self.assertEqual(sum(results), 1)

    def test_manual_calls_share_job_and_only_enqueue_once(self):
        with patch('app.services.email_polling_service.PollCoordinator', return_value=self.coordinator), patch('app.core.celery_app.celery_app.send_task') as send:
            first = enqueue_email_poll()
            second = enqueue_email_poll()
        self.assertEqual(first['job_id'], second['job_id'])
        self.assertTrue(second['already_running'])
        self.assertEqual(send.call_count, 1)
        self.assertTrue(self.coordinator.begin(first['job_id']))
        self.assertFalse(self.coordinator.begin(first['job_id']))

    def test_automatic_poll_skips_manual_reservation(self):
        self.coordinator.reserve(str(uuid4()))
        with patch('app.services.email_polling_service.PollCoordinator', return_value=self.coordinator), patch('app.tasks.polling_tasks.get_email_client') as gmail:
            result = poll_gmail.run()
        self.assertEqual(result['status'], 'skipped')
        gmail.assert_not_called()

    def test_expired_owner_cannot_release_new_job(self):
        old, new = str(uuid4()), str(uuid4())
        self.coordinator.reserve(old)
        self.redis.delete(self.coordinator.lock_key)
        self.coordinator.reserve(new)
        self.coordinator.release(old)
        self.assertTrue(self.coordinator.owns_lock(new))
        self.assertEqual(self.coordinator.status(old)['status'], 'expired')
        self.assertFalse(self.coordinator.begin(old))

    def test_gmail_error_is_visible_and_releases_lock(self):
        job = str(uuid4())
        self.coordinator.reserve(job)
        with patch('app.services.email_polling_service.PollCoordinator', return_value=self.coordinator), patch('app.tasks.polling_tasks.get_email_client', side_effect=RuntimeError('OAuth invalid')):
            result = poll_gmail.run(job)
        self.assertEqual(result['status'], 'failed')
        self.assertIn('credenziali email', result['message'])
        self.assertFalse(self.coordinator.owns_lock(job))
        self.assertEqual(self.coordinator.status(job)['status'], 'failed')

    def test_new_emails_queued_and_duplicates_skipped(self):
        job = str(uuid4())
        self.coordinator.reserve(job)
        gmail = MagicMock()
        gmail.fetch_unread_emails.return_value = [
            dict(gmail_id='gmail-new', sender='student@example.org', subject='Help', body='Question'),
            dict(gmail_id='gmail-old', sender='student@example.org', subject='Help', body='Question'),
        ]
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [None, SimpleNamespace(id=uuid4())]
        email_id = uuid4()
        with patch('app.services.email_polling_service.PollCoordinator', return_value=self.coordinator), patch('app.tasks.polling_tasks.get_email_client', return_value=gmail), patch('app.tasks.polling_tasks.session_scope') as session, patch('app.tasks.polling_tasks.email_service.create_email', return_value=SimpleNamespace(id=email_id, processing_generation=0)) as create, patch('app.tasks.polling_tasks.celery_app.send_task') as send:
            session.return_value.__enter__.return_value = db
            result = poll_gmail.run(job)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['fetched_count'], 1)
        self.assertEqual(create.call_count, 1)
        send.assert_called_once_with('app.tasks.email_tasks.classify_email_task', args=[str(email_id)], kwargs={'generation': 0}, queue='classify_queue')
        self.assertEqual(gmail.mark_as_read.call_count, 2)
        self.assertFalse(self.coordinator.owns_lock(job))

    def test_queue_failure_releases_reservation(self):
        with patch('app.services.email_polling_service.PollCoordinator', return_value=self.coordinator), patch('app.core.celery_app.celery_app.send_task', side_effect=RuntimeError('broker down')):
            with self.assertRaises(RuntimeError):
                enqueue_email_poll()
        self.assertIsNone(self.redis.get(self.coordinator.lock_key))


class EmailFetchApiTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from app.main import app
        self.app = app
        self.client = TestClient(app)

    def tearDown(self):
        self.app.dependency_overrides.clear()
        self.client.close()

    def authenticate(self):
        from app.api.authentication import get_current_user
        self.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=uuid4())

    def test_fetch_requires_authentication(self):
        self.assertIn(self.client.post('/api/emails/fetch-now').status_code, (401, 403))

    def test_fetch_returns_accepted_job_and_handles_broker_error(self):
        self.authenticate()
        job = dict(job_id=str(uuid4()), status='queued', message='In coda', fetched_count=0)
        with patch('app.api.endpoints.emails.enqueue_email_poll', return_value=job):
            response = self.client.post('/api/emails/fetch-now')
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()['job_id'], job['job_id'])
        with patch('app.api.endpoints.emails.enqueue_email_poll', side_effect=RuntimeError()):
            self.assertEqual(self.client.post('/api/emails/fetch-now').status_code, 503)

    def test_status_route_does_not_conflict_with_email_detail(self):
        self.authenticate()
        job = dict(job_id=str(uuid4()), status='completed', message='Completato', fetched_count=3)
        with patch('app.api.endpoints.emails.PollCoordinator') as coordinator:
            coordinator.return_value.status.return_value = job
            response = self.client.get('/api/emails/fetch-status/' + job['job_id'])
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['fetched_count'], 3)
            coordinator.return_value.status.return_value = None
            self.assertEqual(self.client.get('/api/emails/fetch-status/' + job['job_id']).status_code, 404)


if __name__ == '__main__':
    unittest.main()
