from sqlalchemy.orm import Session
from app.models.template import Template
from app.models.category import Category
from app.schemas.template import TemplateCreate, TemplateUpdate

def get_template(db: Session, template_id: int):
    return db.query(Template).filter(Template.id == template_id).first()

def get_templates(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Template).offset(skip).limit(limit).all()

def get_templates_by_category(db: Session, category_id: int):
    return db.query(Template).filter(Template.category_id == category_id).all()

def create_template(db: Session, template: TemplateCreate):
    db_template = Template(
        name=template.name,
        subject_template=template.subject_template,
        body_template=template.body_template
    )
    
    if template.category_ids:
        categories = db.query(Category).filter(Category.id.in_(template.category_ids)).all()
        db_template.categories = categories

    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template

def update_template(db: Session, template_id: int, template_data: TemplateUpdate):
    db_template = get_template(db, template_id)
    if not db_template:
        return None
    
    update_dict = template_data.model_dump(exclude_unset=True)
    
    if "category_ids" in update_dict:
        category_ids = update_dict.pop("category_ids")
        if category_ids is not None:
            db_template.categories = db.query(Category).filter(Category.id.in_(category_ids)).all()

    for key, value in update_dict.items():
        setattr(db_template, key, value)
        
    db.commit()
    db.refresh(db_template)
    return db_template