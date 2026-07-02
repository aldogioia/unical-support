from pydantic import BaseModel, ConfigDict, Field
import uuid


class AISettingsResponse(BaseModel):
    id: uuid.UUID
    classifier_provider: str
    classifier_model: str
    classifier_base_url: str | None = None
    responder_provider: str
    responder_model: str
    responder_base_url: str | None = None
    model_config = ConfigDict(from_attributes=True)


class AISettingsUpdate(BaseModel):
    classifier_provider: str | None = Field(default=None, min_length=2, max_length=50)
    classifier_model: str | None = Field(default=None, min_length=2, max_length=100)
    classifier_base_url: str | None = Field(default=None, max_length=255)
    responder_provider: str | None = Field(default=None, min_length=2, max_length=50)
    responder_model: str | None = Field(default=None, min_length=2, max_length=100)
    responder_base_url: str | None = Field(default=None, max_length=255)