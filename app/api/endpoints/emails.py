from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from app.schemas.email import EmailResponse, EmailUpdateDraft, EmailCreate
from app.models.email import EmailStatus, Email
from app.services import email_service
from app.db.database import get_db
from app.tasks.email_tasks import process_new_email
from app.core.dependencies import get_current_user

router = APIRouter()

@router.get("/", response_model=List[EmailResponse])
def read_emails(
    status: Optional[EmailStatus] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _=Depends(get_current_user)  # ✅ protetto
):
    return email_service.get_emails(db, status=status, skip=skip, limit=limit)

@router.get("/{email_id}", response_model=EmailResponse)
def read_email(
    email_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user)  # ✅ protetto
):
    email = email_service.get_email(db, email_id=email_id)
    if email is None:
        raise HTTPException(status_code=404, detail="Email non trovata")
    return email

@router.post("/", response_model=EmailResponse)
def create_new_email(
    email: EmailCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_user)  # ✅ protetto
):
    existing_email = db.query(Email).filter(Email.gmail_id == email.gmail_id).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="Email già processata")

    db_email = email_service.create_email(db=db, email=email)
    process_new_email.apply_async(args=[db_email.id], queue="emails_queue")
    return db_email

@router.put("/{email_id}/draft", response_model=EmailResponse)
def update_email_draft(
    email_id: int,
    update_data: EmailUpdateDraft,
    db: Session = Depends(get_db),
    _=Depends(get_current_user)  # ✅ protetto
):
    email = email_service.update_email_draft(db, email_id=email_id, update_data=update_data)
    if email is None:
        raise HTTPException(status_code=404, detail="Email non trovata")
    return email