from app.core.celery_app import celery_app
from app.db.database import session_scope
from app.models.email import Email, EmailStatus
from app.ai.llm_factory import get_classifier_llm, get_responder_llm
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage, HumanMessage
from app.ai.prompts import get_classifier_system_prompt, get_responder_system_prompt

from app.ai.tools import (
    get_available_categories,
    assign_categories_and_route,
    search_knowledge_base,
    get_category_template,
    save_draft_response,
    escalate_to_human
)

@celery_app.task(name="app.tasks.email_tasks.classify_email_task")
def classify_email_task(email_id: int):
    try:
        with session_scope() as db:
            email = db.query(Email).filter(Email.id == email_id).first()
            if not email or email.status != EmailStatus.TO_CLASSIFY:
                return f"Email {email_id} non trovata o stato non valido."
            
            sender = email.sender
            subject = email.subject or ""
            body = email.body or ""
        
        print(f"[WORKER-CLASSIFY] Avvio classificazione per email {email_id}...")
        
        llm = get_classifier_llm()
        tools = [get_available_categories, assign_categories_and_route]
        
        sys_msg = SystemMessage(content=get_classifier_system_prompt())
        user_msg = HumanMessage(content=f"L'email ID è {email_id}.\nMittente: {sender}\nOggetto: {subject}\nTesto:\n{body}")
        
        agent = create_react_agent(llm, tools)
        
        agent.invoke(
            {"messages": [sys_msg, user_msg]}, 
            config={"recursion_limit": 25}
        )
        
        with session_scope() as db:
            check_email = db.query(Email).filter(Email.id == email_id).first()
            if check_email and check_email.status == EmailStatus.TO_CLASSIFY:
                print(f"[WORKER-CLASSIFY] L'agente non ha aggiornato lo stato per l'email {email_id}. Forzatura a FAILED.")
                check_email.status = EmailStatus.FAILED
                return False
                
        print(f"[WORKER-CLASSIFY] Classificazione completata per email {email_id}.")
        return True

    except Exception as e:
        print(f"[WORKER-CLASSIFY] Errore: {e}")
        try:
            with session_scope() as db:
                email = db.query(Email).filter(Email.id == email_id).first()
                if email and email.status == EmailStatus.TO_CLASSIFY:
                    email.status = EmailStatus.FAILED
        except Exception:
            pass
        return False

@celery_app.task(name="app.tasks.email_tasks.respond_email_task")
def respond_email_task(email_id: int):
    try:
        with session_scope() as db:
            email = db.query(Email).filter(Email.id == email_id).first()
            if not email or email.status != EmailStatus.TO_RESPOND:
                return f"Email {email_id} non trovata o stato non valido."
            
            sender = email.sender
            subject = email.subject or ""
            body = email.body or ""
            categories = ", ".join([c.name for c in email.categories])
        
        print(f"[WORKER-RESPOND] Avvio risposta per email {email_id} (Categorie: {categories})...")
        
        llm = get_responder_llm()
        tools = [search_knowledge_base, get_category_template, save_draft_response, escalate_to_human]
        
        sys_msg = SystemMessage(content=get_responder_system_prompt())
        user_msg = HumanMessage(content=f"L'email ID è {email_id}.\nMittente: {sender}\nOggetto: {subject}\nCategorie Assegnate: {categories}\nTesto:\n{body}")
        
        agent = create_react_agent(llm, tools)
        agent.invoke(
            {"messages": [sys_msg, user_msg]}, 
            config={"recursion_limit": 40}
        )
        
        with session_scope() as db:
            check_email = db.query(Email).filter(Email.id == email_id).first()
            if check_email and check_email.status == EmailStatus.TO_RESPOND:
                print(f"[WORKER-RESPOND] L'agente ha mancato l'obiettivo per l'email {email_id}. Forzatura a ESCALATED.")
                check_email.status = EmailStatus.ESCALATED
                check_email.draft_response = "Il sistema AI non è riuscito a formulare una risposta e ha ignorato i tool. Richiesto intervento umano."
                return False

        print(f"[WORKER-RESPOND] Risposta completata per email {email_id}.")
        return True

    except Exception as e:
        print(f"[WORKER-RESPOND] Errore: {e}")
        try:
            with session_scope() as db:
                email = db.query(Email).filter(Email.id == email_id).first()
                if email and email.status == EmailStatus.TO_RESPOND:
                    email.status = EmailStatus.ESCALATED
                    email.draft_response = f"Errore interno di sistema: {str(e)}"
        except Exception:
            pass
        return False