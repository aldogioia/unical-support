from uuid import UUID
from app.api.authentication import get_current_user
from app.models.user import User
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from app.schemas.email import EmailResponse, EmailUpdateDraft, EmailCreate, EmailFetchResponse
from app.services.email_polling_service import enqueue_email_poll, PollCoordinator
from app.models.enumerators.enumerators import EmailStatus
from app.models.email import Email
from app.services import email_service
from app.db.database import get_db
from app.tasks.email_tasks import classify_email_task

router = APIRouter()


@router.post('/fetch-now', response_model=EmailFetchResponse, status_code=202)
def fetch_emails_now(current_user: Annotated[User, Depends(get_current_user)]):
    try:
        return enqueue_email_poll()
    except Exception:
        raise HTTPException(status_code=503, detail='Controllo email non disponibile. Riprova tra poco.')


@router.get('/fetch-status/{job_id}', response_model=EmailFetchResponse)
def read_email_fetch_status(job_id: UUID, current_user: Annotated[User, Depends(get_current_user)]):
    try:
        result = PollCoordinator().status(str(job_id))
    except Exception:
        raise HTTPException(status_code=503, detail='Impossibile verificare lo stato del controllo email.')
    if not result:
        raise HTTPException(status_code=404, detail='Controllo email non trovato o scaduto.')
    return result

@router.get("/", response_model=List[EmailResponse])
def read_emails(
    current_user: Annotated[User, Depends(get_current_user)],
    status: Optional[EmailStatus] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    return email_service.get_emails(db, status=status, skip=skip, limit=limit)

@router.get("/{email_id}", response_model=EmailResponse)
def read_email(
    email_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    email = email_service.get_email(db, email_id=email_id)
    if email is None:
        raise HTTPException(status_code=404, detail="Email non trovata")
    return email


@router.post("/", response_model=EmailResponse)
def create_new_email(email: EmailCreate, current_user: Annotated[User, Depends(get_current_user)], db: Session = Depends(get_db)):
    db_email = email_service.create_email(db=db, email=email, user_id=current_user.id)
    classify_email_task.delay(db_email.id)
    return db_email

@router.put("/{email_id}/draft", response_model=EmailResponse)
def update_email_draft(email_id: UUID, update_data: EmailUpdateDraft, current_user: Annotated[User, Depends(get_current_user)], db: Session = Depends(get_db)):
    return email_service.update_email_draft(db, email_id=email_id, update_data=update_data, user_id=current_user.id)
