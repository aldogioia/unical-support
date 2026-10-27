from uuid import UUID
# pyrefly: ignore [missing-import]
from langchain_core.tools import tool
from app.db.database import session_scope
from app.models.category import Category
from app.models.email import Email, EmailStatus
from app.services.email_processing import can_write, release_processing, enqueue_processing
from app.ai.rag import retrieve_context
from app.core.email_formatting import prepare_draft, get_ai_disclaimer, response_language_for

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

def _assign_categories(email_id: UUID, category_names: list[str], token=None) -> str:
    """
    Assegna le categorie indicate all'email e la invia all'agente risponditore.
    Obbligatorio chiamare questo tool alla fine del processo di classificazione.
    """
    with session_scope() as db:
        email = db.query(Email).filter(Email.id == email_id).populate_existing().with_for_update().first()
        if not can_write(email, EmailStatus.TO_CLASSIFY, token):
            return "Elaborazione scaduta o email già gestita: nessuna modifica applicata."
        
        # Regole di combinazione delle categorie:
        # 1. Se la lista contiene "Altro", tieni solo quello
        # 2. Se contiene "Generale" e almeno un'altra specifica, scarta "Generale"
        names_lower = [n.lower() for n in category_names]
        if any(n == "altro" for n in names_lower):
            category_names = [n for n in category_names if n.lower() == "altro"][:1]
        elif any(n == "generale" for n in names_lower) and len(category_names) > 1:
            category_names = [n for n in category_names if n.lower() != "generale"]

        assigned = []
        email.categories = []
        all_categories = db.query(Category).all()
        for name in category_names:
            matched = next((c for c in all_categories if c.name.lower() == name.lower()), None)
            if matched and matched not in email.categories:
                email.categories.append(matched)
                assigned.append(matched.name)
        
        email.status = EmailStatus.TO_RESPOND
        email.failure_stage = None
        generation = email.processing_generation
        release_processing(email)
    try:
        enqueue_processing(email_id, 'respond', generation)
    except Exception:
        with session_scope() as db:
            email = db.query(Email).filter(Email.id == email_id).populate_existing().with_for_update().first()
            if email and email.status == EmailStatus.TO_RESPOND and email.processing_generation == generation and not email.processing_token:
                email.status = EmailStatus.FAILED
                email.failure_stage = 'respond'
        raise
    return f"Categorie {assigned} assegnate. Email passata al risponditore."

@tool
def search_knowledge_base(query: str, category_names: list[str] | None = None) -> str:
    """
    Esegue una ricerca nella base di conoscenza vettoriale (RAG) per trovare
    informazioni pertinenti per rispondere alla richiesta dell'utente.
    `category_names` (opzionale) limita la ricerca ai documenti associati ad ALMENO UNA
    delle categorie indicate (un documento può appartenere a più categorie).
    Passa le categorie assegnate all'email; se omesso, cerca in tutta la base di conoscenza.
    """
    return retrieve_context(query=query, k=4, category_names=category_names)

def _save_draft_response(email_id: UUID, draft_text: str, response_language: str | None = None, ai_disclaimer: str | None = None, token=None) -> str:
    """
    Salva la bozza finale sull'email indicata.
    Passa response_language con il codice ISO della lingua rilevata (it, en, es, ecc.).
    Il sistema inserisce separatamente la nota IA supervisionata al momento dell'invio.
    Non includere disclaimer in draft_text. Per lingue diverse da
    it/en/es/fr/de/pt, passa anche ai_disclaimer: la traduzione nella lingua della
    risposta di "Questa risposta è stata preparata con l'ausilio dell'intelligenza
    artificiale e revisionata da un operatore prima dell'invio. L'IA può commettere
    errori: verifica le informazioni nelle fonti indicate."
    Obbligatorio chiamare questo tool alla fine del processo di risposta.
    """
    try:
        formatted_draft = prepare_draft(draft_text, response_language, ai_disclaimer)
        language = response_language_for(response_language)
        disclaimer = get_ai_disclaimer(language, ai_disclaimer)
    except ValueError as exc:
        return str(exc)
    with session_scope() as db:
        email = db.query(Email).filter(Email.id == email_id).populate_existing().with_for_update().first()
        if not can_write(email, EmailStatus.TO_RESPOND, token):
            return "Elaborazione scaduta o bozza revisionata: nessuna modifica applicata."
        
        email.generated_draft = formatted_draft
        email.response_language = language
        email.ai_disclaimer = disclaimer
        email.status = EmailStatus.DRAFT
        email.draft_revision += 1
        email.failure_stage = None
        release_processing(email)
        return "Bozza salvata con successo."

def _escalate_to_human(email_id: UUID, reason: str, token=None) -> str:
    """
    Usa questo tool se non trovi informazioni sufficienti per rispondere
    e ritieni che l'email debba essere gestita da un operatore umano.
    """
    with session_scope() as db:
        email = db.query(Email).filter(Email.id == email_id).populate_existing().with_for_update().first()
        if not can_write(email, EmailStatus.TO_RESPOND, token):
            return "Elaborazione scaduta o bozza revisionata: nessuna modifica applicata."
        
        email.status = EmailStatus.ESCALATED
        email.draft_revision += 1
        release_processing(email)
        email.generated_draft = f"GESTIONE MANUALE RICHIESTA:\n{reason}"
        return "Email marcata per escalation."


# The model never receives the processing token. Each production agent gets bound tools.
@tool
def assign_categories_and_route(email_id: UUID, category_names: list[str]) -> str:
    """Assegna categorie e passa al risponditore. Chiamata finale obbligatoria della classificazione."""
    return _assign_categories(email_id, category_names)


@tool
def save_draft_response(email_id: UUID, draft_text: str, response_language: str | None = None, ai_disclaimer: str | None = None) -> str:
    """Salva la bozza nella sola lingua iniziale del corpo ricevuto. Passa response_language ISO e, per lingue fuori it/en/es/fr/de/pt, ai_disclaimer tradotto. Non includere disclaimer in draft_text."""
    return _save_draft_response(email_id, draft_text, response_language, ai_disclaimer)


@tool
def escalate_to_human(email_id: UUID, reason: str) -> str:
    """Richiedi gestione manuale quando nessuna domanda trova risposta nelle fonti."""
    return _escalate_to_human(email_id, reason)


def processing_tools(identifier, token, stage):
    import json
    import re
    from app.core.urls import normalize_reference_url
    target = str(identifier)
    sources = {}
    searched = False

    @tool('search_knowledge_base', description=search_knowledge_base.description)
    def search(query: str, category_names: list[str] | None = None) -> str:
        nonlocal searched
        searched = True
        context = retrieve_context(query=query, k=4, category_names=category_names)
        for passage in context.split('\n\n---\n\n'):
            try:
                source = json.loads(passage)
                name = source.get('source_name')
                try:
                    url = normalize_reference_url(source.get('reference_url'))
                except (ValueError, TypeError, AttributeError):
                    url = None
                if name:
                    sources.setdefault(name, set())
                    if url:
                        sources[name].add(url)
            except (ValueError, TypeError, AttributeError):
                continue
        return context
    def valid(email_id):
        return str(email_id) == target

    @tool('assign_categories_and_route', description=assign_categories_and_route.description)
    def assign(email_id: UUID, category_names: list[str]) -> str:
        return _assign_categories(email_id, category_names, token) if valid(email_id) else 'Email non autorizzata per questa elaborazione.'

    @tool('save_draft_response', description=save_draft_response.description)
    def save(email_id: UUID, draft_text: str, response_language: str | None = None, ai_disclaimer: str | None = None) -> str:
        if not valid(email_id):
            return 'Email non autorizzata per questa elaborazione.'
        if not searched or not sources:
            return 'Consulta prima la Knowledge Base. Senza frammenti documentali utili richiedi gestione manuale.'
        allowed = set().union(*sources.values())
        urls = set()
        for raw in re.findall(r'https?://[^\s<>]+', draft_text):
            url = raw.rstrip('.,;:!?')
            for opening, closing in [('(', ')'), ('[', ']'), ('{', '}')]:
                while url.endswith(closing) and url.count(closing) > url.count(opening):
                    url = url[:-1]
            urls.add(url)
        if urls - allowed:
            return 'Link non presente tra i reference_url recuperati: correggi la bozza usando soltanto link validi forniti dalla ricerca.'
        for name, links in sources.items():
            if name != 'Documento' and name in draft_text and not any(url in draft_text for url in links):
                return 'Non citare il nome di una fonte senza il suo link valido. Ometti la citazione priva di URL e riprova a salvare.'
        return _save_draft_response(email_id, draft_text, response_language, ai_disclaimer, token)

    @tool('escalate_to_human', description=escalate_to_human.description)
    def escalate(email_id: UUID, reason: str) -> str:
        return _escalate_to_human(email_id, reason, token) if valid(email_id) else 'Email non autorizzata per questa elaborazione.'

    return [get_available_categories, assign] if stage == 'classify' else [search, save, escalate]
