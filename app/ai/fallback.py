"""
Ripiego per i modelli senza tool calling nativo.

Il percorso principale (agente LangGraph in app/tasks/email_tasks.py) resta invariato.
Questo modulo entra in gioco solo quando quel tentativo fallisce per un problema del
modello: server che rifiuta gli strumenti, chiamate malformate, agente che termina
senza chiamare lo strumento finale, ciclo di ragionamento esaurito.

In modalità di ripiego il codice esegue da sé i passi fissi (lettura delle categorie,
ricerca nella Knowledge Base) e al modello chiede soltanto un oggetto JSON. Le azioni
finali riusano le stesse funzioni dell'agente (_assign_categories, _save_draft_response,
_escalate_to_human), quindi stati, token di elaborazione e regole restano identici.

Gli errori di infrastruttura (server irraggiungibile, timeout, credenziali, modello
inesistente, database) NON attivano il ripiego: fallirebbe allo stesso modo, quindi
proseguono verso i retry di Celery come prima.
"""
import json
import re
import unicodedata

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.ai.llm_factory import get_classifier_llm, get_responder_llm
from app.ai.prompts import get_classifier_system_prompt, get_responder_system_prompt
from app.ai.rag import retrieve_context
from app.ai.tools import _assign_categories, _escalate_to_human, _save_draft_response
from app.core.ai_confidence import retrieval_confidence
from app.core.urls import normalize_reference_url
from app.db.database import session_scope
from app.models.category import Category
from app.models.email import Email, EmailStatus
from app.services.email_processing import can_write

# Tentativi per fase: il primo più al massimo due correzioni con l'errore restituito al modello.
MAX_ATTEMPTS = 3
PASSAGE_SEPARATOR = '\n\n---\n\n'
QUERY_MAX_CHARS = 2000
SAVED_OK = 'Bozza salvata con successo.'

# Errori per cui il ripiego non servirebbe: cambiare modalità non cambia l'esito.
_INFRASTRUCTURE_ERRORS = {
    # client OpenAI-compatibili (Ollama, LM Studio, vLLM...) e Groq
    'APIConnectionError', 'APITimeoutError', 'AuthenticationError', 'PermissionDeniedError',
    'NotFoundError', 'RateLimitError',
    # Google Generative AI
    'GoogleAuthenticationError', 'GooglePermissionDeniedError', 'GoogleModelNotFoundError',
    'GoogleRateLimitError', 'ModelAuthenticationError', 'ModelPermissionDeniedError',
    'ModelNotFoundError', 'ModelRateLimitError', 'ServiceUnavailable', 'DeadlineExceeded',
    'ResourceExhausted', 'Unauthenticated', 'PermissionDenied',
    # trasporto HTTP
    'TransportError', 'TimeoutException', 'ConnectError', 'ConnectTimeout', 'ReadTimeout',
    'WriteTimeout', 'PoolTimeout',
    # Celery: limiti di tempo e retry
    'SoftTimeLimitExceeded', 'TimeLimitExceeded', 'Retry',
}
_INFRASTRUCTURE_MODULES = ('sqlalchemy', 'psycopg', 'redis', 'kombu')

CLASSIFIER_FALLBACK_RULES = """

## MODALITÀ SENZA STRUMENTI (prevale sulle istruzioni precedenti)
In questa modalità non hai strumenti a disposizione: ignora ogni riferimento a
`get_available_categories` e `assign_categories_and_route`.
L'elenco ufficiale delle categorie è già nel messaggio, sotto "CATEGORIE DISPONIBILI".
Rispondi con UN SOLO oggetto JSON valido e nient'altro (niente testo prima o dopo), nel formato:
{"category_names": ["Nome categoria esatto", "Altro nome esatto"]}
Valgono tutte le altre regole: analisi multi-intento, nomi copiati lettera per lettera
dall'elenco, uso di "Generale" o "Altro" quando nessuna categoria specifica si applica."""

RESPONDER_FALLBACK_RULES = """

MODALITÀ SENZA STRUMENTI (prevale sulle istruzioni precedenti)
In questa modalità non hai strumenti: la ricerca nella Knowledge Base è già stata eseguita
e i frammenti sono nel messaggio, sotto "FRAMMENTI DELLA KNOWLEDGE BASE". Ignora le
istruzioni che chiedono di chiamare search_knowledge_base, save_draft_response o
escalate_to_human e sostituiscile così:
- al posto di save_draft_response rispondi con
  {"action": "draft", "draft_text": "...", "response_language": "it", "ai_disclaimer": null}
- al posto di escalate_to_human rispondi con
  {"action": "escalate", "reason": "..."}
Rispondi con UN SOLO oggetto JSON valido e nient'altro: niente testo prima o dopo.
Dentro draft_text scrivi i ritorni a capo come \\n. Usa ai_disclaimer solo per lingue
diverse da it/en/es/fr/de/pt, altrimenti null.
Tutte le altre regole (lingua, tono, formato, fonti e link, escalation) restano valide."""


class FallbackError(RuntimeError):
    """Il ripiego non ha ottenuto dal modello un risultato valido."""


# --------------------------------------------------------------------------- ingresso

def is_model_failure(exc: BaseException) -> bool:
    """True se l'errore dipende dal modello e non dall'infrastruttura."""
    seen = set()
    current = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, (ConnectionError, TimeoutError)):
            return False
        for cls in type(current).__mro__:
            if cls.__name__ in _INFRASTRUCTURE_ERRORS or cls.__module__.startswith(_INFRASTRUCTURE_MODULES):
                return False
        current = current.__cause__ or current.__context__
    return True


def attempt_fallback(exc, email_id, stage, token, generation):
    """
    Punto di aggancio per email_tasks._process. Non solleva mai eccezioni.
    Restituisce (gestita, eccezione): se gestita è True l'email è stata portata avanti
    dal ripiego; altrimenti l'eccezione originale, da passare ai retry come prima.
    L'eventuale errore del ripiego finisce nei log del worker con il prefisso [FALLBACK].
    """
    if not is_model_failure(exc):
        return False, exc
    print(f"[FALLBACK] Email {email_id}, fase {stage}: agente fallito ({type(exc).__name__}: {exc}). "
          f"Avvio la modalità senza strumenti.")
    try:
        handled = run_fallback(email_id, stage, token, generation)
    except Exception as fallback_exc:
        print(f"[FALLBACK] Email {email_id}, fase {stage}: anche il ripiego è fallito "
              f"({type(fallback_exc).__name__}: {fallback_exc}).")
        return False, exc
    if handled:
        print(f"[FALLBACK] Email {email_id}, fase {stage}: completata in modalità senza strumenti.")
    return bool(handled), exc


def run_fallback(email_id, stage, token, generation):
    """None se l'email non è più nostra (stato cambiato o token scaduto), True se completata."""
    status = EmailStatus.TO_CLASSIFY if stage == 'classify' else EmailStatus.TO_RESPOND
    with session_scope() as db:
        email = db.query(Email).filter(Email.id == email_id).populate_existing().first()
        if not can_write(email, status, token):
            return None
        snapshot = {
            'sender': email.sender,
            'subject': email.subject or '',
            'body': email.body or '',
            'categories': [c.name for c in email.categories],
        }
        catalog = [(c.name, c.description or '') for c in db.query(Category).all()] if stage == 'classify' else []
    if stage == 'classify':
        return _classify(email_id, token, snapshot, catalog)
    return _respond(email_id, token, generation, snapshot)


# --------------------------------------------------------------------------- classificazione

def _classify(email_id, token, email, catalog):
    if not catalog:
        _assign_categories(email_id, [], token)
        return True
    listing = '\n'.join(f'- {name}: {description}' for name, description in catalog)
    by_key = {_name_key(name): name for name, _ in catalog}
    messages = [
        SystemMessage(content=get_classifier_system_prompt() + CLASSIFIER_FALLBACK_RULES),
        HumanMessage(content=(
            f"Email ID: {email_id}\nMittente: {email['sender']}\n"
            f"Oggetto (non determina la lingua): {email['subject']}\n"
            f"CATEGORIE DISPONIBILI:\n{listing}\n\nCORPO DEL MESSAGGIO:\n{email['body']}"
        )),
    ]
    llm = get_classifier_llm()
    problem = None
    for _ in range(MAX_ATTEMPTS):
        text = _ask(llm, messages)
        data, problem = _parse_json(text)
        if data is not None:
            raw = data.get('category_names', data.get('categories'))
            names = _as_name_list(raw)
            matched = []
            for name in names:
                canonical = by_key.get(_name_key(name))
                if canonical and canonical not in matched:
                    matched.append(canonical)
            if matched:
                _assign_categories(email_id, matched, token)
                return True
            problem = ('Nessuna delle categorie indicate esiste. Usa solo nomi copiati esattamente '
                       'da questo elenco: ' + ', '.join(by_key.values()))
        messages += [AIMessage(content=text), HumanMessage(content=_correction(problem))]
    raise FallbackError(f'Classificazione senza strumenti non riuscita: {problem}')


# --------------------------------------------------------------------------- risposta

def _respond(email_id, token, generation, email):
    query = f"{email['subject']}\n{email['body']}".strip()[:QUERY_MAX_CHARS]
    names = email['categories']
    context = retrieve_context(query=query, k=4, category_names=names or None)
    if not context and names:
        # Come chiede il prompt del responder: se il filtro non trova nulla, si ripete senza filtro.
        context = retrieve_context(query=query, k=4, category_names=None)
    sources = _collect_sources(context)
    if not context or not sources:
        _escalate_to_human(email_id, 'Modalità senza strumenti: nessun frammento pertinente trovato '
                                     'nella Knowledge Base per questa richiesta.', token)
        return True

    messages = [
        SystemMessage(content=get_responder_system_prompt() + RESPONDER_FALLBACK_RULES),
        HumanMessage(content=(
            f"Email ID: {email_id}\nMittente: {email['sender']}\n"
            f"Oggetto (non determina la lingua): {email['subject']}\n"
            f"Categorie assegnate: {', '.join(names)}\nCORPO DEL MESSAGGIO:\n{email['body']}\n\n"
            f"FRAMMENTI DELLA KNOWLEDGE BASE:\n{context}"
        )),
    ]
    llm = get_responder_llm()
    problem = None
    for _ in range(MAX_ATTEMPTS):
        text = _ask(llm, messages)
        data, problem = _parse_json(text)
        if data is not None:
            action = str(data.get('action') or '').strip().lower()
            if action == 'escalate':
                reason = str(data.get('reason') or '').strip() or 'Richiesta gestione manuale dal modello.'
                _escalate_to_human(email_id, reason, token)
                return True
            draft = data.get('draft_text')
            if action in ('draft', '') and isinstance(draft, str) and draft.strip():
                problem = _draft_problem(draft, sources)
                if problem is None:
                    result = _save_draft_response(email_id, draft, _optional_str(data.get('response_language')),
                                                  _optional_str(data.get('ai_disclaimer')), token)
                    if result == SAVED_OK:
                        _store_confidence(email_id, generation, context)
                        return True
                    if result.startswith('Elaborazione scaduta'):
                        return True
                    problem = result
            elif problem is None:
                problem = 'Il JSON deve avere "action" uguale a "draft" (con "draft_text" non vuoto) oppure "escalate" (con "reason").'
        messages += [AIMessage(content=text), HumanMessage(content=_correction(problem))]
    raise FallbackError(f'Risposta senza strumenti non riuscita: {problem}')


def _collect_sources(context):
    """Stessa estrazione di nome fonte e link che fa lo strumento di ricerca dell'agente."""
    sources = {}
    for passage in (context or '').split(PASSAGE_SEPARATOR):
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
    return sources


def _draft_problem(draft_text, sources):
    """Stessi controlli su link e citazioni che l'agente applica prima di salvare la bozza."""
    allowed = set().union(*sources.values()) if sources else set()
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
            return 'Non citare il nome di una fonte senza il suo link valido. Ometti la citazione priva di URL e riprova.'
    return None


def _store_confidence(email_id, generation, context):
    """Calcola la confidenza come fa il percorso dell'agente, a partire dagli stessi frammenti."""
    confidence = retrieval_confidence([
        ToolMessage(content=context, name='search_knowledge_base', tool_call_id='fallback'),
    ])
    with session_scope() as db:
        email = db.query(Email).filter(Email.id == email_id).populate_existing().with_for_update().first()
        if (email and email.status == EmailStatus.DRAFT and not email.manually_edited
                and (generation is None or email.processing_generation == generation)):
            email.ai_confidence = confidence


# --------------------------------------------------------------------------- utilità

def _ask(llm, messages):
    return _response_text(llm.invoke(messages))


def _response_text(response):
    content = getattr(response, 'content', response)
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and part.get('type', 'text') == 'text':
                parts.append(str(part.get('text', '')))
        content = ''.join(parts)
    text = str(content or '')
    # Modelli con ragionamento esplicito (es. <think>...</think>): conta solo ciò che segue.
    if '</think>' in text:
        text = text.rsplit('</think>', 1)[1]
    return text.strip()


def _parse_json(text):
    """Estrae il primo oggetto JSON dal testo. Restituisce (dati, None) oppure (None, problema)."""
    decoder = json.JSONDecoder(strict=False)
    candidates = [text]
    candidates += re.findall(r'```(?:json)?\s*(.*?)```', text, flags=re.DOTALL | re.IGNORECASE)
    for candidate in candidates:
        try:
            data = decoder.decode(candidate.strip())
            if isinstance(data, dict):
                return data, None
        except ValueError:
            pass
    for start in (i for i, ch in enumerate(text) if ch == '{'):
        try:
            data, _ = decoder.raw_decode(text, start)
        except ValueError:
            continue
        if isinstance(data, dict):
            return data, None
    if not text:
        return None, 'La risposta era vuota.'
    return None, 'La risposta non conteneva un oggetto JSON valido.'


def _correction(problem):
    return (f'{problem}\nRispondi di nuovo con UN SOLO oggetto JSON valido nel formato richiesto, '
            f'senza altro testo.')


def _as_name_list(raw):
    if isinstance(raw, str):
        raw = [part for part in re.split(r'[,;\n]', raw)]
    if not isinstance(raw, list):
        return []
    return [item.strip() for item in raw if isinstance(item, str) and item.strip()]


def _name_key(name):
    """Confronto tollerante: maiuscole, accenti, spazi e virgolette non contano."""
    text = unicodedata.normalize('NFKD', str(name))
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r'\s+', ' ', text).strip().strip('"\'`“”«»').strip()
    return text.casefold()


def _optional_str(value):
    if value is None:
        return None
    value = str(value).strip()
    return value if value and value.lower() not in ('null', 'none') else None
