from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.schemas.category import CategoryResponse, CategoryCreate, CategoryUpdate
from app.services import category_service
from app.db.database import get_db
from app.core.dependencies import get_current_user

router = APIRouter()

@router.get("/", response_model=List[CategoryResponse])
def read_categories(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    #_=Depends(get_current_user)
):
    return category_service.get_categories(db, skip=skip, limit=limit)

@router.post("/", response_model=CategoryResponse)
def create_category(
    category: CategoryCreate,
    db: Session = Depends(get_db),
    #_=Depends(get_current_user)
):
    db_category = category_service.get_category_by_name(db, name=category.name)
    if db_category:
        raise HTTPException(status_code=400, detail="Categoria già esistente")
    return category_service.create_category(db=db, category=category)

@router.put("/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: int,
    category_in: CategoryUpdate,
    db: Session = Depends(get_db),
    #_=Depends(get_current_user)
):
    updated_category = category_service.update_category(db, category_id, category_in)
    if not updated_category:
        raise HTTPException(status_code=404, detail="Categoria non trovata")
    return updated_category

@router.delete("/{category_id}", status_code=204)
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    #_=Depends(get_current_user)
):
    success = category_service.delete_category(db, category_id)
    if not success:
        raise HTTPException(status_code=404, detail="Categoria non trovata")