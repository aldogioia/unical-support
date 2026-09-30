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

class CategoryImportResult(BaseModel):
    total_processed: int = Field(..., description="Totale elementi analizzati nel file o payload")
    created_count: int = Field(..., description="Numero di categorie create con successo")
    skipped_count: int = Field(..., description="Numero di categorie saltate (già esistenti o duplicate)")
    created_categories: list[CategoryResponse] = Field(default_factory=list, description="Elenco delle categorie create")
    skipped_categories: list[str] = Field(default_factory=list, description="Nomi delle categorie saltate")
    errors: list[str] = Field(default_factory=list, description="Eventuali anomalie o errori riscontrati")