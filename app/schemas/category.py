from pydantic import BaseModel, ConfigDict, Field
import uuid

class CategoryBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=50, description="Nome univoco della categoria")
    description: str | None = Field(default=None, max_length=500)

class CategoryCreate(CategoryBase):
    pass

class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=50)
    description: str | None = Field(default=None, max_length=500)

class CategoryResponse(CategoryBase):
    id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)