"""Exercise upgrade/downgrade against disposable PostgreSQL databases."""
import json
import unittest
from unittest.mock import patch
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from app.core.config import settings


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.database = 'unical_migration_test_' + uuid4().hex
        self.admin = create_engine(settings.DATABASE_URL, isolation_level='AUTOCOMMIT')
        with self.admin.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{self.database}"'))
        self.url = make_url(settings.DATABASE_URL).set(database=self.database).render_as_string(hide_password=False)
        self.engine = create_engine(self.url)
        self.config = Config('alembic.ini')

    def tearDown(self):
        self.engine.dispose()
        with self.admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{self.database}" WITH (FORCE)'))
        self.admin.dispose()

    def migrate(self, direction, revision):
        with patch.object(settings, 'DATABASE_URL', self.url):
            getattr(command, direction)(self.config, revision)

    def test_legacy_links_and_chunks_survive_upgrade_and_downgrade(self):
        self.migrate('upgrade', 'a3c9d2f4b7e1')
        ids = [uuid4(), uuid4()]
        with self.engine.begin() as connection:
            connection.execute(text('CREATE TABLE langchain_pg_embedding (id uuid PRIMARY KEY, cmetadata jsonb)'))
            for doc_id, link in zip(ids, ['https://example.org/legacy.pdf', None]):
                connection.execute(text("INSERT INTO documents (id, filename, content_type, link, created_by, last_updated_by) VALUES (:id, 'legacy.pdf', 'application/pdf', :link, 'test', 'test')"), dict(id=doc_id, link=link))
                connection.execute(text('INSERT INTO langchain_pg_embedding VALUES (:id, CAST(:metadata AS jsonb))'), dict(id=uuid4(), metadata=json.dumps({'document_id': str(doc_id), 'categories': ['Iscrizioni']})))
        self.migrate('upgrade', 'head')
        with self.engine.connect() as connection:
            rows = connection.execute(text('SELECT id, reference_url FROM documents')).mappings().all()
            self.assertEqual(len(rows), 2)
            self.assertEqual({row['reference_url'] for row in rows}, {'https://example.org/legacy.pdf', None})
            self.assertNotIn('link', [column['name'] for column in inspect(self.engine).get_columns('documents')])
            chunks = connection.execute(text('SELECT cmetadata FROM langchain_pg_embedding')).scalars().all()
            self.assertEqual({item['reference_url'] for item in chunks}, {'https://example.org/legacy.pdf', None})
            self.assertTrue(all(item['source_name'] == 'legacy.pdf' for item in chunks))
        self.migrate('downgrade', 'a3c9d2f4b7e1')
        self.assertNotIn('reference_url', [column['name'] for column in inspect(self.engine).get_columns('documents')])
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text('SELECT count(*) FROM documents')).scalar(), 2)
            chunks = connection.execute(text('SELECT cmetadata FROM langchain_pg_embedding')).scalars().all()
            self.assertTrue(all('reference_url' not in item and item['categories'] == ['Iscrizioni'] for item in chunks))
        self.migrate('upgrade', 'head')

    def test_explicit_citation_wins_and_chunk_metadata_tracks_updates(self):
        self.migrate('upgrade', 'b7e2f6c8d901')
        doc_id = uuid4()
        with self.engine.begin() as connection:
            connection.execute(text('CREATE TABLE langchain_pg_embedding (id uuid PRIMARY KEY, cmetadata jsonb)'))
            connection.execute(text("INSERT INTO documents (id, filename, content_type, link, reference_url, created_by, last_updated_by) VALUES (:id, 'file.pdf', 'application/pdf', 'https://example.org/origin', 'https://example.org/citation', 'test', 'test')"), {'id':doc_id})
            connection.execute(text('INSERT INTO langchain_pg_embedding VALUES (:id, CAST(:metadata AS jsonb))'), {'id':uuid4(), 'metadata':json.dumps({'document_id':str(doc_id), 'category':'old', 'page':3})})
        self.migrate('upgrade', 'head')
        from sqlalchemy.orm import Session
        from app.services.document_service import update_document
        from app.schemas.document import DocumentUpdate
        from app.models.document import Document
        with Session(self.engine) as db:
            self.assertEqual(db.get(Document, doc_id).reference_url, 'https://example.org/citation')
            update_document(db, doc_id, DocumentUpdate(reference_url='https://example.org/new'), uuid4())
            metadata = db.execute(text('SELECT cmetadata FROM langchain_pg_embedding')).scalar()
            self.assertEqual(metadata['reference_url'], 'https://example.org/new')
            self.assertEqual(metadata['page'], 3)
            self.assertNotIn('category', metadata)
            update_document(db, doc_id, DocumentUpdate(reference_url=None), uuid4())
            self.assertIsNone(db.get(Document, doc_id).reference_url)
            self.assertIsNone(db.execute(text('SELECT cmetadata FROM langchain_pg_embedding')).scalar()['reference_url'])
        self.migrate('downgrade', 'b7e2f6c8d901')
        self.assertIn('link', [column['name'] for column in inspect(self.engine).get_columns('documents')])

    def test_fresh_database_without_vector_tables(self):
        self.migrate('upgrade', 'head')
        self.assertIn('reference_url', [column['name'] for column in inspect(self.engine).get_columns('documents')])
        self.migrate('downgrade', '-1')


if __name__ == '__main__':
    unittest.main()
