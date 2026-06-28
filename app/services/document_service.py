from uuid import UUID
import os
import tempfile
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
from langchain_unstructured import UnstructuredLoader
from langchain_community.document_loaders import WebBaseLoader
from app.models.document import Document
from app.models.category import Category
from app.ai.rag import index_langchain_documents

def get_document(db: Session, document_id: int):
    return db.query(Document).filter(Document.id == document_id).first()

def get_documents(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Document).offset(skip).limit(limit).all()

def process_and_upload_document(db: Session, file: UploadFile | None, url: str | None, category_id: int | None, user_id: UUID):
    docs = []
    filename = "Link Web"
    content_type = "text/html"
    document_url = url

    if file:
        filename = file.filename
        content_type = file.content_type

        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as temp_file:
            content = file.file.read()
            temp_file.write(content)
            temp_path = temp_file.name

        try:
            print(f"[SERVICE] 📄 Estrazione dati da: {filename}...")
            # nuovo loader aggiornato
            loader = UnstructuredLoader(temp_path)
            docs = loader.load()
        finally:
            os.remove(temp_path)

    elif url:
        print(f"[SERVICE] 🌐 Estrazione dati da URL: {url}...")
        filename = url
        loader = WebBaseLoader(url)
        docs = loader.load()
    else:
        raise ValueError("Devi fornire un file oppure un URL valido.")

    category_name = "Generale"
    if category_id:
        db_category = db.query(Category).filter(Category.id == category_id).first()
        if db_category:
            category_name = db_category.name

    chunk_count = index_langchain_documents(docs, category_name=category_name)

    preview_text = docs[0].page_content[:500] if docs else "Nessun testo estratto."

    db_document = Document(
        filename=filename,
        content_type=content_type,
        link=document_url,
        extracted_text=preview_text,
        category_id=category_id
    )

    db_document.apply_audit_fields(user_id=user_id, is_create=True)

    db.add(db_document)
    db.commit()
    db.refresh(db_document)

    return db_document, chunk_count

def delete_document(db: Session, document_id: int):
    db_document = get_document(db, document_id)
    if db_document:
        db.delete(db_document)
        db.commit()
    else:
        raise HTTPException(status_code=404, detail="Categoria non trovata")
