"""Indicizzazione forzata dei documenti fermati dalla verifica di fedeltà (needs_review)."""
import inspect
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api.authentication import get_current_user
from app.api.endpoints.documents import router
from app.db.database import get_db
from app.models.enumerators.enumerators import UserRole
from app.services import document_service
from app.tasks import document_tasks

MARKDOWN = '**Seconda rata.** La seconda rata scade il 31 marzo 2027. (Fonte: Regolamento Tasse.)'


def reviewed(**kwargs):
    values = dict(id=uuid4(), filename='Regolamento Tasse.pdf', content_type='application/pdf',
                  processing_status='needs_review', reference_url='https://www.unical.it/tasse.pdf',
                  review_notes='Parte 1/1: dati persi: 14', extracted_text=document_service.REVIEW_PREFIX + MARKDOWN,
                  categories=[SimpleNamespace(name='Tasse e contributi')], apply_audit_fields=MagicMock())
    values.update(kwargs)
    return SimpleNamespace(**values)


def locked_db(document):
    db = MagicMock()
    db.query.return_value.filter.return_value.populate_existing.return_value.with_for_update.return_value.first.return_value = document
    return db


def make_client(role):
    app = FastAPI()
    app.include_router(router, prefix='/api/documents')
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=uuid4(), role=role)
    app.dependency_overrides[get_db] = lambda: MagicMock()
    return TestClient(app)


# ------------------------------------------------------------------ contratto con il worker esistente

def test_prefix_matches_the_one_written_by_the_document_worker():
    assert document_service.REVIEW_PREFIX.strip() in inspect.getsource(document_tasks.process_document_task)


def test_reviewed_markdown_strips_the_warning_and_rejects_empty_or_unmarked_text():
    assert document_service.reviewed_markdown(document_service.REVIEW_PREFIX + MARKDOWN) == MARKDOWN
    assert document_service.reviewed_markdown(document_service.REVIEW_PREFIX + 'Nessun testo generato.') == ''
    assert document_service.reviewed_markdown(MARKDOWN) == ''
    assert document_service.reviewed_markdown(None) == ''


# ------------------------------------------------------------------ endpoint

def test_only_admins_can_force_indexing():
    with patch.object(document_service, 'force_index_document') as force:
        response = make_client(UserRole.user).post(f'/api/documents/{uuid4()}/force-index')
    assert response.status_code == 403
    force.assert_not_called()


def test_admin_request_is_forwarded_with_the_admin_id():
    document_id = uuid4()
    result = dict(id=str(document_id), filename='a.pdf', content_type='application/pdf', categories=[],
                  processing_status='pending', review_notes='Parte 1/1: dati persi: 14')
    with patch.object(document_service, 'force_index_document', return_value=result) as force:
        response = make_client(UserRole.admin).post(f'/api/documents/{document_id}/force-index')
    assert response.status_code == 200
    assert response.json()['processing_status'] == 'pending'
    assert force.call_args.args[1] == document_id


# ------------------------------------------------------------------ servizio

def test_force_index_marks_pending_and_queues_the_worker():
    document = reviewed()
    db = locked_db(document)
    with patch.object(document_service, 'force_index_document_task') as task:
        result = document_service.force_index_document(db, document.id, uuid4())
    assert result.processing_status == 'pending'
    task.delay.assert_called_once_with(str(document.id))
    document.apply_audit_fields.assert_called_once()


@pytest.mark.parametrize('document, status', [
    (None, 404),
    (reviewed(processing_status='indexed'), 409),
    (reviewed(processing_status='pending'), 409),
    (reviewed(extracted_text=document_service.REVIEW_PREFIX + 'Nessun testo generato.'), 422),
])
def test_force_index_refuses_missing_already_handled_or_empty_documents(document, status):
    with patch.object(document_service, 'force_index_document_task') as task, pytest.raises(HTTPException) as error:
        document_service.force_index_document(locked_db(document), uuid4(), uuid4())
    assert error.value.status_code == status
    task.delay.assert_not_called()


def test_queue_failure_restores_the_review_state():
    document = reviewed()
    with patch.object(document_service, 'force_index_document_task') as task, pytest.raises(HTTPException) as error:
        task.delay.side_effect = RuntimeError('redis offline')
        document_service.force_index_document(locked_db(document), document.id, uuid4())
    assert error.value.status_code == 503
    assert document.processing_status == 'needs_review'


# ------------------------------------------------------------------ worker

def run_worker(document, index_side_effect=None):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = document
    with patch('app.tasks.document_tasks.session_scope') as session, \
         patch('app.services.document_service.delete_document_chunks') as delete_chunks, \
         patch('app.ai.rag.index_langchain_documents', return_value=3, side_effect=index_side_effect) as index:
        session.return_value.__enter__.return_value = db
        document_tasks.force_index_document_task.run(str(document.id))
    return index, delete_chunks


def test_worker_indexes_the_saved_markdown_with_categories_and_link():
    document = reviewed(processing_status='pending')
    index, delete_chunks = run_worker(document)
    delete_chunks.assert_called_once()
    docs = index.call_args.args[0]
    assert [d.page_content for d in docs] == [MARKDOWN]
    assert index.call_args.kwargs['category_names'] == ['Tasse e contributi']
    assert index.call_args.kwargs['reference_url'] == document.reference_url
    assert index.call_args.kwargs['source_name'] == 'Regolamento Tasse.pdf'
    assert document.processing_status == 'indexed'
    assert document.extracted_text == MARKDOWN
    assert document.review_notes.startswith(document_service.FORCED_REVIEW_NOTE)
    assert document.review_notes.endswith('Parte 1/1: dati persi: 14')


def test_worker_ignores_documents_no_longer_pending():
    document = reviewed(processing_status='needs_review')
    index, delete_chunks = run_worker(document)
    index.assert_not_called()
    delete_chunks.assert_not_called()


def test_worker_failure_puts_the_document_back_in_review():
    document = reviewed(processing_status='pending')
    run_worker(document, index_side_effect=RuntimeError('embeddings offline'))
    assert document.processing_status == 'needs_review'
    assert document.review_notes == 'Parte 1/1: dati persi: 14'


# ------------------------------------------------------------------ testo corretto a mano dall'admin

CORRECTED = '**Seconda rata.** La seconda rata scade il 30 aprile 2027. (Fonte: Regolamento Tasse.)'


def forced_result(document_id):
    return dict(id=str(document_id), filename='a.pdf', content_type='application/pdf', categories=[],
                processing_status='pending', review_notes=None)


def test_endpoint_without_body_keeps_the_generated_text():
    document_id = uuid4()
    with patch.object(document_service, 'force_index_document', return_value=forced_result(document_id)) as force:
        response = make_client(UserRole.admin).post(f'/api/documents/{document_id}/force-index')
    assert response.status_code == 200
    assert force.call_args.kwargs['markdown'] is None


def test_endpoint_forwards_the_corrected_text():
    document_id = uuid4()
    with patch.object(document_service, 'force_index_document', return_value=forced_result(document_id)) as force:
        response = make_client(UserRole.admin).post(
            f'/api/documents/{document_id}/force-index', json={'markdown': CORRECTED})
    assert response.status_code == 200
    assert force.call_args.kwargs['markdown'] == CORRECTED


def test_users_cannot_send_a_corrected_text():
    with patch.object(document_service, 'force_index_document') as force:
        response = make_client(UserRole.user).post(
            f'/api/documents/{uuid4()}/force-index', json={'markdown': CORRECTED})
    assert response.status_code == 403
    force.assert_not_called()


def test_corrected_text_replaces_the_generated_one_before_queueing():
    document = reviewed()
    with patch.object(document_service, 'force_index_document_task') as task:
        document_service.force_index_document(locked_db(document), document.id, uuid4(),
                                              markdown='  ' + CORRECTED.replace(' ', ' ', 1) + '\r\n')
    assert document.extracted_text == document_service.REVIEW_PREFIX + CORRECTED
    assert document_service.reviewed_markdown(document.extracted_text) == CORRECTED
    assert document.processing_status == 'pending'
    task.delay.assert_called_once_with(str(document.id))


def test_blank_corrected_text_is_refused_and_nothing_changes():
    document = reviewed()
    with patch.object(document_service, 'force_index_document_task') as task, pytest.raises(HTTPException) as error:
        document_service.force_index_document(locked_db(document), document.id, uuid4(), markdown=' \n ')
    assert error.value.status_code == 422
    assert document.extracted_text == document_service.REVIEW_PREFIX + MARKDOWN
    assert document.processing_status == 'needs_review'
    task.delay.assert_not_called()


def test_worker_indexes_the_corrected_text():
    document = reviewed()
    with patch.object(document_service, 'force_index_document_task'):
        document_service.force_index_document(locked_db(document), document.id, uuid4(), markdown=CORRECTED)
    index, _ = run_worker(document)
    assert index.call_args.args[0][0].page_content == CORRECTED
    assert document.processing_status == 'indexed'
