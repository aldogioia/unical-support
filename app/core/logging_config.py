"""
Configurazione unica del logging per backend (uvicorn/FastAPI), worker e beat (Celery).

Formato di ogni riga:
    2026-11-03 12:05:31 | INFO     | worker classify_email_task[3f2a9c1e] | app.tasks.email_tasks | messaggio

- data e ora (senza millesimi) nel fuso indicato da LOG_TIMEZONE (default Europe/Rome);
- livello;
- componente: backend, worker o beat; dentro un task Celery anche nome e ID breve del task;
- modulo che ha scritto la riga;
- messaggio, seguito dal traceback completo quando si registra un'eccezione.

Il livello minimo si regola con la variabile d'ambiente LOG_LEVEL (default INFO).
"""
import logging
import os
import sys
from datetime import datetime

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(component)s | %(name)s | %(message)s"

# Librerie molto verbose: si vedono solo i loro avvisi ed errori.
QUIET_LOGGERS = ("httpx", "httpcore", "urllib3", "openai", "groq", "google", "googleapiclient",
                 "sqlalchemy.engine", "unstructured", "pdfminer", "multipart", "asyncio", "apscheduler")

# Logger che uvicorn e Celery configurano per conto loro: li riportiamo al gestore unico.
OWNED_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access", "celery", "celery.app.trace",
                 "celery.worker", "celery.beat", "celery.task", "celery.redirected")


def _timezone():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(os.environ.get("LOG_TIMEZONE", "Europe/Rome"))
    except Exception:  # fuso non disponibile: si usa l'ora del sistema
        return None


class UnicalFormatter(logging.Formatter):
    """Formatter con data e ora nel fuso configurato."""

    def __init__(self):
        super().__init__(LOG_FORMAT, DATE_FORMAT)
        self.tz = _timezone()

    def formatTime(self, record, datefmt=None):
        moment = datetime.fromtimestamp(record.created, self.tz) if self.tz else datetime.fromtimestamp(record.created)
        return moment.strftime(datefmt or DATE_FORMAT)


class ComponentFilter(logging.Filter):
    """Aggiunge a ogni riga il componente e, dentro un task Celery, nome e ID breve del task."""

    def __init__(self, component: str):
        super().__init__()
        self.component = component

    def filter(self, record):
        component = self.component
        try:
            from celery import current_task
            if current_task and current_task.request and current_task.request.id:
                name = (current_task.name or "task").rsplit(".", 1)[-1]
                component = f"{self.component} {name}[{current_task.request.id[:8]}]"
        except Exception:
            pass
        record.component = component
        return True


def setup_logging(component: str) -> None:
    """Configura il logging del processo. component: 'backend', 'worker' o 'beat'."""
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(UnicalFormatter())
    handler.addFilter(ComponentFilter(component))

    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)

    for name in OWNED_LOGGERS:
        owned = logging.getLogger(name)
        owned.handlers[:] = []
        owned.propagate = True
    for name in QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
    logging.captureWarnings(True)
