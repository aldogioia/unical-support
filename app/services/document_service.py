import os
import shutil
import uuid
from uuid import UUID
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
from app.models.document import Document
from app.models.category import Category
from app.tasks.document_tasks import process_document_task

UPLOAD_DIR = "/app/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def get_document(db: Session, document_id: UUID):
    return db.query(Document).filter(Document.id == document_id).first()

def get_documents(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Document).offset(skip).limit(limit).all()

def process_and_upload_document(db: Session, file: UploadFile | None, url: str | None, category_id: UUID | None, user_id: UUID):
    filename = "Link Web"
    content_type = "text/html"
    document_url = url
    file_path = None

    if file:
        filename = file.filename
        content_type = file.content_type
        file_extension = os.path.splitext(filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
    elif not url:
        raise ValueError("Devi fornire un file oppure un URL valido.")

    db_document = Document(
        filename=filename,
        content_type=content_type,
        link=document_url,
        extracted_text="Elaborazione in corso da parte dell'IA...",
        category_id=category_id
    )
    db_document.apply_audit_fields(user_id=user_id, is_create=True)
    db.add(db_document)
    db.commit()
    db.refresh(db_document)

    process_document_task.delay(db_document.id, file_path, url, category_id)

    return db_document, 0

def delete_document(db: Session, document_id: UUID):
    db_document = get_document(db, document_id)
    if db_document:
        db.delete(db_document)
        db.commit()
    else:
        raise HTTPException(status_code=404, detail="Categoria non trovata")
