from sqlalchemy.orm import Session
from app.models.category import Category
from app.models.email import Email, EmailStatus
from app.schemas.email import EmailUpdateDraft, EmailCreate

def get_email(db: Session, email_id: int):
    return db.query(Email).filter(Email.id == email_id).first()

def get_emails(db: Session, status: EmailStatus = None, skip: int = 0, limit: int = 100):
    query = db.query(Email)
    if status:
        query = query.filter(Email.status == status)
    # Ordiniamo per le più recenti
    return query.order_by(Email.id.desc()).offset(skip).limit(limit).all()

def create_email(db: Session, email: EmailCreate):
    db_email = Email(
        gmail_id=email.gmail_id,
        sender=email.sender,
        subject=email.subject,
        body=email.body,
        status=EmailStatus.UNREAD
    )
    
    if getattr(email, 'category_ids', None):
        categories = db.query(Category).filter(Category.id.in_(email.category_ids)).all()
        db_email.categories = categories
        
    db.add(db_email)
    db.commit()
    db.refresh(db_email)
    return db_email

def update_email_draft(db: Session, email_id: int, update_data: EmailUpdateDraft):
    db_email = db.query(Email).filter(Email.id == email_id).first()
    if not db_email:
        return None
    
    db_email.generated_draft = update_data.generated_draft
    db_email.status = update_data.status
    
    db.commit()
    db.refresh(db_email)
    return db_email

# Questa funzione verrà usata dal Worker Asincrono in futuro
def update_email_status(db: Session, email_id: int, new_status: EmailStatus, category_ids: list[int] = None):
    db_email = db.query(Email).filter(Email.id == email_id).first()
    if db_email:
        db_email.status = new_status
        if category_ids:
            db_email.categories = db.query(Category).filter(Category.id.in_(category_ids)).all()
        db.commit()
        db.refresh(db_email)
    return db_email