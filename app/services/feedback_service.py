import os
import uuid
import smtplib
import shutil
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from fastapi import UploadFile
from sqlalchemy.orm import Session
from app.models.feedback import Feedback
from app.core.config import settings
from uuid import UUID

UPLOAD_DIR = "/app/uploads/feedback"
os.makedirs(UPLOAD_DIR, exist_ok=True)


ALLOWED_IMAGE_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

def create_feedback(
    db: Session,
    description: str,
    file: UploadFile | None,
    user_id: UUID
) -> Feedback:
    image_path = None
    image_bytes = None

    if file:
        content_type = (file.content_type or "").lower()
        ext = os.path.splitext(file.filename)[1].lower() if file.filename else ""

        if content_type in ALLOWED_IMAGE_TYPES:
            file_extension = ALLOWED_IMAGE_TYPES[content_type]
        elif ext in ALLOWED_IMAGE_EXTENSIONS:
            file_extension = ext
        elif content_type.startswith("image/"):
            file_extension = ".png"
        else:
            raise ValueError(f"Tipo di file '{content_type or ext}' non consentito per l'allegato del feedback. Sono ammesse solo immagini (PNG, JPG, WEBP, GIF).")

        file.file.seek(0, os.SEEK_END)
        file_size = file.file.tell()
        file.file.seek(0)

        if file_size > 10 * 1024 * 1024:
            raise ValueError("La dimensione dello screenshot supera il limite di 10MB.")

        unique_filename = f"{uuid.uuid4()}{file_extension}"
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        file_path = os.path.join(UPLOAD_DIR, unique_filename)

        # Leggi i byte prima di salvare (servono anche per l'email)
        image_bytes = file.file.read()

        with open(file_path, "wb") as buffer:
            buffer.write(image_bytes)

        image_path = f"feedback/{unique_filename}"

    db_feedback = Feedback(
        description=description,
        image_path=image_path,
        user_id=user_id
    )
    db_feedback.apply_audit_fields(user_id=user_id, is_create=True)
    db.add(db_feedback)
    db.commit()
    db.refresh(db_feedback)

    # Invia email di notifica (non bloccante: se fallisce logga ma non rompe il flusso)
    try:
        _send_feedback_email(description=description, image_bytes=image_bytes, user_id=user_id)
    except Exception as e:
        print(f"[FEEDBACK] Errore invio email notifica: {e}")

    return db_feedback


def _send_feedback_email(description: str, image_bytes: bytes | None, user_id: UUID):
    sender = settings.FEEDBACK_EMAIL_SENDER
    password = settings.FEEDBACK_EMAIL_PASSWORD
    recipient = settings.FEEDBACK_EMAIL_RECIPIENT

    if not sender or not password or not recipient:
        print("[FEEDBACK] Variabili email non configurate, invio saltato.")
        return

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = "Nuovo Feedback - Unical Support"

    body = f"""Nuovo feedback ricevuto da Unical Support.

Utente (ID): {user_id}
Descrizione:
{description}

{"Screenshot allegato." if image_bytes else "Nessuno screenshot allegato."}
"""
    msg.attach(MIMEText(body, "plain", "utf-8"))

    if image_bytes:
        img = MIMEImage(image_bytes, name="screenshot.png")
        img.add_header("Content-Disposition", "attachment", filename="screenshot.png")
        msg.attach(img)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, recipient, msg.as_string())

    print(f"[FEEDBACK] Email notifica inviata a {recipient}")


def get_feedbacks(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Feedback).offset(skip).limit(limit).all()


def get_feedback(db: Session, feedback_id: UUID) -> Feedback | None:
    return db.query(Feedback).filter(Feedback.id == feedback_id).first()