import os
import uuid
import shutil
from fastapi import UploadFile
from sqlalchemy.orm import Session
from app.models.feedback import Feedback
from uuid import UUID

UPLOAD_DIR = "/app/uploads/feedback"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def create_feedback(
    db: Session,
    description: str,
    file: UploadFile | None,
    user_id: UUID
) -> Feedback:
    image_path = None
    print("IMMAGINE: ", file)
    if file:
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
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
    return db_feedback

def get_feedbacks(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Feedback).offset(skip).limit(limit).all()

def get_feedback(db: Session, feedback_id: UUID) -> Feedback | None:
    return db.query(Feedback).filter(Feedback.id == feedback_id).first()
