from uuid import UUID
from app.core.celery_app import celery_app
from app.db.database import session_scope
from app.models.email import Email, EmailStatus
from app.services.email_processing import claim_processing, can_write, release_processing


def _process(task, email_id, stage, generation=None):
    from app.ai.llm_factory import get_classifier_llm, get_responder_llm
    from langgraph.prebuilt import create_react_agent
    from langchain_core.messages import SystemMessage, HumanMessage
    from app.ai.prompts import get_classifier_system_prompt, get_responder_system_prompt
    from app.ai.tools import processing_tools
    status = EmailStatus.TO_CLASSIFY if stage == 'classify' else EmailStatus.TO_RESPOND
    with session_scope() as db:
        email = claim_processing(db, email_id, status, generation)
        if email is None:
            return 'Email già gestita, elaborazione attiva o generazione scaduta: ignorata.'
        token, generation = email.processing_token, email.processing_generation
        sender, subject, body = email.sender, email.subject or '', email.body or ''
        categories = ', '.join(c.name for c in email.categories)
        if stage == 'respond':
            email.ai_confidence = None
    try:
        llm = get_classifier_llm() if stage == 'classify' else get_responder_llm()
        prompt = get_classifier_system_prompt() if stage == 'classify' else get_responder_system_prompt()
        agent = create_react_agent(llm, processing_tools(email_id, token, stage))
        result = agent.invoke({'messages': [SystemMessage(content=prompt), HumanMessage(content=(
            f'Email ID: {email_id}\nMittente: {sender}\nOggetto (non determina la lingua): {subject}\n'
            f'Categorie assegnate: {categories}\nCORPO DEL MESSAGGIO:\n{body}'
        ))]}, config={'recursion_limit': 15})
        with session_scope() as db:
            email = db.query(Email).filter(Email.id == email_id).populate_existing().with_for_update().first()
            if not email or email.processing_generation != generation or email.manually_edited:
                return False
            if stage == 'respond' and email.status == EmailStatus.DRAFT:
                from app.core.ai_confidence import retrieval_confidence
                email.ai_confidence = retrieval_confidence(result.get('messages', []))
            elif can_write(email, status, token):
                raise RuntimeError('L’agente non ha completato il salvataggio o la transizione di stato.')
        return True
    except Exception as exc:
        with session_scope() as db:
            email = db.query(Email).filter(Email.id == email_id).populate_existing().with_for_update().first()
            if not can_write(email, status, token):
                return False
            release_processing(email)
            if task.request.retries >= task.max_retries:
                email.status = EmailStatus.FAILED
                email.failure_stage = stage
                # Preserve the last draft, including operator text, on infrastructure failures.
                return False
        raise task.retry(exc=exc, countdown=60 * (task.request.retries + 1), kwargs={'generation': generation})


@celery_app.task(bind=True, max_retries=3, name='app.tasks.email_tasks.classify_email_task', soft_time_limit=540, time_limit=600)
def classify_email_task(self, email_id: UUID, generation: int | None = None):
    return _process(self, email_id, 'classify', generation)


@celery_app.task(bind=True, max_retries=3, name='app.tasks.email_tasks.respond_email_task', soft_time_limit=540, time_limit=600)
def respond_email_task(self, email_id: UUID, generation: int | None = None):
    return _process(self, email_id, 'respond', generation)
