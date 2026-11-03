from uuid import UUID
from app.api.authentication import get_current_user
from app.api.authorization import is_admin_user
from app.models.user import User
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional

from app.schemas.document import DocumentResponse, DocumentUpdate, DocumentForceIndex
from app.services import document_service
from app.db.database import get_db

router = APIRouter()

@router.get("/", response_model=List[DocumentResponse])
def read_documents(
    current_user: Annotated[User, Depends(get_current_user)],
    skip: int = 0,
    limit: int = 150,
    db: Session = Depends(get_db),
):
    return document_service.get_documents(db, skip=skip, limit=limit)

@router.put("/{document_id}", response_model=DocumentResponse)
def update_document(
    document_id: UUID,
    document_in: DocumentUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    return document_service.update_document(db, document_id, document_in, current_user.id)

@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    current_user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(...),
    reference_url: Optional[str] = Form(None),
    category_ids: Optional[List[UUID]] = Form(None),
    db: Session = Depends(get_db),
):
    try:
        db_document, chunks = document_service.process_and_upload_document(db=db, file=file, category_ids=category_ids, user_id=current_user.id, reference_url=reference_url)
        return db_document
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore critico: {str(e)}")

@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    document_service.delete_document(db, document_id)


@router.post("/{document_id}/force-index", response_model=DocumentResponse)
def force_index_document(
    document_id: UUID,
    current_user: Annotated[User, Depends(is_admin_user)],
    db: Session = Depends(get_db),
    body: Optional[DocumentForceIndex] = None,
):
    """Indicizza comunque un documento fermato dalla verifica di fedeltà (solo amministratori).
    Con `markdown` nel corpo indicizza il testo corretto dall'amministratore al posto di quello generato."""
    markdown = body.markdown if body else None
    return document_service.force_index_document(db, document_id, current_user.id, markdown=markdown)
