import os
from uuid import UUID
from app.core.celery_app import celery_app
from app.db.database import session_scope
from app.models.document import Document
from app.models.category import Category

@celery_app.task(name="app.tasks.document_tasks.process_document_task")
def process_document_task(document_id: UUID, file_path: str | None, url: str | None, category_id: str | None):

    from langchain_unstructured import UnstructuredLoader
    from langchain_community.document_loaders import WebBaseLoader
    from app.ai.rag import index_langchain_documents

    try:
        docs = []
        if file_path and os.path.exists(file_path):
            print(f"[WORKER] Estrazione dati da file: {file_path}")
            loader = UnstructuredLoader(file_path)
            docs = loader.load()
            os.remove(file_path)
        elif url:
            print(f"[WORKER] Estrazione dati da URL: {url}")
            loader = WebBaseLoader(url)
            docs = loader.load()

        category_name = "Generale"
        with session_scope() as db:
            if category_id:
                db_category = db.query(Category).filter(Category.id == category_id).first()
                if db_category:
                    category_name = db_category.name

        chunk_count = index_langchain_documents(docs, category_name=category_name)
        preview_text = docs[0].page_content[:500] if docs else "Nessun testo estratto."

        with session_scope() as db:
            db_doc = db.query(Document).filter(Document.id == document_id).first()
            if db_doc:
                db_doc.extracted_text = preview_text
                db.commit()

        print(f"[WORKER] Documento {document_id} processato! Chunks: {chunk_count}")

    except Exception as e:
        print(f"[WORKER] Errore elaborazione documento {document_id}: {e}")