# app/tasks/polling_tasks.py
from datetime import datetime, timedelta, timezone
from sqlalchemy import or_
from app.core.celery_app import celery_app
from app.listener.gmail_client import GmailClient
from app.db.database import session_scope
from app.schemas.email import EmailCreate
from app.services import email_service
from app.models.email import Email, EmailStatus
from sqlalchemy.exc import IntegrityError

@celery_app.task(name="app.tasks.polling_tasks.poll_gmail")
def poll_gmail():
    print("[BEAT] Controllo nuove email Gmail...")

    try:
        client = GmailClient()
    except Exception as e:
        print(f"[BEAT] Autenticazione Gmail fallita: {e}")
        return False

    try:
        with session_scope() as db:
            unread_emails = client.fetch_unread_emails()

            if not unread_emails:
                print("[BEAT] Nessuna nuova email.")
                return True

            print(f"[BEAT] Trovate {len(unread_emails)} nuove email.")

            for email_data in unread_emails:
                gmail_id = email_data["gmail_id"]
                email_create = EmailCreate(
                    gmail_id=gmail_id,
                    sender=email_data["sender"],
                    subject=email_data["subject"],
                    body=email_data["body"]
                )

                try:
                    db_email = email_service.create_email(db=db, email=email_create, user_id=None)
                    db.commit() 
                    
                    print(f"[BEAT] Salvata: {db_email.subject}")

                    try:
                        client.mark_as_read(gmail_id)
                        print(f"[BEAT] Etichetta UNREAD rimossa per {gmail_id}")
                    except Exception as api_err:
                        print(f"[BEAT] Avviso: Errore API Gmail per {gmail_id}: {api_err}")

                    celery_app.send_task(
                        "app.tasks.email_tasks.classify_email_task",
                        args=[db_email.id],
                        queue="classify_queue"
                    )
                    print(f"[BEAT] Lanciata in coda di classificazione.")

                except IntegrityError:
                    db.rollback()
                    client.mark_as_read(gmail_id)

            return True

    except Exception as e:
        print(f"[BEAT] Errore durante il polling: {e}")
        return False


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