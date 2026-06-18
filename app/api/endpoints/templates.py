from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.schemas.template import TemplateResponse, TemplateCreate, TemplateUpdate
from app.services import template_service
from app.db.database import get_db

router = APIRouter()

@router.get("/", response_model=List[TemplateResponse])
def read_templates(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return template_service.get_templates(db, skip=skip, limit=limit)

@router.get("/category/{category_id}", response_model=List[TemplateResponse])
def read_templates_by_category(category_id: int, db: Session = Depends(get_db)):
    return template_service.get_templates_by_category(db, category_id=category_id)

@router.post("/", response_model=TemplateResponse)
def create_template(template: TemplateCreate, db: Session = Depends(get_db)):
    return template_service.create_template(db=db, template=template)

@router.put("/{template_id}", response_model=TemplateResponse)
def update_template(template_id: int, template_in: TemplateUpdate, db: Session = Depends(get_db)):
    updated_template = template_service.update_template(db, template_id, template_in)
    if not updated_template:
        raise HTTPException(status_code=404, detail="Template non trovato")
    return updated_template

@router.delete("/{template_id}", status_code=204)
def delete_template(template_id: int, db: Session = Depends(get_db)):
    success = template_service.delete_template(db, template_id)
    if not success:
        raise HTTPException(status_code=404, detail="Template non trovato")