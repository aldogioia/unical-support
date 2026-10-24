from pydantic import BaseModel, ConfigDict, Field
from typing import List, Literal
from app.models.enumerators.enumerators import EmailStatus
from app.schemas.category import CategoryResponse
import uuid

class EmailBase(BaseModel):

    sender: str = Field(..., min_length=1, max_length=255)
    subject: str | None = Field(default=None, max_length=255)
    body: str | None = Field(default=None)

class EmailCreate(EmailBase):
    gmail_id: str = Field(..., min_length=5)
    category_ids: List[uuid.UUID] = Field(default_factory=list)

class EmailResponse(EmailBase):
    id: uuid.UUID
    gmail_id: str
    status: EmailStatus
    generated_draft: str | None = None
    ai_confidence: float | None = Field(default=None, ge=0, le=1)
    response_language: str | None = None
    ai_disclaimer: str | None = None
    categories: List[CategoryResponse] = []
    model_config = ConfigDict(from_attributes=True)

class EmailUpdateDraft(BaseModel):
    generated_draft: str = Field(..., min_length=1)
    status: EmailStatus


class EmailFetchResponse(BaseModel):
    job_id: uuid.UUID
    status: Literal['queued', 'running', 'completed', 'failed', 'expired']
    message: str
    fetched_count: int = 0
    already_running: bool = False


class EmailPreviewRequest(BaseModel):
    generated_draft: str = Field(min_length=1, max_length=100000)


class EmailPreviewResponse(BaseModel):
    html: str
