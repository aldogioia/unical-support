"""Database leases and generation fencing shared by AI jobs, retries and the sweeper."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from app.models.email import Email, EmailStatus

LEASE_SECONDS = 660


def claim_processing(db, email_id, status, generation=None):
    email = db.query(Email).filter(Email.id == email_id).populate_existing().with_for_update().first()
    if not email or email.status != status or email.manually_edited:
        return None
    if generation is not None and email.processing_generation != generation:
        return None
    now = datetime.now(timezone.utc)
    if email.processing_token and email.processing_started_at and email.processing_started_at > now - timedelta(seconds=LEASE_SECONDS):
        return None
    email.processing_token = str(uuid4())
    email.processing_started_at = now
    return email


def can_write(email, status, token):
    return bool(email and email.status == status and not email.manually_edited
                and email.processing_token == token)


def release_processing(email):
    email.processing_token = None
    email.processing_started_at = None


def enqueue_processing(email_id, stage, generation):
    from app.core.celery_app import celery_app
    name = 'classify' if stage == 'classify' else 'respond'
    return celery_app.send_task(
        f'app.tasks.email_tasks.{name}_email_task', args=[str(email_id)],
        kwargs={'generation': generation}, queue=f'{name}_queue',
    )
