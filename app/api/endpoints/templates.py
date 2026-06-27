from app.api.authentication import get_current_user
from app.models.user import User
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.schemas.template import TemplateResponse, TemplateCreate, TemplateUpdate, TemplateReviewAction
from app.services import template_service
from app.db.database import get_db

router = APIRouter()

@router.get("/", response_model=List[TemplateResponse])
def read_templates(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return template_service.get_templates(db, skip=skip, limit=limit)

@router.get("/pending", response_model=List[TemplateResponse])
def read_pending_templates(db: Session = Depends(get_db)):
    return template_service.get_pending_templates(db)

@router.get("/category/{category_id}", response_model=List[TemplateResponse])
def read_templates_by_category(category_id: int, db: Session = Depends(get_db)):
    return template_service.get_templates_by_category(db, category_id=category_id)

@router.post("/", response_model=TemplateResponse)
def create_template(template: TemplateCreate, db: Session = Depends(get_db), current_user = Annotated[User, Depends(get_current_user)]):
    return template_service.create_template(db=db, template=template, user_id=current_user.id)

@router.post("/{template_id}/review", response_model=TemplateResponse)
def review_template(template_id: int, action: TemplateReviewAction, db: Session = Depends(get_db), current_user = Annotated[User, Depends(get_current_user)]):
    return template_service.review_template(db, template_id, action.action, user_id=current_user.id)

@router.put("/{template_id}", response_model=TemplateResponse)
def update_template(template_id: int, template_in: TemplateUpdate, db: Session = Depends(get_db), current_user = Annotated[User, Depends(get_current_user)]):
    return template_service.update_template(db, template_id, template_in, user_id=current_user.id)

@router.delete("/{template_id}", status_code=204)
def delete_template(template_id: int, db: Session = Depends(get_db)):
    template_service.delete_template(db, template_id)
