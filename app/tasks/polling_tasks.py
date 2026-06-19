from app.core.celery_app import celery_app

@celery_app.task(name="app.tasks.polling_tasks.poll_gmail")
def poll_gmail():
    from app.listener.gmail_client import GmailClient
    from app.db.database import SessionLocal
    from app.schemas.email import EmailCreate
    from app.services import email_service
    from app.tasks.email_tasks import process_new_email
    from sqlalchemy.exc import IntegrityError

    print("[BEAT] Controllo nuove email Gmail...")

    try:
        client = GmailClient()
    except Exception as e:
        print(f"[BEAT] Autenticazione Gmail fallita: {e}")
        return False

    db = SessionLocal()
    try:
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
                print(f"[BEAT] Salvata: {db_email.subject}")

                process_new_email.apply_async(
                    args=[db_email.id],
                    queue="emails_queue"
                )

                client.mark_as_read(email_data["gmail_id"])
                print(f"[BEAT] Lanciata in coda e segnata come letta.")

            except IntegrityError:
                print(f"[BEAT]  Email {email_data['gmail_id']} già nel DB, skip.")
                db.rollback()

        return True

    except Exception as e:
        print(f"[BEAT] Errore durante il polling: {e}")
        return False
    finally:
        db.close()