from langchain_core.tools import tool
from app.db.database import session_scope
from app.models.category import Category
from app.models.email import Email, EmailStatus
from app.core.celery_app import celery_app
from app.ai.rag import retrieve_context

@tool
def get_available_categories() -> str:
    """
    Legge e restituisce la lista delle categorie disponibili (nome e descrizione).
    Usalo per capire quali categorie possono essere assegnate all'email.
    """
    with session_scope() as db:
        categories = db.query(Category).all()
        if not categories:
            return "Nessuna categoria disponibile."
        return "\n".join([f"- {c.name}: {c.description}" for c in categories])

@tool
def assign_categories_and_route(email_id: int, category_names: list[str]) -> str:
    """
    Assegna le categorie indicate all'email e la invia all'agente risponditore.
    Obbligatorio chiamare questo tool alla fine del processo di classificazione.
    """
    with session_scope() as db:
        email = db.query(Email).filter(Email.id == email_id).first()
        if not email:
            return f"Email {email_id} non trovata."
        
        assigned = []
        all_categories = db.query(Category).all()
        for name in category_names:
            matched = next((c for c in all_categories if c.name.lower() == name.lower()), None)
            if matched and matched not in email.categories:
                email.categories.append(matched)
                assigned.append(matched.name)
        
        email.status = EmailStatus.TO_RESPOND
    
    celery_app.send_task(
        "app.tasks.email_tasks.respond_email_task",
        args=[email_id],
        queue="respond_queue"
    )
    return f"Categorie {assigned} assegnate. Email passata al risponditore."

@tool
def search_knowledge_base(query: str, category_name: str = None) -> str:
    """
    Esegue una ricerca nella base di conoscenza vettoriale (RAG) per trovare
    informazioni pertinenti per rispondere alla richiesta dell'utente.
    """
    return retrieve_context(query=query, k=4, category_name=category_name)

@tool
def get_category_template(category_name: str) -> str:
    """
    Recupera il template di risposta pre-approvato per una data categoria, se esiste.
    """
    with session_scope() as db:
        category = db.query(Category).filter(Category.name.ilike(category_name)).first()
        if not category:
            return f"Categoria {category_name} non trovata."
        if not category.templates:
            return f"Nessun template disponibile per {category_name}."
        
        return category.templates[0].body_template

@tool
def save_draft_response(email_id: int, draft_text: str) -> str:
    """
    Salva la bozza finale sull'email indicata.
    Obbligatorio chiamare questo tool alla fine del processo di risposta se è stata creata una bozza.
    """
    with session_scope() as db:
        email = db.query(Email).filter(Email.id == email_id).first()
        if not email:
            return f"Email {email_id} non trovata."
        
        email.generated_draft = draft_text
        email.status = EmailStatus.DRAFT
        return "Bozza salvata con successo."

@tool
def escalate_to_human(email_id: int, reason: str) -> str:
    """
    Usa questo tool se non trovi informazioni sufficienti per rispondere
    e ritieni che l'email debba essere gestita da un operatore umano.
    """
    with session_scope() as db:
        email = db.query(Email).filter(Email.id == email_id).first()
        if not email:
            return f"Email {email_id} non trovata."
        
        email.status = EmailStatus.ESCALATED
        email.generated_draft = f"ESCALATION REQUIRED:\n{reason}"
        return "Email marcata per escalation."
