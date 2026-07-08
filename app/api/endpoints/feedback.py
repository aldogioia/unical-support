from app.api.authentication import get_current_user_dev_bypass
from uuid import UUID
from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.api.authentication import get_current_user
from app.models.user import User
from app.models.enumerators.enumerators import UserRole
from app.schemas.feedback import FeedbackResponse
from app.services import feedback_service

router = APIRouter()

@router.post("/", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
def create_user_feedback(
    current_user: Annotated[User, Depends(get_current_user_dev_bypass)],
    description: str = Form(...),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    return feedback_service.create_feedback(
        db=db,
        description=description,
        file=image,
        user_id=current_user.id
    )

@router.get("/", response_model=List[FeedbackResponse])
def read_feedbacks(
    current_user: Annotated[User, Depends(get_current_user_dev_bypass)],
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    return feedback_service.get_feedbacks(db, skip=skip, limit=limit)
