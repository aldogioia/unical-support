from app.core.celery_app import celery_app
from app.listener.gmail_client import GmailClient
from app.db.database import session_scope
from app.schemas.email import EmailCreate
from app.services import email_service
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
                email_create = EmailCreate(
                    gmail_id=email_data["gmail_id"],
                    sender=email_data["sender"],
                    subject=email_data["subject"],
                    body=email_data["body"]
                )

                try:
                    db_email = email_service.create_email(db=db, email=email_create)
                    db.commit() 
                    
                    print(f"[BEAT] Salvata: {db_email.subject}")

                    celery_app.send_task(
                        "app.tasks.email_tasks.classify_email_task",
                        args=[db_email.id],
                        queue="classify_queue",
                        countdown=2 
                    )

                    print(f"[BEAT] Lanciata in coda. Rimarrà UNREAD su Gmail fino a completamento.")

                except IntegrityError:
                    db.rollback()

            return True

    except Exception as e:
        print(f"[BEAT] Errore durante il polling: {e}")
        return False