from uuid import UUID
from app.api.authentication import get_current_user
from app.models.user import User
from typing import Annotated
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
    category_id: Optional[UUID] = Form(None),
    db: Session = Depends(get_db),
    current_user = Annotated[User, Depends(get_current_user)]
):
    if not file and not url:
        raise HTTPException(status_code=400, detail="Devi fornire un 'file' oppure un 'url'.")
    try:
        db_document, chunks = document_service.process_and_upload_document(db=db, file=file, url=url, category_id=category_id, user_id=current_user.id)
        return db_document
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore critico: {str(e)}")

@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: UUID, db: Session = Depends(get_db)):
    document_service.delete_document(db, document_id)
