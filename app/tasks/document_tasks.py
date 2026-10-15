import os
from uuid import UUID
from app.core.celery_app import celery_app
from app.db.database import session_scope
from app.models.document import Document
from app.models.category import Category

@celery_app.task(name="app.tasks.document_tasks.process_document_task")
def process_document_task(document_id: UUID | str, file_path: str, category_ids: list[str] | str | None = None, *legacy_args):

    from langchain_unstructured import UnstructuredLoader
    from app.ai.rag import index_langchain_documents

    try:
        docs = []
        if file_path and os.path.exists(file_path):
            print(f"[WORKER] Estrazione dati da file: {file_path}")
            loader = UnstructuredLoader(file_path)
            docs = loader.load()
            os.remove(file_path)
        else:
            raise ValueError("File locale non disponibile per l'elaborazione.")

        # Old file tasks had a separate third URL argument. Ignore it; never fetch it.
        if legacy_args:
            category_ids = legacy_args[0]

        # Retro-compatibilità con task accodati prima della migrazione (singolo category_id)
        if isinstance(category_ids, str):
            category_ids = [category_ids]

        category_names: list[str] = []
        with session_scope() as db:
            source = db.query(Document).filter(Document.id == document_id).first()
            if not source:
                return
            reference_url = source.reference_url
            source_name = source.filename
            if category_ids:
                db_categories = db.query(Category).filter(Category.id.in_(category_ids)).all()
                category_names = [c.name for c in db_categories]

        chunk_count = index_langchain_documents(
            docs, category_names=category_names, document_id=str(document_id),
            reference_url=reference_url, source_name=source_name,
        )
        preview_text = docs[0].page_content[:500] if docs else "Nessun testo estratto."

        with session_scope() as db:
            db_doc = db.query(Document).filter(Document.id == document_id).first()
            if db_doc:
                db_doc.extracted_text = preview_text
                db.commit()

        print(f"[WORKER] Documento {document_id} processato! Chunks: {chunk_count}")

    except Exception as e:
        print(f"[WORKER] Errore elaborazione documento {document_id}: {e}")
