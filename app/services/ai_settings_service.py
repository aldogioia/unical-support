from uuid import UUID
from sqlalchemy.orm import Session
from app.models.ai_settings import AISettings
from app.schemas.ai_settings import AISettingsUpdate


def get_settings(db: Session) -> AISettings:
    """
    Restituisce l'unica riga di impostazioni AI, creandola con i valori
    di default (quelli storicamente hardcoded in llm_factory) se non esiste ancora.
    """
    settings_row = db.query(AISettings).first()
    if settings_row is None:
        settings_row = AISettings()
        settings_row.apply_audit_fields(is_create=True)
        db.add(settings_row)
        db.commit()
        db.refresh(settings_row)
    return settings_row


def update_settings(db: Session, data: AISettingsUpdate, user_id: UUID) -> AISettings:
    settings_row = get_settings(db)

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(settings_row, field, value)

    settings_row.apply_audit_fields(user_id=user_id, is_create=False)

    db.commit()
    db.refresh(settings_row)
    return settings_row
