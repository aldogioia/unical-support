from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4, UUID
import json

import pytest
from alembic import command
from alembic.config import Config
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.email import Email, EmailStatus
from app.models.category import Category
from app.schemas.email import EmailUpdateDraft
from app.services.email_service import get_email_page, update_email_draft, retry_email, retry_failed_emails
from app.services.email_processing import claim_processing


@pytest.fixture
def flow_db():
    database = 'unical_flow_test_' + uuid4().hex
    admin = create_engine(settings.DATABASE_URL, isolation_level='AUTOCOMMIT')
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{database}"'))
    url = make_url(settings.DATABASE_URL).set(database=database).render_as_string(hide_password=False)
    with patch.object(settings, 'DATABASE_URL', url):
        command.upgrade(Config('alembic.ini'), 'head')
    engine = create_engine(url)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()
    try:
        yield db, factory
    finally:
        db.close()
        engine.dispose()
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{database}" WITH (FORCE)'))
        admin.dispose()


def message(db, **kwargs):
    values = dict(gmail_id=uuid4().hex, sender='student@example.org', status=EmailStatus.DRAFT,
                  received_at=datetime.now(timezone.utc), generated_draft='Risposta originale')
    values.update(kwargs)
    row = Email(**values)
    db.add(row); db.commit()
    return row


def test_keyset_pagination_orders_arrival_and_does_not_repeat_after_new_mail(flow_db):
    db, _ = flow_db
    now = datetime.now(timezone.utc)
    for index in range(5):
        message(db, id=UUID(int=5-index), received_at=now - timedelta(days=index // 2, minutes=index % 2))
    first = get_email_page(db, limit=2)
    assert [row.id for row in first['items']] == [UUID(int=5), UUID(int=4)]
    message(db, received_at=now + timedelta(hours=1))
    second = get_email_page(db, cursor=first['next_cursor'], limit=2)
    third = get_email_page(db, cursor=second['next_cursor'], limit=2)
    assert [row.id for row in second['items'] + third['items']] == [UUID(int=3), UUID(int=2), UUID(int=1)]
    assert third['next_cursor'] is None
    assert first['counts']['DRAFT'] == 5
    assert first['counts']['FAILED'] == 0
    with pytest.raises(HTTPException) as invalid:
        get_email_page(db, cursor='invalid')
    assert invalid.value.status_code == 422


def test_search_uses_the_entire_filtered_query_and_literal_wildcards(flow_db):
    db, _ = flow_db
    category = Category(name='Tirocini'); db.add(category); db.commit()
    row = message(db, subject='Pratica 100%', categories=[category])
    message(db, status=EmailStatus.FAILED, subject='Altro')
    assert get_email_page(db, q='Tirocini')['items'][0].id == row.id
    assert get_email_page(db, q='%')['total'] == 1
    assert get_email_page(db, status=EmailStatus.FAILED)['total'] == 1


def test_manual_draft_version_prevents_concurrent_overwrite_and_ai_write(flow_db):
    db, factory = flow_db
    row = message(db, processing_token='obsolete-worker')
    result = update_email_draft(db, row.id, EmailUpdateDraft(generated_draft='Testo operatore', status='DRAFT', expected_revision=0), uuid4())
    assert result.draft_revision == 1 and result.manually_edited
    assert result.processing_token is None
    with pytest.raises(HTTPException) as stale:
        update_email_draft(db, row.id, EmailUpdateDraft(generated_draft='Versione vecchia', status='DRAFT', expected_revision=0), uuid4())
    assert stale.value.status_code == 409
    db.rollback()
    from app.ai.tools import _save_draft_response
    @contextmanager
    def scope():
        with factory.begin() as session: yield session
    with patch('app.ai.tools.session_scope', scope):
        assert 'nessuna modifica' in _save_draft_response(row.id, 'Sovrascrittura AI', 'it', token='obsolete-worker')
    db.expire_all()
    assert db.get(Email, row.id).generated_draft == 'Testo operatore'


def test_an_already_loaded_stale_session_cannot_overwrite_a_new_operator_revision(flow_db):
    db, factory = flow_db
    row = message(db)
    identifier = row.id
    with factory() as other:
        other.get(Email, identifier)
        update_email_draft(db, identifier, EmailUpdateDraft(generated_draft='Prima revisione', status='DRAFT', expected_revision=0), uuid4())
        with pytest.raises(HTTPException) as stale:
            update_email_draft(other, identifier, EmailUpdateDraft(generated_draft='Sovrascrittura', status='DRAFT', expected_revision=0), uuid4())
        assert stale.value.status_code == 409
    db.expire_all()
    assert db.get(Email, identifier).generated_draft == 'Prima revisione'


def test_duplicate_worker_claims_have_one_winner_and_old_generation_is_rejected(flow_db):
    db, factory = flow_db
    row = message(db, status=EmailStatus.TO_RESPOND, processing_generation=2)
    identifier = row.id
    def claim(_):
        with factory.begin() as session:
            email = claim_processing(session, identifier, EmailStatus.TO_RESPOND, 2)
            return email.processing_token if email else None
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(token is not None for token in pool.map(claim, range(4))) == 1
    with factory.begin() as session:
        assert claim_processing(session, identifier, EmailStatus.TO_RESPOND, 1) is None


def test_retry_stages_are_fenced_idempotent_and_preserve_reviewed_drafts(flow_db):
    db, _ = flow_db
    failed = message(db, status=EmailStatus.FAILED, failure_stage='classify')
    with patch('app.services.email_processing.enqueue_processing') as publish:
        queued = retry_email(db, failed.id, 0)
        publish.assert_called_once_with(failed.id, 'classify', 1)
        assert queued.status == EmailStatus.TO_CLASSIFY and queued.generated_draft == 'Risposta originale'
        with pytest.raises(HTTPException) as duplicate:
            retry_email(db, failed.id)
        assert duplicate.value.status_code == 409
    db.rollback()
    manual = message(db, status=EmailStatus.FAILED, manually_edited=True, failure_stage='send')
    with pytest.raises(HTTPException) as protected:
        retry_email(db, manual.id)
    assert protected.value.status_code == 409
    db.rollback()
    assert db.get(Email, manual.id).generated_draft == 'Risposta originale'


def test_queue_failure_keeps_failed_email_and_existing_answer(flow_db):
    db, _ = flow_db
    row = message(db, status=EmailStatus.FAILED)
    with patch('app.services.email_processing.enqueue_processing', side_effect=RuntimeError('offline')):
        with pytest.raises(HTTPException) as error:
            retry_email(db, row.id)
    assert error.value.status_code == 503
    db.expire_all()
    assert db.get(Email, row.id).status == EmailStatus.FAILED
    assert db.get(Email, row.id).generated_draft == 'Risposta originale'


def test_bulk_retry_skips_operator_drafts_and_the_open_email(flow_db):
    db, _ = flow_db
    eligible = message(db, status=EmailStatus.FAILED)
    opened = message(db, status=EmailStatus.FAILED)
    message(db, status=EmailStatus.FAILED, manually_edited=True)
    with patch('app.services.email_processing.enqueue_processing') as publish:
        result = retry_failed_emails(db, [opened.id])
    assert result['queued_count'] == 1
    assert publish.call_args.args[0] == eligible.id
    assert db.get(Email, opened.id).status == EmailStatus.FAILED


def test_delivery_is_serialized_and_a_second_approval_does_not_send_again(flow_db):
    db, _ = flow_db
    row = message(db)
    with patch('app.listener.client_factory.get_email_client') as provider:
        update_email_draft(db, row.id, EmailUpdateDraft(generated_draft='Risposta revisionata', status='SENT', expected_revision=0), uuid4())
        with pytest.raises(HTTPException):
            update_email_draft(db, row.id, EmailUpdateDraft(generated_draft='Duplicato', status='SENT', expected_revision=0), uuid4())
        provider.return_value.__enter__.return_value.send_reply.assert_called_once()


def test_retry_runs_actual_scoped_classifier_and_responder_without_external_services(flow_db):
    db, factory = flow_db
    from app.tasks.email_tasks import classify_email_task, respond_email_task
    category = Category(name='Generale'); db.add(category); db.commit()
    row = message(db, status=EmailStatus.FAILED, failure_stage='classify')
    identifier = row.id
    with patch('app.services.email_processing.enqueue_processing'):
        retry_email(db, identifier)
    @contextmanager
    def scope():
        with factory.begin() as session: yield session
    context = json.dumps(dict(source_name='Guida di collaudo', reference_url='https://example.org/test', relevance_score=0.9, content='Codice TEST-42'))
    def make_agent(llm, tools):
        operations = {operation.name: operation for operation in tools}
        def invoke(*args, **kwargs):
            if 'assign_categories_and_route' in operations:
                operations['assign_categories_and_route'].invoke(dict(email_id=str(identifier), category_names=['Generale']))
            else:
                operations['search_knowledge_base'].invoke(dict(query='Test'))
                operations['save_draft_response'].invoke(dict(email_id=str(identifier), draft_text='Hello, the code is TEST-42. Guida di collaudo: https://example.org/test', response_language='en'))
            return {'messages': [SimpleNamespace(type='tool', name='search_knowledge_base', content=context)]}
        return SimpleNamespace(invoke=invoke)
    with patch('app.tasks.email_tasks.session_scope', scope), patch('app.ai.tools.session_scope', scope), \
         patch('app.ai.tools.retrieve_context', return_value=context), patch('app.ai.llm_factory.get_classifier_llm'), \
         patch('app.ai.llm_factory.get_responder_llm'), patch('langgraph.prebuilt.create_react_agent', side_effect=make_agent), \
         patch('app.ai.tools.enqueue_processing') as next_stage:
        assert classify_email_task.run(identifier, generation=1) is True
        next_stage.assert_called_once_with(identifier, 'respond', 1)
        assert respond_email_task.run(identifier, generation=1) is True
    db.expire_all()
    result = db.get(Email, identifier)
    assert result.status == EmailStatus.DRAFT and result.response_language == 'en'
    assert result.ai_confidence == 0.9 and not result.manually_edited


def test_sweeper_only_requeues_expired_processing_not_active_or_reviewed(flow_db):
    db, factory = flow_db
    from app.tasks.polling_tasks import sweep_stuck_emails
    old = datetime.now(timezone.utc) - timedelta(minutes=20)
    expired = message(db, status=EmailStatus.TO_RESPOND, processing_token='expired', processing_started_at=old)
    active = message(db, status=EmailStatus.TO_RESPOND, processing_token='active', processing_started_at=datetime.now(timezone.utc))
    manual = message(db, manually_edited=True)
    @contextmanager
    def scope():
        with factory.begin() as session: yield session
    with patch('app.tasks.polling_tasks.session_scope', scope), patch('app.services.email_processing.enqueue_processing') as publish:
        assert sweep_stuck_emails.run()['requeued_count'] == 1
    publish.assert_called_once_with(str(expired.id), 'respond', 1)
    db.expire_all()
    assert db.get(Email, active.id).processing_token == 'active'
    assert db.get(Email, manual.id).status == EmailStatus.DRAFT
