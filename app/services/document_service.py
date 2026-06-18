from sqlalchemy.orm import Session
from app.models.document import Document
from app.schemas.document import DocumentCreate

def get_document(db: Session, document_id: int):
    return db.query(Document).filter(Document.id == document_id).first()

def get_documents(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Document).offset(skip).limit(limit).all()

def create_document(db: Session, document: DocumentCreate):
    db_document = Document(
        filename=document.filename,
        content_type=document.content_type,
        extracted_text=document.extracted_text,
        category_id=document.category_id
    )
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    return db_document

def delete_document(db: Session, document_id: int):
    db_document = get_document(db, document_id)
    if db_document:
        db.delete(db_document)
        db.commit()
        return True
    return False