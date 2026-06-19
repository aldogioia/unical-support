from pydantic import BaseModel, ConfigDict, Field
from app.schemas.category import CategoryResponse

class DocumentBase(BaseModel):
    filename: str = Field(..., min_length=3, max_length=255)
    content_type: str = Field(..., pattern=r'^[a-zA-Z0-9]+/[a-zA-Z0-9.-]+$')
    extracted_text: str | None = Field(default=None, min_length=1)
    link: str | None = Field(default=None, max_length=500)
    category_id: int | None = Field(default=None, gt=0)

class DocumentCreate(DocumentBase):
    pass

class DocumentResponse(DocumentBase):
    id: int
    category: CategoryResponse | None = None
    model_config = ConfigDict(from_attributes=True)