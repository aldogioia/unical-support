from celery import Celery
from app.core.config import settings

# Creazione dell'istanza Celery
celery_app = Celery(
    "unical_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

# Configurazioni opzionali per ottimizzare Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Rome",
    enable_utc=True,
    # Indirizziamo i task delle email a una coda specifica chiamata "emails_queue"
    task_routes={
        "app.tasks.email_tasks.*": {"queue": "emails_queue"}
    }
)

# Auto-scoperta dei task nella cartella "app.tasks"
celery_app.autodiscover_tasks(["app.tasks"])