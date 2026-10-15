import os
import json
import shutil
import uuid
import logging
from uuid import UUID
from fastapi import UploadFile, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.models.document import Document
from app.models.category import Category
from app.schemas.document import DocumentUpdate
from app.tasks.document_tasks import process_document_task
from app.core.urls import normalize_reference_url

UPLOAD_DIR = "/app/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_DOCUMENT_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/msword": ".docx",
    "text/plain": ".txt",
    "application/json": ".json",
    "text/json": ".json",
    "application/x-yaml": ".yaml",
    "text/yaml": ".yaml",
    "text/x-yaml": ".yaml",
    "application/yaml": ".yaml",
    "text/markdown": ".md",
    "text/x-markdown": ".md",
}
ALLOWED_EXTENSIONS = {".pdf", ".yaml", ".yml", ".txt", ".json", ".docx", ".md"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

def get_document(db: Session, document_id: UUID):
    return db.query(Document).filter(Document.id == document_id).first()

def get_documents(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Document).offset(skip).limit(limit).all()

def _resolve_categories(db: Session, category_ids: list[UUID] | None) -> list[Category]:
    """
    Converte una lista di ID in oggetti Category, eliminando i duplicati.
    Solleva ValueError se uno o più ID non corrispondono a categorie esistenti.
    """
    unique_ids = list(dict.fromkeys(category_ids or []))
    if not unique_ids:
        return []
    categories = db.query(Category).filter(Category.id.in_(unique_ids)).all()
    found_ids = {c.id for c in categories}
    missing = [str(cid) for cid in unique_ids if cid not in found_ids]
    if missing:
        raise ValueError(f"Categorie non trovate: {', '.join(missing)}")
    return categories

def process_and_upload_document(db: Session, file: UploadFile, category_ids: list[UUID] | None, user_id: UUID, reference_url: str | None = None):
    if file is None:
        raise ValueError("Devi fornire un file locale.")
    categories = _resolve_categories(db, category_ids)
    reference_url = normalize_reference_url(reference_url)

    filename = file.filename or "documento"
    content_type = (file.content_type or "").lower()
    file_extension = os.path.splitext(filename)[1].lower()

    # 1. Validazione Tipo di File (MIME Type) ed Estensione
    is_type_valid = content_type in ALLOWED_DOCUMENT_TYPES or content_type.startswith("text/")
    is_ext_valid = file_extension in ALLOWED_EXTENSIONS

    if not is_type_valid or not is_ext_valid:
        raise ValueError(f"Tipo di file o estensione non consentiti. Formati supportati: PDF, DOCX, TXT, JSON, YAML, MD.")

    # Determina l'estensione sicura da usare su disco
    if file_extension in ALLOWED_EXTENSIONS:
        clean_ext = file_extension
    else:
        clean_ext = ALLOWED_DOCUMENT_TYPES.get(content_type, ".txt" if "text" in content_type else ".bin")

    # 2. Validazione dimensione del file (max 50MB)
    file.file.seek(0, os.SEEK_END)
    file_size = file.file.tell()
    file.file.seek(0)  # Ripristina la posizione dello stream

    if file_size > MAX_FILE_SIZE:
        max_mb = MAX_FILE_SIZE / (1024 * 1024)
        actual_mb = file_size / (1024 * 1024)
        raise ValueError(f"Dimensione del file ({actual_mb:.2f}MB) superiore al limite massimo consentito ({max_mb:.0f}MB).")

    unique_filename = f"{uuid.uuid4()}{clean_ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    db_document = Document(
        filename=filename,
        content_type=content_type,
        reference_url=reference_url,
        extracted_text="Elaborazione in corso da parte dell'IA...",
    )
    db_document.categories = categories
    db_document.apply_audit_fields(user_id=user_id, is_create=True)
    db.add(db_document)
    db.commit()
    db.refresh(db_document)

    process_document_task.delay(str(db_document.id), file_path, [str(c.id) for c in categories])
    return db_document, 0

logger = logging.getLogger(__name__)

def delete_document_chunks(db: Session, document_id: UUID | str):
    """
    Elimina tutti i chunk associati al document_id dal Vector Store (tabella langchain_pg_embedding).
    """
    try:
        db.execute(
            text("DELETE FROM langchain_pg_embedding WHERE cmetadata->>'document_id' = :doc_id"),
            {"doc_id": str(document_id)}
        )
    except Exception as e:
        logger.warning(f"Impossibile eliminare i chunk per il documento {document_id}: {e}")

def update_document_chunks_metadata(db: Session, document_id: UUID | str, metadata: dict):
    """Keep citation links and taxonomy in sync without rebuilding embeddings."""
    try:
        with db.begin_nested():
            db.execute(
                text(
                    "UPDATE langchain_pg_embedding "
                    "SET cmetadata = (COALESCE(cmetadata, '{}'::jsonb) - 'category') || CAST(:metadata AS jsonb) "
                    "WHERE cmetadata->>'document_id' = :doc_id"
                ),
                {"metadata": json.dumps(metadata), "doc_id": str(document_id)},
            )
    except Exception as e:
        logger.warning(f"Impossibile aggiornare i metadati dei chunk per il documento {document_id}: {e}")


def update_document(db: Session, document_id: UUID, document_in: DocumentUpdate, user_id: UUID):
    db_document = get_document(db, document_id)
    if not db_document:
        raise HTTPException(status_code=404, detail="Documento non trovato")

    try:
        if 'category_ids' in document_in.model_fields_set:
            db_document.categories = _resolve_categories(db, document_in.category_ids)
        if 'reference_url' in document_in.model_fields_set:
            db_document.reference_url = document_in.reference_url
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    db_document.apply_audit_fields(user_id=user_id, is_create=False)

    update_document_chunks_metadata(db, document_id, {
        'categories': sorted(c.name for c in db_document.categories),
        'reference_url': db_document.reference_url,
    })
    db.commit()
    db.refresh(db_document)
    return db_document

def delete_document(db: Session, document_id: UUID):
    db_document = get_document(db, document_id)
    if not db_document:
        raise HTTPException(status_code=404, detail="Documento non trovato")

    delete_document_chunks(db, document_id)
    db.delete(db_document)
    db.commit()
