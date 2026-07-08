from app.models.user import User
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.schemas.category import CategoryResponse, CategoryCreate, CategoryUpdate
from app.services import category_service
from app.db.database import get_db
from app.api.authentication import get_current_user

router = APIRouter()

@router.get("/", response_model=List[CategoryResponse])
def read_categories(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return category_service.get_categories(db, skip=skip, limit=limit)

@router.post("/", response_model=CategoryResponse)
def create_category(
    category: CategoryCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    return category_service.create_category(db=db, category=category, user_id=current_user.id)

@router.put("/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: UUID,
    category_in: CategoryUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    return category_service.update_category(db, category_id, category_in, current_user.id)

@router.delete("/{category_id}", status_code=204)
def delete_category(category_id: UUID, db: Session = Depends(get_db)):
    category_service.delete_category(db, category_id)
