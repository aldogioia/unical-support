from app.core.celery_app import celery_app
from app.db.database import SessionLocal

from app.models import *
from app.models.email import Email, EmailStatus
from app.models.category import Category
from app.ai.graph import app_graph, EmailProcessingState

@celery_app.task(name="app.tasks.email_tasks.process_new_email")
def process_new_email(email_id: int):
    db = SessionLocal()
    try:
        db_email = db.query(Email).filter(Email.id == email_id).first()
        if not db_email:
            return f"Errore: Email {email_id} non trovata."

        db_email.status = EmailStatus.PROCESSING
        db.commit()
        print(f"[WORKER] Avvio Agente LangGraph per email {email_id}...")

        all_categories = db.query(Category).all()
        category_names = [cat.name for cat in all_categories]

        if not category_names:
            db_email.status = EmailStatus.IGNORED
            db.commit()
            return "Nessuna categoria nel sistema per classificare."

        initial_state = EmailProcessingState(
            email_id=db_email.id,
            sender=db_email.sender,
            subject=db_email.subject or "",
            body=db_email.body or "",
            available_categories=category_names,
            predicted_categories_json=None,
            context_retrieved=None,
            generated_response_json=None,
            final_draft=None,
            error=None,
            retry_count=0
        )

        final_state = app_graph.invoke(initial_state)

        if final_state.get("error"):
            print(f"[WORKER] Fallimento definitivo: {final_state['error']}")
            db_email.status = EmailStatus.FAILED
            db.commit()
            return False

        bozza = final_state.get("final_draft")
        if bozza:
            db_email.generated_draft = bozza
            db_email.status = EmailStatus.DRAFT

            predicted_json = final_state.get("predicted_categories_json", [])
            if isinstance(predicted_json, list):
                for item in predicted_json:
                    for cat_info in item.get("categories", []):
                        matched = next((c for c in all_categories if c.name.lower() == cat_info.get("name", "").lower()), None)
                        if matched and matched not in db_email.categories:
                            db_email.categories.append(matched)

            db.commit()
            print(f"[WORKER] Elaborazione completata! Bozza creata.")
            return True
        else:
            print("[WORKER] LangGraph non ha prodotto alcuna bozza.")
            db_email.status = EmailStatus.UNREAD
            db.commit()
            return False

    except Exception as e:
        print(f"[WORKER] Errore critico: {e}")
        db.rollback()
        return False
    finally:
        db.close()
