from typing import List
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.category import CategoryResponse
import uuid

class DocumentBase(BaseModel):
    filename: str = Field(..., min_length=3, max_length=255)
    content_type: str = Field(..., pattern=r'^[a-zA-Z0-9]+/[a-zA-Z0-9.-]+$')
    extracted_text: str | None = Field(default=None, min_length=1)
    link: str | None = Field(default=None, max_length=500)

class DocumentCreate(DocumentBase):
    category_ids: List[uuid.UUID] = Field(default_factory=list)

class DocumentUpdate(BaseModel):
    # Lista completa delle categorie da associare al documento (sostituisce quelle esistenti).
    # Una lista vuota rimuove tutte le categorie.
    category_ids: List[uuid.UUID] = Field(default_factory=list)

class DocumentResponse(DocumentBase):
    id: uuid.UUID
    categories: List[CategoryResponse] = []
    model_config = ConfigDict(from_attributes=True)
