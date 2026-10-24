from typing import List
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.core.urls import normalize_reference_url
from app.schemas.category import CategoryResponse
import uuid

class DocumentBase(BaseModel):
    filename: str = Field(..., min_length=3, max_length=255)
    content_type: str = Field(..., pattern=r'^[a-zA-Z0-9]+/[a-zA-Z0-9.-]+$')
    extracted_text: str | None = Field(default=None, min_length=1)
    reference_url: str | None = Field(default=None, max_length=2048)

class DocumentCreate(DocumentBase):
    category_ids: List[uuid.UUID] = Field(default_factory=list)
    _validate_reference_url = field_validator('reference_url')(normalize_reference_url)

class DocumentUpdate(BaseModel):
    # Lista completa delle categorie da associare al documento (sostituisce quelle esistenti).
    # Una lista vuota rimuove tutte le categorie.
    category_ids: List[uuid.UUID] = Field(default_factory=list)
    reference_url: str | None = Field(default=None, max_length=2048)
    _validate_reference_url = field_validator('reference_url')(normalize_reference_url)

class DocumentResponse(DocumentBase):
    id: uuid.UUID
    categories: List[CategoryResponse] = []
    processing_status: str = "pending"
    review_notes: str | None = None
    model_config = ConfigDict(from_attributes=True)
