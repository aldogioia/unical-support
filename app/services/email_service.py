from uuid import UUID
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import or_, and_, func
from datetime import datetime, timezone
import base64
import json
from app.models.category import Category
from app.models.email import Email, EmailStatus
from app.schemas.email import EmailUpdateDraft, EmailCreate
from fastapi import HTTPException
from app.core.email_formatting import normalize_email_text

def get_email(db: Session, email_id: UUID):
    return db.query(Email).filter(Email.id == email_id).first()

def get_emails(db: Session, status: EmailStatus = None, skip: int = 0, limit: int = 100):
    query = db.query(Email)
    if status:
        query = query.filter(Email.status == status)
    # Ordiniamo per le più recenti
    return query.order_by(Email.received_at.desc(), Email.id.desc()).offset(skip).limit(limit).all()

def create_email(db: Session, email: EmailCreate, user_id: UUID):
    existing_email = db.query(Email).filter(Email.gmail_id == email.gmail_id).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="Email già processata")

    db_email = Email(
        gmail_id=email.gmail_id,
        sender=email.sender,
        subject=email.subject,
        body=email.body,
        received_at=email.received_at or datetime.now(timezone.utc),
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
    db_email = db.query(Email).filter(Email.id == email_id).populate_existing().with_for_update().first()
    if not db_email:
        raise HTTPException(status_code=404, detail="Email non trovata")

    if update_data.expected_revision is not None and db_email.draft_revision != update_data.expected_revision:
        raise HTTPException(status_code=409, detail="La bozza sul server è cambiata. Le tue modifiche locali sono conservate: confronta le versioni prima di salvare.")
    if db_email.status not in (EmailStatus.DRAFT, EmailStatus.ESCALATED, EmailStatus.FAILED):
        raise HTTPException(status_code=409, detail="Questa email è in elaborazione o è già stata inviata.")
    if update_data.status not in (EmailStatus.DRAFT, EmailStatus.ESCALATED, EmailStatus.SENT, EmailStatus.FAILED):
        raise HTTPException(status_code=400, detail="Stato non valido per una revisione manuale.")
    db_email.manually_edited = True
    db_email.draft_revision += 1
    db_email.processing_generation += 1
    db_email.processing_token = None
    db_email.processing_started_at = None
    db_email.failure_stage = None
    db_email.generated_draft = normalize_email_text(update_data.generated_draft)
    if not db_email.generated_draft:
        raise HTTPException(status_code=400, detail="La risposta non può essere vuota.")
    db_email.status = update_data.status

    # Se lo status diventa SENT, invia tramite il provider configurato.
    if update_data.status == EmailStatus.SENT:
        try:
            from app.listener.client_factory import get_email_client
            with get_email_client() as client:
                client.send_reply(
                    original_gmail_id=db_email.gmail_id,
                    reply_text=db_email.generated_draft,
                    sender_email=db_email.sender,
                    subject=db_email.subject or '',
                    response_language=db_email.response_language,
                    ai_disclaimer=db_email.ai_disclaimer,
                )
        except Exception as e:
            # Se l'invio fallisce non blocchiamo il salvataggio del draft,
            # ma segnaliamo l'errore e teniamo lo status su FAILED
            print(f"[EMAIL_SERVICE] Errore invio email: {e}")
            db_email.status = EmailStatus.FAILED
            db_email.failure_stage = 'send'

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


def get_email_page(db: Session, status=None, cursor=None, limit=50, q=''):
    query = db.query(Email).options(selectinload(Email.categories))
    counts = {state.value: count for state, count in db.query(Email.status, func.count(Email.id)).group_by(Email.status).all()}
    counts = {state.value: counts.get(state.value, 0) for state in EmailStatus}
    counts['ALL'] = sum(counts.values())
    if status:
        query = query.filter(Email.status == status)
    if q.strip():
        term = q.strip()
        query = query.filter(or_(Email.sender.icontains(term, autoescape=True), Email.subject.icontains(term, autoescape=True),
                                 Email.body.icontains(term, autoescape=True), Email.categories.any(Category.name.icontains(term, autoescape=True))))
    total = query.count()
    if cursor:
        try:
            timestamp, identifier = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
            received = datetime.fromisoformat(timestamp)
            if received.tzinfo is None:
                raise ValueError()
            identifier = UUID(identifier)
        except (ValueError, TypeError, UnicodeError, KeyError):
            raise HTTPException(status_code=422, detail='Cursore di paginazione non valido.')
        query = query.filter(or_(Email.received_at < received, and_(Email.received_at == received, Email.id < identifier)))
    rows = query.order_by(Email.received_at.desc(), Email.id.desc()).limit(limit + 1).all()
    items = rows[:limit]
    next_cursor = None
    if len(rows) > limit and items:
        last = items[-1]
        next_cursor = base64.urlsafe_b64encode(json.dumps([last.received_at.isoformat(), str(last.id)]).encode()).decode()
    return dict(items=items, next_cursor=next_cursor, total=total, counts=counts)


def retry_email(db: Session, email_id: UUID, expected_revision=None):
    from app.services.email_processing import enqueue_processing, release_processing
    email = db.query(Email).filter(Email.id == email_id).populate_existing().with_for_update().first()
    if not email:
        raise HTTPException(status_code=404, detail='Email non trovata')
    if expected_revision is not None and expected_revision != email.draft_revision:
        raise HTTPException(status_code=409, detail='Email aggiornata da un altro operatore. Ricarica il dettaglio prima di riprovare.')
    if email.status != EmailStatus.FAILED:
        raise HTTPException(status_code=409, detail='L’email non è più in errore o è già stata riaccodata.')
    if email.manually_edited or email.failure_stage == 'send':
        raise HTTPException(status_code=409, detail='La bozza revisionata è protetta: usa Approva e invia per ritentare la consegna senza rigenerarla.')
    stage = 'classify' if email.failure_stage == 'classify' or not email.categories else 'respond'
    email.status = EmailStatus.TO_CLASSIFY if stage == 'classify' else EmailStatus.TO_RESPOND
    email.processing_generation += 1
    email.draft_revision += 1
    email.failure_stage = None
    release_processing(email)
    identifier, generation = email.id, email.processing_generation
    db.commit()
    try:
        enqueue_processing(identifier, stage, generation)
    except Exception:
        db.refresh(email)
        if email.processing_generation == generation and email.processing_token is None and email.status in (EmailStatus.TO_CLASSIFY, EmailStatus.TO_RESPOND):
            email.status = EmailStatus.FAILED
            email.failure_stage = stage
            db.commit()
        raise HTTPException(status_code=503, detail='Impossibile accodare l’elaborazione. La bozza è conservata: riprova tra poco.')
    db.refresh(email)
    return email


def retry_failed_emails(db: Session, exclude_ids=None):
    identifiers = [row[0] for row in db.query(Email.id).filter(Email.status == EmailStatus.FAILED, Email.manually_edited.is_(False), or_(Email.failure_stage.is_(None), Email.failure_stage != 'send'), ~Email.id.in_(exclude_ids or [])).limit(100).all()]
    skipped = db.query(Email).filter(Email.status == EmailStatus.FAILED, or_(Email.manually_edited.is_(True), Email.failure_stage == 'send', Email.id.in_(exclude_ids or []))).count()
    queued = failed = 0
    for identifier in identifiers:
        try:
            retry_email(db, identifier)
            queued += 1
        except HTTPException as exc:
            db.rollback()
            if exc.status_code == 503:
                failed += 1
            else:
                skipped += 1
    remaining = db.query(Email).filter(Email.status == EmailStatus.FAILED, Email.manually_edited.is_(False), or_(Email.failure_stage.is_(None), Email.failure_stage != 'send'), ~Email.id.in_(exclude_ids or [])).count()
    return dict(queued_count=queued, skipped_count=skipped, failed_count=failed, remaining_count=remaining)
