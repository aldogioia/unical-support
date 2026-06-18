import time
from app.core.celery_app import celery_app
from app.db.database import SessionLocal
from app.models.email import Email, EmailStatus

@celery_app.task(name="app.tasks.email_tasks.process_new_email")
def process_new_email(email_id: int):
    """
    Questo task viene eseguito in background dal Worker.
    In futuro (Modulo 4), qui dentro ci sarà LangChain.
    """

    db = SessionLocal()
    try:
        # 1. Recuperiamo l'email dal DB
        email = db.query(Email).filter(Email.id == email_id).first()
        if not email:
            return f"Errore: Email con ID {email_id} non trovata."

        # 2. Aggiorniamo lo stato per segnalare alla UI che ci stiamo lavorando
        email.status = EmailStatus.PROCESSING
        db.commit()

        print(f"[WORKER] Inizio elaborazione email ID {email_id} da {email.sender}...")

        # --- SIMULAZIONE LLM (LANGCHAIN ANDRA' QUI) ---
        time.sleep(5)
        # ----------------------------------------------

        # 3. L'IA ha finito. Salviamo la bozza e aggiorniamo lo stato
        email.generated_draft = f"Gentile studente,\n\nIn risposta alla sua richiesta: '{email.subject}'.\n\nCordiali saluti,\nSegreteria Unical"
        email.status = EmailStatus.DRAFT
        db.commit()

        print(f"[WORKER] Elaborazione completata per email ID {email_id}.")
        return f"Email {email_id} processata con successo. Bozza creata."

    except Exception as e:
        print(f"[WORKER] Errore durante l'elaborazione dell'email {email_id}: {e}")
        # In un sistema reale, qui potresti rimettere il task in coda (retry)
    finally:
        # È FONDAMENTALE chiudere sempre la sessione DB nel worker
        db.close()