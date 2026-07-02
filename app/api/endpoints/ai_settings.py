from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.schemas.ai_settings import AISettingsResponse, AISettingsUpdate
from app.services import ai_settings_service
from app.db.database import get_db
from app.api.authentication import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("/", response_model=AISettingsResponse)
def read_ai_settings(db: Session = Depends(get_db)):
    return ai_settings_service.get_settings(db)


@router.put("/", response_model=AISettingsResponse)
def update_ai_settings(
    settings_in: AISettingsUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    return ai_settings_service.update_settings(db, settings_in, current_user.id)
