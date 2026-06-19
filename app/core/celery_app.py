from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery_app = Celery(
    "unical_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Rome",
    enable_utc=True,
    task_routes={
        "app.tasks.email_tasks.*": {"queue": "emails_queue"},
        "app.tasks.polling_tasks.*": {"queue": "polling_queue"},  # ✅ coda dedicata al polling
    },
    # ✅ Celery Beat: sostituisce completamente il container poller
    # controlla Gmail ogni 2 minuti invece di ogni 30 secondi
    # più sostenibile per le API di Gmail
    beat_schedule={
        "poll-gmail-every-2-minutes": {
            "task": "app.tasks.polling_tasks.poll_gmail",
            "schedule": crontab(minute="*/2"),
        }
    }
)

celery_app.autodiscover_tasks(["app.tasks"])