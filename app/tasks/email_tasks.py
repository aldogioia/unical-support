from app.core.celery_app import celery_app
from app.db.database import SessionLocal
from app.models.email import Email, EmailStatus
from app.models.category import Category
from app.ai.graph import app_graph, EmailProcessingState

@celery_app.task(name="app.tasks.email_tasks.process_new_email")
def process_new_email(email_id: int):
    db = SessionLocal()
    try:
        email = db.query(Email).filter(Email.id == email_id).first()
        if not email:
            return f"Errore: Email {email_id} non trovata."

        email.status = EmailStatus.PROCESSING
        db.commit()
        print(f"[WORKER] Avvio Agente LangGraph per email {email_id}...")

        all_categories = db.query(Category).all()
        category_names = [cat.name for cat in all_categories]
        
        if not category_names:
            email.status = EmailStatus.IGNORED
            db.commit()
            return "Nessuna categoria nel sistema per classificare."

        # Inizializziamo lo stato per LangGraph
        initial_state = EmailProcessingState(
            email_id=email.id,
            sender=email.sender,
            subject=email.subject or "",
            body=email.body or "",
            available_categories=category_names,
            predicted_categories_json=None,
            context_retrieved=None,
            generated_response_json=None,
            final_draft=None,
            error=None,
            retry_count=0
        )

        # INVOCA IL GRAFO: Tutto il ragionamento multi-intento avviene qui
        final_state = app_graph.invoke(initial_state)

        # Gestione fallimenti definitivi
        if final_state.get("error"):
            print(f"[WORKER] Fallimento definitivo LangGraph: {final_state['error']}")
            # Inserisci logica di escalation qui in futuro
            email.status = EmailStatus.UNREAD
            db.commit()
            return False

        # Salvataggio successo
        bozza = final_state.get("final_draft")
        if bozza:
            email.generated_draft = bozza
            email.status = EmailStatus.DRAFT
            
            # Salviamo le categorie multiple associate a questa email
            predicted_json = final_state.get("predicted_categories_json", [])
            if isinstance(predicted_json, list):
                for item in predicted_json:
                    for cat_info in item.get("categories", []):
                        matched = next((c for c in all_categories if c.name.lower() == cat_info.get("name", "").lower()), None)
                        if matched and matched not in email.categories:
                            email.categories.append(matched)

            db.commit()
            print(f"[WORKER] Elaborazione completata! Bozza creata con successo.")
            return True
        else:
            print("[WORKER] Errore: LangGraph non ha prodotto alcuna bozza.")
            email.status = EmailStatus.UNREAD
            db.commit()
            return False

    except Exception as e:
        print(f"[WORKER] Errore critico nel Worker: {e}")
        db.rollback()
        return False
    finally:
        db.close()