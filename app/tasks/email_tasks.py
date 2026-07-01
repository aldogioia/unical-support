from uuid import UUID
from app.core.celery_app import celery_app
from app.db.database import session_scope
from app.models.email import Email, EmailStatus
from app.ai.llm_factory import get_classifier_llm, get_responder_llm
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage, HumanMessage
from app.ai.prompts import get_classifier_system_prompt, get_responder_system_prompt
from app.listener.gmail_client import GmailClient

from app.ai.tools import (
    get_available_categories,
    assign_categories_and_route,
    search_knowledge_base,
    get_category_template,
    save_draft_response,
    escalate_to_human
)

@celery_app.task(bind=True, max_retries=3, name="app.tasks.email_tasks.classify_email_task")
def classify_email_task(self, email_id: UUID):
    try:
        with session_scope() as db:
            email = db.query(Email).filter(Email.id == email_id).first()
            if not email or email.status != EmailStatus.TO_CLASSIFY:
                return f"Email {email_id} ignorata (non trovata o stato non valido)."
            
            sender = email.sender
            subject = email.subject or ""
            body = email.body or ""
            gmail_id = email.gmail_id
        
        print(f"[WORKER-CLASSIFY] Avvio classificazione per email {email_id} (Tentativo {self.request.retries + 1}/4)...")
        
        llm = get_classifier_llm()
        tools = [get_available_categories, assign_categories_and_route]
        
        sys_msg = SystemMessage(content=get_classifier_system_prompt())
        user_msg = HumanMessage(content=f"L'email ID è {email_id}.\nMittente: {sender}\nOggetto: {subject}\nTesto:\n{body}")
        
        agent = create_react_agent(llm, tools)
        
        agent.invoke(
            {"messages": [sys_msg, user_msg]}, 
            config={"recursion_limit": 15}
        )
        
        # Validazione successo
        with session_scope() as db:
            check_email = db.query(Email).filter(Email.id == email_id).first()
            if check_email and check_email.status == EmailStatus.TO_CLASSIFY:
                raise Exception("L'agente non ha aggiornato lo stato. Forzatura retry.")
                
        print(f"[WORKER-CLASSIFY] Classificazione completata con successo per email {email_id}.")
        return True

    except Exception as e:
        print(f"[WORKER-CLASSIFY] Errore elaborazione email {email_id}: {e}")
        
        if self.request.retries >= self.max_retries:
            print(f"[WORKER-CLASSIFY] Limite retry raggiunto per email {email_id}. Spostamento in FAILED.")
            try:
                with session_scope() as db:
                    email = db.query(Email).filter(Email.id == email_id).first()
                    if email:
                        email.status = EmailStatus.FAILED
                
            except Exception as inner_e:
                print(f"Errore critico durante la marcatura di FAILED: {inner_e}")
            return False
        else:
            delay = 60 * (self.request.retries + 1)
            print(f"[WORKER-CLASSIFY] Ritento tra {delay} secondi...")
            raise self.retry(exc=e, countdown=delay)

@celery_app.task(bind=True, max_retries=3, name="app.tasks.email_tasks.respond_email_task")
def respond_email_task(self, email_id: UUID):
    try:
        with session_scope() as db:
            email = db.query(Email).filter(Email.id == email_id).first()
            if not email or email.status != EmailStatus.TO_RESPOND:
                return f"Email {email_id} ignorata (non trovata o stato non valido)."
            
            sender = email.sender
            subject = email.subject or ""
            body = email.body or ""
            gmail_id = email.gmail_id
            categories = ", ".join([c.name for c in email.categories])
        
        print(f"[WORKER-RESPOND] Avvio risposta email {email_id} (Tentativo {self.request.retries + 1}/4)...")
        
        llm = get_responder_llm()
        tools = [search_knowledge_base, get_category_template, save_draft_response, escalate_to_human]
        
        sys_msg = SystemMessage(content=get_responder_system_prompt())
        user_msg = HumanMessage(content=f"L'email ID è {email_id}.\nMittente: {sender}\nOggetto: {subject}\nCategorie Assegnate: {categories}\nTesto:\n{body}")
        
        agent = create_react_agent(llm, tools)
        
        agent.invoke(
            {"messages": [sys_msg, user_msg]}, 
            config={"recursion_limit": 15}
        )
        
        with session_scope() as db:
            check_email = db.query(Email).filter(Email.id == email_id).first()
            if check_email and check_email.status == EmailStatus.TO_RESPOND:
                raise Exception("L'agente non ha completato la risposta o l'escalation. Forzatura retry.")

        return True

    except Exception as e:
        print(f"[WORKER-RESPOND] Errore elaborazione email {email_id}: {e}")
        
        if self.request.retries >= self.max_retries:
            print(f"[WORKER-RESPOND] Limite retry raggiunto per email {email_id}. Spostamento in ESCALATED.")
            try:
                with session_scope() as db:
                    email = db.query(Email).filter(Email.id == email_id).first()
                    if email:
                        email.status = EmailStatus.ESCALATED
                        email.draft_response = f"Errore interno di sistema dopo 3 tentativi: {str(e)}"
                
            except Exception as inner_e:
                print(f"Errore critico durante la marcatura di ESCALATED: {inner_e}")
            return False
        else:
            delay = 60 * (self.request.retries + 1)
            print(f"[WORKER-RESPOND] Ritento tra {delay} secondi...")
            raise self.retry(exc=e, countdown=delay)