from pydantic import BaseModel, ConfigDict, Field, EmailStr
from typing import List
from app.models.email import EmailStatus
from app.schemas.category import CategoryResponse

class EmailBase(BaseModel):
    sender: EmailStr = Field(...)
    subject: str | None = Field(default=None, max_length=255)
    body: str | None = Field(default=None)

class EmailCreate(EmailBase):
    gmail_id: str = Field(..., min_length=5)
    category_ids: List[int] = Field(default_factory=list)

class EmailResponse(EmailBase):
    id: int
    gmail_id: str
    status: EmailStatus
    generated_draft: str | None = None
    categories: List[CategoryResponse] = []
    model_config = ConfigDict(from_attributes=True)

class EmailUpdateDraft(BaseModel):
    generated_draft: str = Field(..., min_length=1)
    status: EmailStatus