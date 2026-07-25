from uuid import UUID
from sqlalchemy.orm import Session
from app.models.category import Category
from app.models.email import Email, EmailStatus
from app.schemas.email import EmailUpdateDraft, EmailCreate
from fastapi import HTTPException

def get_email(db: Session, email_id: UUID):
    return db.query(Email).filter(Email.id == email_id).first()

def get_emails(db: Session, status: EmailStatus = None, skip: int = 0, limit: int = 100):
    query = db.query(Email)
    if status:
        query = query.filter(Email.status == status)
    # Ordiniamo per le più recenti
    return query.order_by(Email.id.desc()).offset(skip).limit(limit).all()

def create_email(db: Session, email: EmailCreate, user_id: UUID):
    existing_email = db.query(Email).filter(Email.gmail_id == email.gmail_id).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="Email già processata")

    db_email = Email(
        gmail_id=email.gmail_id,
        sender=email.sender,
        subject=email.subject,
        body=email.body,
        status=EmailStatus.TO_CLASSIFY
    )
    
    if getattr(email, 'category_ids', None):
        categories = db.query(Category).filter(Category.id.in_(email.category_ids)).all()
        db_email.categories = categories

    db_email.apply_audit_fields(user_id=user_id, is_create=True)

    db.add(db_email)
    db.commit()
    db.refresh(db_email)
    return db_email

def update_email_draft(db: Session, email_id: UUID, update_data: EmailUpdateDraft, user_id: UUID):
    db_email = db.query(Email).filter(Email.id == email_id).first()
    if not db_email:
        raise HTTPException(status_code=404, detail="Email non trovata")

    db_email.generated_draft = update_data.generated_draft
    db_email.status = update_data.status

    # Se lo status diventa SENT, invia davvero l'email tramite Gmail
    if update_data.status == EmailStatus.SENT:
        try:
            from app.listener.gmail_client import GmailClient
            client = GmailClient()
            client.send_reply(
                original_gmail_id=db_email.gmail_id,
                reply_text=update_data.generated_draft,
                sender_email=db_email.sender,
                subject=db_email.subject or '',
            )
        except Exception as e:
            # Se l'invio fallisce non blocchiamo il salvataggio del draft,
            # ma segnaliamo l'errore e teniamo lo status su FAILED
            print(f"[EMAIL_SERVICE] Errore invio Gmail: {e}")
            db_email.status = EmailStatus.FAILED

    db_email.apply_audit_fields(user_id=user_id)
    db.commit()
    db.refresh(db_email)
    return db_email

def update_email_status(db: Session, email_id: UUID, new_status: EmailStatus, user_id: UUID, category_ids: list[UUID] = None):
    db_email = db.query(Email).filter(Email.id == email_id).first()
    if db_email:
        db_email.status = new_status
        if category_ids:
            db_email.categories = db.query(Category).filter(Category.id.in_(category_ids)).all()
        db_email.apply_audit_fields(user_id=user_id)
        db.commit()
        db.refresh(db_email)
    return db_email