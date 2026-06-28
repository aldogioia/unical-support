import re
import uuid
from typing import List
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.schemas.category import CategoryResponse
from app.models.enumerators.enumerators import TemplateStatus

def _check_template_syntax(text: str, context: str):
    if text.count('[') != text.count(']'):
        raise ValueError(f"Parentesi '[' e ']' non bilanciate in: {context}.")
    
    parameters = re.findall(r'\[(.*?)\]', text)
    for param in parameters:
        if not re.match(r'^[A-Za-z0-9_]+$', param):
            raise ValueError(f"Parametro non valido '[{param}]' in {context}. Solo lettere, numeri e underscore.")


class TemplateBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    subject_template: str | None = Field(default=None, max_length=255)
    body_template: str = Field(..., min_length=10)

    @model_validator(mode='after')
    def validate_template_parameters(self) -> 'TemplateBase':
        _check_template_syntax(self.body_template, "corpo")
        if self.subject_template:
            _check_template_syntax(self.subject_template, "oggetto")
        return self


class TemplateCreate(TemplateBase):
    category_ids: List[uuid.UUID] = Field(default_factory=list)


class TemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=100)
    subject_template: str | None = Field(default=None, max_length=255)
    body_template: str | None = Field(default=None, min_length=10)
    category_ids: List[uuid.UUID] | None = Field(default=None)

    @model_validator(mode='after')
    def validate_template_parameters(self) -> 'TemplateUpdate':
        if self.body_template:
            _check_template_syntax(self.body_template, "corpo")
        if self.subject_template:
            _check_template_syntax(self.subject_template, "oggetto")
        return self


class TemplateReviewAction(BaseModel):
    action: str = Field(..., pattern="^(approve|reject)$")


class TemplateResponse(TemplateBase):
    id: uuid.UUID
    status: TemplateStatus
    usage_count: int
    categories: List[CategoryResponse] = []
    
    model_config = ConfigDict(from_attributes=True)