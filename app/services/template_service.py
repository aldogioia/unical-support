from uuid import UUID
from sqlalchemy.orm import Session
from app.models.template import Template, TemplateStatus
from app.models.category import Category
from app.schemas.template import TemplateCreate, TemplateUpdate
from fastapi import HTTPException

def get_template(db: Session, template_id: int):
    return db.query(Template).filter(Template.id == template_id).first()

def get_templates(db: Session, skip: int = 0, limit: int = 100):
    return (
        db.query(Template)
        .filter(Template.status == TemplateStatus.ACTIVE)
        .offset(skip)
        .limit(limit)
        .all()
    )

def get_templates_by_category(db: Session, category_id: int):
    return (
        db.query(Template)
        .join(Template.categories)
        .filter(Category.id == category_id)
        .filter(Template.status == TemplateStatus.ACTIVE)
        .all()
    )

def get_pending_templates(db: Session):
    return (
        db.query(Template)
        .filter(Template.status == TemplateStatus.PENDING_APPROVAL)
        .all()
    )

def create_template(db: Session, template: TemplateCreate, user_id: UUID):
    db_template = Template(
        name=template.name,
        subject_template=template.subject_template,
        body_template=template.body_template,
        status=TemplateStatus.ACTIVE
    )

    if template.category_ids:
        categories = db.query(Category).filter(Category.id.in_(template.category_ids)).all()
        db_template.categories = categories

    db_template.apply_audit_fields(user_id=user_id, is_create=True)

    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template

def create_template_from_agent(db: Session, name: str, body_template: str, category_ids: list[int], user_id: UUID, subject_template: str = None):
    db_template = Template(
        name=name,
        subject_template=subject_template,
        body_template=body_template,
        status=TemplateStatus.PENDING_APPROVAL
    )

    if category_ids:
        categories = db.query(Category).filter(Category.id.in_(category_ids)).all()
        db_template.categories = categories

    db_template.apply_audit_fields(user_id=user_id, is_create=True)

    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template

def review_template(db: Session, template_id: int, action: str, user_id: UUID):
    db_template = get_template(db, template_id)
    if not db_template:
        raise HTTPException(status_code=404, detail="Template non trovato")

    if action == "approve":
        db_template.status = TemplateStatus.ACTIVE
    elif action == "reject":
        db_template.status = TemplateStatus.REJECTED

    db_template.apply_audit_fields(user_id=user_id)

    db.commit()
    db.refresh(db_template)
    return db_template

def update_template(db: Session, template_id: int, template_data: TemplateUpdate, user_id: UUID):
    db_template = get_template(db, template_id)
    if not db_template:
        raise HTTPException(status_code=404, detail="Template non trovato")

    update_dict = template_data.model_dump(exclude_unset=True)

    if "category_ids" in update_dict:
        category_ids = update_dict.pop("category_ids")
        if category_ids is not None:
            db_template.categories = db.query(Category).filter(Category.id.in_(category_ids)).all()

    for key, value in update_dict.items():
        setattr(db_template, key, value)
    
    db_template.apply_audit_fields(user_id=user_id)

    db.commit()
    db.refresh(db_template)
    return db_template

def delete_template(db: Session, template_id: int):
    db_template = get_template(db, template_id)
    if db_template:
        db.delete(db_template)
        db.commit()
    else:
        raise HTTPException(status_code=404, detail="Template non trovato")

def increment_usage(db: Session, template_id: int, user_id: UUID):
    db_template = get_template(db, template_id)
    if db_template:
        db_template.usage_count += 1
        db_template.apply_audit_fields(user_id=user_id)
        db.commit()