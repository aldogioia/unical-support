import re
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import List
from app.schemas.category import CategoryResponse
import re

class TemplateBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    subject_template: str | None = Field(default=None, max_length=255)
    body_template: str = Field(..., min_length=10)

    @model_validator(mode='after')
    def validate_template_parameters(self) -> 'TemplateBase':
    
        body = self.body_template
        if body.count('[') != body.count(']'):
            raise ValueError("Errore di sintassi nel template: numero di '[' e ']' non corrispondente nel corpo.")
        
        if self.subject_template:
            subj = self.subject_template
            if subj.count('[') != subj.count(']'):
                raise ValueError("Errore di sintassi nel template: numero di '[' e ']' non corrispondente nell'oggetto.")

        parameters = re.findall(r'\[(.*?)\]', body)
        for param in parameters:
            if not re.match(r'^[A-Za-z0-9_]+$', param):
                raise ValueError(f"Parametro non valido '[{param}]'. Usa solo lettere, numeri e underscore senza spazi.")
        
        return self

class TemplateCreate(TemplateBase):
    category_ids: List[int] = Field(default_factory=list, description="Lista degli ID delle categorie")
    pass

class TemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=100)
    subject_template: str | None = Field(default=None, max_length=255)
    body_template: str | None = Field(default=None, min_length=10)
    category_ids: List[int] | None = Field(default=None)
    
    @model_validator(mode='after')
    def validate_template_parameters(self) -> 'TemplateUpdate':
        if self.body_template and self.body_template.count('[') != self.body_template.count(']'):
            raise ValueError("Errore di sintassi nel template: parentesi sbilanciate.")
        return self

class TemplateResponse(TemplateBase):
    id: int
    categories: List[CategoryResponse] = []
    model_config = ConfigDict(from_attributes=True)