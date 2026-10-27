# app/tasks/polling_tasks.py
from datetime import datetime, timedelta, timezone
from sqlalchemy import or_
from app.core.celery_app import celery_app
from app.listener.client_factory import get_email_client
from app.db.database import session_scope
from app.schemas.email import EmailCreate
from app.services import email_service
from app.models.email import Email, EmailStatus
from sqlalchemy.exc import IntegrityError

@celery_app.task(bind=True, name="app.tasks.polling_tasks.poll_gmail", soft_time_limit=540, time_limit=600)
def poll_gmail(self, reservation_id: str | None = None):
    from uuid import uuid4
    from app.services.email_polling_service import PollCoordinator

    coordinator = PollCoordinator()
    job_id = reservation_id or self.request.id or str(uuid4())
    if reservation_id is None and not coordinator.reserve(job_id):
        return {"status": "skipped", "message": "Un controllo è già in corso."}
    if not coordinator.begin(job_id):
        return {"status": "skipped", "message": "Prenotazione scaduta o controllo già in corso."}

    fetched_count = 0
    client = None
    try:
        print("[BEAT] Controllo nuove email...")
        try:
            client = get_email_client()
        except Exception as exc:
            print(f"[BEAT] Inizializzazione client email fallita: {exc}")
            return coordinator.update(job_id, "failed", "Impossibile accedere alla posta. Verifica provider e credenziali email.")

        unread_emails = client.fetch_unread_emails()
        with session_scope() as db:
            for email_data in unread_emails:
                gmail_id = email_data["gmail_id"]
                if db.query(Email).filter(Email.gmail_id == gmail_id).first():
                    client.mark_as_read(gmail_id)
                    continue
                try:
                    db_email = email_service.create_email(
                        db=db, user_id=None, email=EmailCreate(**email_data),
                    )
                    fetched_count += 1
                    from app.services.email_processing import enqueue_processing
                    enqueue_processing(db_email.id, 'classify', db_email.processing_generation)
                    client.mark_as_read(gmail_id)
                except IntegrityError:
                    db.rollback()
                    client.mark_as_read(gmail_id)
        return coordinator.update(
            job_id, "completed",
            f"Controllo completato: {fetched_count} nuove email acquisite e accodate per l'elaborazione AI.",
            fetched_count,
        )
    except Exception as exc:
        print(f"[BEAT] Errore durante il polling: {exc}")
        return coordinator.update(
            job_id, "failed", "Errore durante il recupero delle email. Verifica la connessione alla posta e riprova.", fetched_count,
        )
    finally:
        try:
            if client is not None:
                client.close()
        finally:
            coordinator.release(job_id)


@celery_app.task(name="app.tasks.polling_tasks.sweep_stuck_emails", soft_time_limit=120, time_limit=150)
def sweep_stuck_emails():
    """Recover expired leases/queued jobs, never reviewed drafts or active workers."""
    from sqlalchemy import and_
    from app.services.email_processing import LEASE_SECONDS, release_processing, enqueue_processing
    now = datetime.now(timezone.utc)
    jobs = []
    with session_scope() as db:
        rows = db.query(Email).filter(
            Email.status.in_([EmailStatus.TO_CLASSIFY, EmailStatus.TO_RESPOND]), Email.manually_edited.is_(False),
            or_(and_(Email.processing_token.is_(None), Email.updated_at < now - timedelta(minutes=15)),
                and_(Email.processing_token.is_not(None), or_(Email.processing_started_at.is_(None), Email.processing_started_at < now - timedelta(seconds=LEASE_SECONDS)))),
        ).with_for_update(skip_locked=True).limit(100).all()
        for email in rows:
            stage = 'classify' if email.status == EmailStatus.TO_CLASSIFY else 'respond'
            release_processing(email)
            email.processing_generation += 1
            email.updated_at = now
            jobs.append((str(email.id), stage, email.processing_generation))
    # Publish after committing generation/lease changes; consumers must see the new state.
    for identifier, stage, generation in jobs:
        try:
            enqueue_processing(identifier, stage, generation)
        except Exception:
            with session_scope() as db:
                email = db.query(Email).filter(Email.id == identifier).populate_existing().with_for_update().first()
                if email and email.processing_generation == generation and email.processing_token is None and email.status in (EmailStatus.TO_CLASSIFY, EmailStatus.TO_RESPOND):
                    email.status = EmailStatus.FAILED
                    email.failure_stage = stage
    return {'requeued_count': len(jobs)}
