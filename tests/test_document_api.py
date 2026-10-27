"""File-only document ingestion and editable citation metadata contracts."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.authentication import get_current_user
from app.api.endpoints.documents import router
from app.db.database import get_db
from app.schemas.document import DocumentUpdate
from app.services import document_service


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router, prefix='/api/documents')
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=uuid4())
    app.dependency_overrides[get_db] = lambda: MagicMock()
    return TestClient(app)


def test_url_without_a_local_file_is_rejected(client):
    with patch.object(document_service, 'process_and_upload_document') as process:
        response = client.post('/api/documents/upload', data={'url': 'https://example.org/page'})
    assert response.status_code == 422
    process.assert_not_called()


def test_openapi_requires_file_and_exposes_only_one_optional_url(client):
    schema = client.get('/openapi.json').json()
    body = schema['components']['schemas']['Body_upload_document_api_documents_upload_post']
    assert body['required'] == ['file']
    assert set(body['properties']) == {'file', 'reference_url', 'category_ids'}
    update = schema['components']['schemas']['DocumentUpdate']
    assert 'reference_url' in update['properties']
    assert 'link' not in schema['components']['schemas']['DocumentResponse']['properties']


def test_file_and_optional_source_link_are_forwarded_without_web_ingestion(client):
    result = dict(id=str(uuid4()), filename='guida.txt', content_type='text/plain',
                  reference_url='https://example.org/guida', categories=[])
    with patch.object(document_service, 'process_and_upload_document', return_value=(result, 0)) as process:
        response = client.post('/api/documents/upload', files={'file': ('guida.txt', b'Regole', 'text/plain')},
                               data={'reference_url': result['reference_url']})
    assert response.status_code == 200
    assert response.json()['reference_url'] == result['reference_url']
    assert 'url' not in process.call_args.kwargs
    assert process.call_args.kwargs['file'].filename == 'guida.txt'


@pytest.mark.parametrize('reference', ['https://example.org/added', 'https://example.org/changed', None, '  '])
def test_update_adds_changes_or_removes_source_and_syncs_chunks(reference):
    document = SimpleNamespace(id=uuid4(), reference_url='https://example.org/old',
                               categories=[SimpleNamespace(name='Tasse')], apply_audit_fields=MagicMock())
    db = MagicMock()
    payload = DocumentUpdate(reference_url=reference)
    with patch.object(document_service, 'get_document', return_value=document), \
         patch.object(document_service, 'update_document_chunks_metadata') as metadata:
        updated = document_service.update_document(db, document.id, payload, uuid4())
    assert updated.reference_url == (reference.strip() if reference and reference.strip() else None)
    assert [category.name for category in updated.categories] == ['Tasse']
    metadata.assert_called_once_with(db, document.id, {'categories': ['Tasse'], 'reference_url': updated.reference_url})
    db.commit.assert_called_once()


def test_category_only_update_preserves_source_link():
    document = SimpleNamespace(id=uuid4(), reference_url='https://example.org/keep',
                               categories=[], apply_audit_fields=MagicMock())
    with patch.object(document_service, 'get_document', return_value=document), \
         patch.object(document_service, 'update_document_chunks_metadata'):
        updated = document_service.update_document(MagicMock(), document.id, DocumentUpdate(category_ids=[]), uuid4())
    assert updated.reference_url == 'https://example.org/keep'


def test_update_rejects_invalid_source_link(client):
    with pytest.raises(ValidationError):
        DocumentUpdate(reference_url='javascript:alert(1)')
    with patch.object(document_service, 'update_document') as update:
        response = client.put(f'/api/documents/{uuid4()}', json={'reference_url': 'ftp://example.org/file'})
    assert response.status_code == 422
    update.assert_not_called()


def test_update_endpoint_supports_explicit_link_removal(client):
    document_id = uuid4()
    result = dict(id=str(document_id), filename='guida.txt', content_type='text/plain', reference_url=None, categories=[])
    with patch.object(document_service, 'update_document', return_value=result) as update:
        response = client.put(f'/api/documents/{document_id}', json={'reference_url': None})
    assert response.status_code == 200
    payload = update.call_args.args[2]
    assert payload.reference_url is None
    assert payload.model_fields_set == {'reference_url'}


@pytest.mark.parametrize('legacy', [False, True])
def test_worker_extracts_only_the_file_including_previously_queued_file_tasks(legacy):
    from app.tasks.document_tasks import process_document_task
    from langchain_core.documents import Document
    source = SimpleNamespace(filename='guida.txt', reference_url='https://example.org/citation')
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = source
    db.query.return_value.filter.return_value.all.return_value = [SimpleNamespace(name='Tasse')]
    with patch('langchain_unstructured.UnstructuredLoader') as loader, \
         patch('app.tasks.document_tasks.os.path.exists', return_value=True), \
         patch('app.tasks.document_tasks.os.remove'), \
         patch('app.tasks.document_tasks.session_scope') as session, \
         patch('app.ai.rag.index_langchain_documents', return_value=1) as index, \
         patch('app.ai.md_formatter.normalize_to_structured_markdown', return_value=SimpleNamespace(needs_review=False, markdown='Regole', review_notes=None)):
        session.return_value.__enter__.return_value = db
        loader.return_value.load.return_value = [Document(page_content='Regole')]
        args = ('doc-id', '/tmp/guida.txt', 'https://example.org/old-origin', ['category-id']) if legacy else ('doc-id', '/tmp/guida.txt', ['category-id'])
        process_document_task.run(*args)
    loader.assert_called_once_with('/tmp/guida.txt')
    assert index.call_args.kwargs['category_names'] == ['Tasse']
    assert index.call_args.kwargs['reference_url'] == source.reference_url


def test_previously_queued_web_task_never_fetches_a_page():
    from app.tasks.document_tasks import process_document_task
    with patch('langchain_unstructured.UnstructuredLoader') as loader, \
         patch('app.ai.rag.index_langchain_documents') as index:
        process_document_task.run('doc-id', None, 'https://example.org/old-page', [])
    loader.assert_not_called()
    index.assert_not_called()
