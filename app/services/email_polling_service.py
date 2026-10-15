"""Shared coordination for manual and scheduled Gmail polling."""
import json
from uuid import uuid4

from redis import Redis
from app.core.config import settings

POLL_LOCK_SECONDS = 660  # Longer than the Celery task's hard time limit (600s).
POLL_STATUS_SECONDS = 86400


class PollCoordinator:
    def __init__(self, client=None, key_prefix="unical:gmail-poll"):
        self.redis = client or Redis.from_url(settings.REDIS_URL, decode_responses=True)
        self.lock_key = f"{key_prefix}:lock"
        self.status_prefix = f"{key_prefix}:job:"

    def reserve(self, job_id: str) -> bool:
        if not self.redis.set(self.lock_key, job_id, nx=True, ex=POLL_LOCK_SECONDS):
            return False
        self.update(job_id, "queued", "Controllo delle email in coda.")
        return True

    def current(self) -> dict | None:
        job_id = self.redis.get(self.lock_key)
        return self.status(job_id) if job_id else None

    def owns_lock(self, job_id: str) -> bool:
        return self.redis.get(self.lock_key) == job_id

    def begin(self, job_id: str) -> bool:
        # Renew at actual start; reject duplicate deliveries of the same task.
        result = dict(job_id=job_id, status='running', message='Controllo delle nuove email in corso…', fetched_count=0)
        return bool(self.redis.eval(
            "if redis.call('get', KEYS[1]) ~= ARGV[1] then return 0 end "
            "local raw = redis.call('get', KEYS[2]); "
            "if not raw or cjson.decode(raw).status ~= 'queued' then return 0 end "
            "redis.call('expire', KEYS[1], ARGV[2]); "
            "redis.call('set', KEYS[2], ARGV[3], 'EX', ARGV[4]); return 1",
            2, self.lock_key, self.status_prefix + job_id, job_id,
            POLL_LOCK_SECONDS, json.dumps(result), POLL_STATUS_SECONDS,
        ))

    def update(self, job_id: str, status: str, message: str, fetched_count: int = 0) -> dict:
        result = dict(job_id=job_id, status=status, message=message, fetched_count=fetched_count)
        self.redis.set(self.status_prefix + job_id, json.dumps(result), ex=POLL_STATUS_SECONDS)
        return result

    def status(self, job_id: str) -> dict | None:
        raw = self.redis.get(self.status_prefix + job_id)
        if not raw:
            return None
        result = json.loads(raw)
        if result['status'] in ('queued', 'running') and not self.owns_lock(job_id):
            # Re-read: completion may have released the lock between the two GETs.
            result = json.loads(self.redis.get(self.status_prefix + job_id) or raw)
            if result['status'] in ('queued', 'running'):
                return dict(result, status='expired', message='Il controllo è scaduto. Puoi riprovare.')
        return result

    def release(self, job_id: str):
        # An expired job must never delete the reservation of a newer job.
        self.redis.eval(
            "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end",
            1, self.lock_key, job_id,
        )


def enqueue_email_poll() -> dict:
    from app.core.celery_app import celery_app

    coordinator = PollCoordinator()
    job_id = str(uuid4())
    for _ in range(2):
        if coordinator.reserve(job_id):
            try:
                celery_app.send_task(
                    'app.tasks.polling_tasks.poll_gmail', args=[job_id],
                    task_id=job_id, queue='polling_queue',
                )
            except Exception:
                coordinator.update(job_id, 'failed', 'Impossibile accodare il controllo delle email.')
                coordinator.release(job_id)
                raise
            return coordinator.status(job_id)
        current = coordinator.current()
        if current:
            return dict(current, already_running=True)
    raise RuntimeError('Impossibile prenotare il controllo delle email.')
