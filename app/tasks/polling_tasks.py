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
                    celery_app.send_task(
                        "app.tasks.email_tasks.classify_email_task",
                        args=[str(db_email.id)], queue="classify_queue",
                    )
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


@celery_app.task(name="app.tasks.polling_tasks.sweep_stuck_emails")
def sweep_stuck_emails():
    """Ricerca e riaccoda le email rimaste incastrate per crash dei worker."""
    print("[SWEEPER] Ricerca di email bloccate (zombie)...")
    try:
        with session_scope() as db:
            time_threshold = datetime.now(timezone.utc) - timedelta(minutes=15)
            
            stuck_emails = db.query(Email).filter(
                or_(
                    Email.status == EmailStatus.TO_CLASSIFY,
                    Email.status == EmailStatus.TO_RESPOND
                ),
                Email.updated_at < time_threshold
            ).all()

            if not stuck_emails:
                print("[SWEEPER] Nessuna email bloccata trovata. Tutto regolare.")
                return True

            print(f"[SWEEPER] Trovate {len(stuck_emails)} email bloccate. Ri-accodamento in corso...")

            for email in stuck_emails:
                email.updated_at = datetime.now(timezone.utc)
                
                if email.status == EmailStatus.TO_CLASSIFY:
                    celery_app.send_task(
                        "app.tasks.email_tasks.classify_email_task",
                        args=[email.id],
                        queue="classify_queue"
                    )
                    print(f"[SWEEPER] Ri-accodata email {email.id} per CLASSIFICAZIONE.")
                
                elif email.status == EmailStatus.TO_RESPOND:
                    celery_app.send_task(
                        "app.tasks.email_tasks.respond_email_task",
                        args=[email.id],
                        queue="respond_queue"
                    )
                    print(f"[SWEEPER] Ri-accodata email {email.id} per RISPOSTA.")
            
            db.commit()
            return True
            
    except Exception as e:
        print(f"[SWEEPER] Errore critico durante l'esecuzione dello sweeper: {e}")
        return False