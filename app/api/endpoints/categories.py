from app.models.user import User
from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from sqlalchemy.orm import Session
from uuid import UUID

from app.schemas.category import (
    CategoryResponse, 
    CategoryCreate, 
    CategoryUpdate, 
    CategoryImportResult
)
from app.services import category_service
from app.db.database import get_db
from app.api.authentication import get_current_user
from app.api.authorization import is_admin_user

router = APIRouter()

@router.get("/", response_model=List[CategoryResponse])
def read_categories(
    current_user: Annotated[User, Depends(get_current_user)],
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    return category_service.get_categories(db, skip=skip, limit=limit)

@router.post("/", response_model=CategoryResponse)
def create_category(
    category: CategoryCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    return category_service.create_category(db=db, category=category, user_id=current_user.id)

@router.post("/import", response_model=CategoryImportResult, summary="Importa categorie da file JSON (Solo Admin)")
async def import_categories_from_json(
    current_user: Annotated[User, Depends(is_admin_user)],
    file: UploadFile = File(..., description="File JSON contenente l'elenco di categorie da importare"),
    skip_duplicates: bool = Query(True, description="Se True, ignora le categorie con nome già esistente senza bloccare l'importazione"),
    db: Session = Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith(".json"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato file non valido. È consentito caricare esclusivamente file con estensione .json"
        )

    max_size = category_service.MAX_FILE_SIZE_BYTES
    content = await file.read(max_size + 1)
    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Il file caricato supera la dimensione massima consentita di {max_size // (1024 * 1024)}MB."
        )

    return category_service.import_categories_from_json_bytes(
        db=db,
        content=content,
        user_id=current_user.id,
        skip_duplicates=skip_duplicates
    )

@router.post("/bulk", response_model=CategoryImportResult, summary="Importa categorie da payload JSON (Solo Admin)")
def bulk_create_categories(
    categories: List[CategoryCreate],
    current_user: Annotated[User, Depends(is_admin_user)],
    skip_duplicates: bool = Query(True, description="Se True, ignora le categorie con nome già esistente"),
    db: Session = Depends(get_db),
):
    return category_service.import_categories_from_list(
        db=db,
        categories_data=categories,
        user_id=current_user.id,
        skip_duplicates=skip_duplicates
    )


@router.put("/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: UUID,
    category_in: CategoryUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    return category_service.update_category(db, category_id, category_in, current_user.id)

@router.delete("/{category_id}", status_code=204)
def delete_category(
    category_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    category_service.delete_category(db, category_id)

