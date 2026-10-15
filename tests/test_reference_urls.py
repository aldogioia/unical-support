import json
import os
from io import BytesIO
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.core.urls import normalize_reference_url
from app.schemas.document import DocumentResponse


class ReferenceUrlTests(unittest.TestCase):
    def test_local_file_upload_persists_only_the_optional_source_link(self):
        from fastapi import UploadFile
        from starlette.datastructures import Headers
        from app.services.document_service import process_and_upload_document
        for reference in ['https://example.org/public.pdf', None]:
            with self.subTest(reference=reference):
                db = MagicMock()
                db.add.side_effect = lambda doc: setattr(doc, 'id', uuid4())
                file = UploadFile(filename='regole.txt', file=BytesIO(b'Regole di iscrizione'), headers=Headers({'content-type': 'text/plain'}))
                with patch('app.services.document_service.process_document_task.delay') as task:
                    document, _ = process_and_upload_document(db, file, [], uuid4(), reference)
                    path = task.call_args.args[1]
                try:
                    self.assertEqual(document.reference_url, reference)
                    self.assertFalse(hasattr(document, 'link'))
                    self.assertEqual(task.call_args.args[2], [])
                    self.assertTrue(os.path.exists(path))
                finally:
                    os.remove(path)

    def test_bad_reference_rejected_before_saving_or_queueing(self):
        from fastapi import UploadFile
        from starlette.datastructures import Headers
        from app.services.document_service import process_and_upload_document
        db = MagicMock()
        file = UploadFile(filename='regole.txt', file=BytesIO(b'Regole'), headers=Headers({'content-type': 'text/plain'}))
        with patch('app.services.document_service.process_document_task.delay') as task:
            with self.assertRaises(ValueError):
                process_and_upload_document(db, file, [], uuid4(), 'ftp://example.org/regole')
        db.add.assert_not_called()
        task.assert_not_called()

    def test_optional_and_http_urls(self):
        self.assertIsNone(normalize_reference_url(None))
        self.assertIsNone(normalize_reference_url('  '))
        self.assertEqual(normalize_reference_url(' https://example.org/form.pdf '), 'https://example.org/form.pdf')
        self.assertEqual(normalize_reference_url('http://example.org/form.pdf'), 'http://example.org/form.pdf')

    def test_reject_unsafe_or_malformed_urls(self):
        for value in ['javascript:alert(1)', 'ftp://example.org/file', 'not a URL', 'https://', 'https://user:pass@example.org/file', 'https://example.org/' + 'x' * 2048]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_reference_url(value)

    def test_legacy_response_without_reference_url(self):
        doc = DocumentResponse(id=uuid4(), filename='regolamento.pdf', content_type='application/pdf')
        self.assertIsNone(doc.reference_url)

    def test_new_chunks_carry_citation_metadata(self):
        from langchain_core.documents import Document
        from app.ai.rag import index_langchain_documents
        store = MagicMock()
        with patch('app.ai.rag.get_vector_store', return_value=store), patch('app.ai.rag.time.sleep'):
            count = index_langchain_documents(
                [Document(page_content='Regole per le iscrizioni')], document_id='doc-123',
                reference_url='https://example.org/regole', source_name='Regolamento',
            )
        self.assertEqual(count, 1)
        metadata = store.add_documents.call_args.args[0][0].metadata
        self.assertEqual(metadata['reference_url'], 'https://example.org/regole')
        self.assertEqual(metadata['source_name'], 'Regolamento')

    def test_legacy_chunks_get_source_from_database(self):
        from langchain_core.documents import Document
        from app.ai.rag import format_source_context
        doc_id = uuid4()
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [SimpleNamespace(
            id=doc_id, filename='Regolamento.pdf', reference_url='https://example.org/legacy',
        )]
        with patch('app.db.database.session_scope') as session:
            session.return_value.__enter__.return_value = db
            result = json.loads(format_source_context([
                Document(page_content='Scadenza: 30 ottobre', metadata={'document_id': str(doc_id)}),
            ]))
        self.assertEqual(result['reference_url'], 'https://example.org/legacy')
        self.assertEqual(result['source_name'], 'Regolamento.pdf')
        self.assertIn('30 ottobre', result['content'])

    def test_removing_database_source_link_overrides_old_chunk_metadata(self):
        from langchain_core.documents import Document
        from app.ai.rag import format_source_context
        doc_id = uuid4()
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [SimpleNamespace(id=doc_id, filename='Regole.pdf', reference_url=None)]
        with patch('app.db.database.session_scope') as session:
            session.return_value.__enter__.return_value = db
            result = json.loads(format_source_context([Document(page_content='Regole', metadata={'document_id':str(doc_id), 'reference_url':'https://old.example.org/'})]))
        self.assertIsNone(result['reference_url'])

    def test_missing_reference_stays_null(self):
        from langchain_core.documents import Document
        from app.ai.rag import format_source_context
        result = json.loads(format_source_context([Document(page_content='Testo senza fonte pubblica')]))
        self.assertIsNone(result['reference_url'])


if __name__ == '__main__':
    unittest.main()
