from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional

from app.schemas.document import DocumentResponse
from app.services import document_service
from app.db.database import get_db

router = APIRouter()

@router.get("/", response_model=List[DocumentResponse])
def read_documents(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return document_service.get_documents(db, skip=skip, limit=limit)

@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    category_id: Optional[int] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Permette l'indicizzazione vettoriale.
    Accetta un file (PDF, TXT, DOCX), un link Web (URL) o entrambi (es. il PDF scaricato e il suo link per la UI).
    Il file fisico NON viene mai salvato in modo permanente sul server.
    """
    if not file and not url:
        raise HTTPException(status_code=400, detail="Devi fornire un 'file' oppure un 'url'.")

    try:
        db_document, chunks = document_service.process_and_upload_document(
            db=db, 
            file=file, 
            url=url, 
            category_id=category_id
        )
        print(f"Indicizzazione completata: {chunks} frammenti vettoriali generati.")
        return db_document
        
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore critico del server: {str(e)}")

@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: int, db: Session = Depends(get_db)):
    success = document_service.delete_document(db, document_id)
    if not success:
        raise HTTPException(status_code=404, detail="Documento non trovato")