import os
from uuid import UUID
from app.core.celery_app import celery_app
from app.db.database import session_scope
from app.models.document import Document
from app.models.category import Category

@celery_app.task(name="app.tasks.document_tasks.process_document_task")
def process_document_task(document_id: UUID | str, file_path: str, category_ids: list[str] | str | None = None, *legacy_args):

    from langchain_unstructured import UnstructuredLoader
    from langchain_core.documents import Document as LangchainDocument
    from app.ai.rag import index_langchain_documents
    from app.ai.md_formatter import normalize_to_structured_markdown

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

        raw_text = "\n\n".join(doc.page_content for doc in docs if doc.page_content)
        print(f"[WORKER] Normalizzazione in markdown atomico per il documento {document_id}...")
        normalization = normalize_to_structured_markdown(
            raw_text, source_name=source_name, reference_url=reference_url
        )

        if normalization.needs_review:
            print(f"[WORKER] Documento {document_id} marcato come needs_review: {normalization.review_notes}")
            with session_scope() as db:
                db_doc = db.query(Document).filter(Document.id == document_id).first()
                if db_doc:
                    db_doc.processing_status = "needs_review"
                    db_doc.review_notes = normalization.review_notes
                    db_doc.extracted_text = (
                        "ATTENZIONE: verifica di fedeltà numerica/fattuale fallita, documento NON indicizzato.\n\n"
                        + (normalization.markdown or "Nessun testo generato.")
                    )
                    db.commit()
            return

        normalized_docs = [LangchainDocument(page_content=normalization.markdown)] if normalization.markdown else []

        chunk_count = index_langchain_documents(
            normalized_docs, category_names=category_names, document_id=str(document_id),
            reference_url=reference_url, source_name=source_name,
        )
        preview_text = normalization.markdown[:500] if normalization.markdown else "Nessun testo estratto."

        with session_scope() as db:
            db_doc = db.query(Document).filter(Document.id == document_id).first()
            if db_doc:
                db_doc.extracted_text = preview_text
                db_doc.processing_status = "indexed"
                db.commit()

        print(f"[WORKER] Documento {document_id} processato! Chunks: {chunk_count}")

    except Exception as e:
        print(f"[WORKER] Errore elaborazione documento {document_id}: {e}")


@celery_app.task(name="app.tasks.document_tasks.force_index_document_task")
def force_index_document_task(document_id: UUID | str):
    """
    Indicizza il Markdown di un documento in needs_review dopo la conferma di un
    amministratore (vedi document_service.force_index_document).
    """
    from langchain_core.documents import Document as LangchainDocument
    from app.ai.rag import index_langchain_documents
    from app.services.document_service import (
        FORCED_REVIEW_NOTE, delete_document_chunks, reviewed_markdown,
    )

    with session_scope() as db:
        source = db.query(Document).filter(Document.id == document_id).first()
        markdown = reviewed_markdown(source.extracted_text) if source else ""
        if not source or source.processing_status != "pending" or not markdown:
            print(f"[WORKER] Indicizzazione forzata ignorata per il documento {document_id}.")
            return
        category_names = sorted(c.name for c in source.categories)
        reference_url = source.reference_url
        source_name = source.filename
        notes = source.review_notes
        # idempotente: un eventuale tentativo precedente non lascia chunk duplicati
        delete_document_chunks(db, document_id)

    try:
        chunk_count = index_langchain_documents(
            [LangchainDocument(page_content=markdown)], category_names=category_names,
            document_id=str(document_id), reference_url=reference_url, source_name=source_name,
        )
    except Exception as e:
        print(f"[WORKER] Indicizzazione forzata fallita per il documento {document_id}: {e}")
        with session_scope() as db:
            db_doc = db.query(Document).filter(Document.id == document_id).first()
            if db_doc and db_doc.processing_status == "pending":
                db_doc.processing_status = "needs_review"
        return

    with session_scope() as db:
        db_doc = db.query(Document).filter(Document.id == document_id).first()
        if db_doc:
            db_doc.extracted_text = markdown[:500]
            db_doc.processing_status = "indexed"
            if not (notes or "").startswith(FORCED_REVIEW_NOTE):
                db_doc.review_notes = FORCED_REVIEW_NOTE + ("\n" + notes if notes else "")
    print(f"[WORKER] Documento {document_id} indicizzato manualmente. Chunks: {chunk_count}")
