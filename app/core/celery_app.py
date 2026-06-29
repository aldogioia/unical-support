from celery import Celery
from celery.signals import worker_process_init
from celery.schedules import crontab
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

celery_app = Celery(
    "unical_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.email_tasks",
        "app.tasks.polling_tasks"
    ]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Rome",
    enable_utc=True,
    task_routes={
        "app.tasks.email_tasks.classify_email*": {"queue": "classify_queue"},
        "app.tasks.email_tasks.respond_email*": {"queue": "respond_queue"},
        "app.tasks.polling_tasks.*": {"queue": "polling_queue"},
    },
    beat_schedule={
        "poll-gmail-every-2-minutes": {
            "task": "app.tasks.polling_tasks.poll_gmail",
            "schedule": crontab(minute="*/2"),
        },
        "sweep-stuck-emails-every-15-minutes": {
            "task": "app.tasks.polling_tasks.sweep_stuck_emails",
            "schedule": crontab(minute="*/15"),
        }
    }
)

@worker_process_init.connect
def init_worker_dependencies(**kwargs):
    from app.ai.rag import init_vector_store
    logger.info("Inizializzazione del Vector Store per il worker Celery...")
    try:
        init_vector_store()
        logger.info("Vector Store inizializzato con successo nel worker.")
    except Exception as e:
        logger.error(f"Errore critico nell'inizializzazione del Vector Store nel worker: {e}")