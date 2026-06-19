import os
import tempfile
from fastapi import UploadFile
from sqlalchemy.orm import Session
from langchain_community.document_loaders import UnstructuredFileLoader, WebBaseLoader
from app.models.document import Document
from app.models.category import Category
from app.ai.rag import index_langchain_documents

def get_document(db: Session, document_id: int):
    return db.query(Document).filter(Document.id == document_id).first()

def get_documents(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Document).offset(skip).limit(limit).all()

# TODO cercare di migliorare questo metodo, soprattutto la categoria deve essere fornita necessariamente
def process_and_upload_document(db: Session, file: UploadFile | None, url: str | None, category_id: int | None):
    """Logica di business per gestire file multi-formato o URL e inviarli al Vector DB."""
    
    docs = []
    filename = "Link Web"
    content_type = "text/html"
    document_url = url

    # CASO 1: Elaborazione di un FILE FISICO (senza salvarlo permanentemente)
    if file:
        filename = file.filename
        content_type = file.content_type
        
        # Se c'è anche l'URL, lo usiamo solo come riferimento nel database
        
        # Creiamo un file temporaneo sicuro fornito dal sistema operativo
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as temp_file:
            content = file.file.read()
            temp_file.write(content)
            temp_path = temp_file.name

        try:
            print(f"[SERVICE] Estrazione dati dal file temporaneo: {filename}...")
            # Unstructured è in grado di leggere PDF, TXT, DOCX, ecc.
            loader = UnstructuredFileLoader(temp_path)
            docs = loader.load()
        finally:
            # FONDAMENTALE: Eliminiamo il file temporaneo, non lasciando tracce sul server!
            os.remove(temp_path)

    # CASO 2: Elaborazione di un LINK WEB
    elif url:
        print(f"[SERVICE] Estrazione dati dalla pagina web: {url}...")
        filename = url # Usiamo il link come nome file per riconoscerlo
        loader = WebBaseLoader(url)
        docs = loader.load()
    else:
        raise ValueError("Devi fornire un file caricato oppure un link URL valido.")

    # 3. Recuperiamo il nome della categoria (se fornita) per i filtri vettoriali
    category_name = "Generale"
    if category_id:
        db_category = db.query(Category).filter(Category.id == category_id).first()
        if db_category:
            category_name = db_category.name

    # 4. Invia i documenti estratti al motore RAG
    chunk_count = index_langchain_documents(docs, category_name=category_name)
    
    # 5. Salviamo un'anteprima testuale per la UI (i primi 500 caratteri)
    preview_text = docs[0].page_content[:500] if docs else "Nessun testo estratto."

    # 6. Salviamo i METADATI nel database relazionale PostgreSQL
    db_document = Document(
        filename=filename,
        content_type=content_type,
        link=document_url,
        extracted_text=preview_text,
        category_id=category_id
    )
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    
    return db_document, chunk_count

def delete_document(db: Session, document_id: int):
    db_document = get_document(db, document_id)
    if db_document:
        db.delete(db_document)
        db.commit()
        return True
    return False