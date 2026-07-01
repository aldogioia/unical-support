from sqlalchemy.orm import Session
from app.models.category import Category
from app.schemas.category import CategoryCreate, CategoryUpdate
from uuid import UUID
from fastapi import HTTPException

def get_category(db: Session, category_id: UUID):
    return db.query(Category).filter(Category.id == category_id).first()

def get_category_by_name(db: Session, name: str):
    return db.query(Category).filter(Category.name == name).first()

def get_categories(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Category).offset(skip).limit(limit).all()

def create_category(db: Session, category: CategoryCreate, user_id: UUID):
    db_category = get_category_by_name(db, name=category.name)
    if db_category:
        raise HTTPException(status_code=400, detail="Categoria già esistente")

    db_category = Category(
        name=category.name,
        description=category.description
    )

    db_category.apply_audit_fields(user_id=user_id, is_create=True)

    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

def update_category(db: Session, category_id: UUID, category_data: CategoryUpdate, user_id: UUID):
    db_category = get_category(db, category_id)
    if not db_category:
        raise HTTPException(status_code=404, detail="Categoria non trovata")
    
    update_dict = category_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(db_category, key, value)
    db_category.apply_audit_fields(user_id=user_id)
        
    db.commit()
    db.refresh(db_category)
    return db_category

def delete_category(db: Session, category_id: UUID):
    db_category = get_category(db, category_id)
    if db_category:
        db.delete(db_category)
        db.commit()
    else:
        raise HTTPException(status_code=404, detail="Categoria non trovata")