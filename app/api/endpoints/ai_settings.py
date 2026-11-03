from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.schemas.ai_settings import AISettingsResponse, AISettingsUpdate, LocalModelsResponse
from app.services import ai_settings_service
from app.services import local_models_service
from app.db.database import get_db
from app.api.authentication import get_current_user
from app.api.authorization import is_admin_user
from app.models.user import User

router = APIRouter()


@router.get("/", response_model=AISettingsResponse)
def read_ai_settings(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    return ai_settings_service.get_settings(db)


@router.put("/", response_model=AISettingsResponse)
def update_ai_settings(
    settings_in: AISettingsUpdate,
    current_user: Annotated[User, Depends(is_admin_user)],
    db: Session = Depends(get_db),
):
    return ai_settings_service.update_settings(db, settings_in, current_user.id)


@router.get("/local-models", response_model=LocalModelsResponse)
def list_local_models(
    current_user: Annotated[User, Depends(is_admin_user)],
    base_url: str = Query(..., max_length=255),
):
    """Modelli disponibili sul server locale indicato (come `ollama list`). Solo amministratori."""
    try:
        models = local_models_service.list_local_models(base_url)
    except local_models_service.LocalModelsError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return LocalModelsResponse(base_url=base_url.strip(), models=models)
