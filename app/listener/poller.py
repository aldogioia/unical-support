import time
from app.listener.gmail_client import GmailClient
from app.db.database import SessionLocal
from app.schemas.email import EmailCreate
from app.services import email_service
from app.tasks.email_tasks import process_new_email
from sqlalchemy.exc import IntegrityError

def start_polling(interval_seconds=60):
    print("Inizializzazione Gmail Listener...")
    try:
        client = GmailClient()
        print("Autenticazione Gmail completata.")
    except Exception as e:
        print(f"Errore critico di autenticazione Gmail: {e}")
        return

    print(f"In attesa di nuove email... (Controllo ogni {interval_seconds} secondi)")
    
    while True:
        try:
            unread_emails = client.fetch_unread_emails()
            
            if unread_emails:
                print(f"📬 Trovate {len(unread_emails)} nuove email da elaborare.")
                
                # Apriamo una connessione al Database
                db = SessionLocal()
                try:
                    for email_data in unread_emails:
                        email_create = EmailCreate(
                            gmail_id=email_data["gmail_id"],
                            sender=email_data["sender"],
                            subject=email_data["subject"],
                            body=email_data["body"]
                        )
                        
                        try:
                            db_email = email_service.create_email(db=db, email=email_create)
                            print(f"   Salvata nel DB: {db_email.subject}")
                            
                            process_new_email.apply_async(args=[db_email.id], queue="emails_queue")
                            
                            client.mark_as_read(email_data["gmail_id"])
                            print(f"   Lanciata in coda e segnata come letta.")
                            
                        except IntegrityError:
                            print(f"   Email {email_data['gmail_id']} già presente nel DB. Salto.")
                            db.rollback()
                            
                finally:
                    db.close()
            
        except Exception as e:
            print(f"Errore durante il ciclo di polling: {e}")
        
        # Pausa prima del prossimo controllo
        time.sleep(interval_seconds)

if __name__ == "__main__":
    start_polling(interval_seconds=30)