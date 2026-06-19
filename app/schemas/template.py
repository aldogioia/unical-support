import re
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import List
from app.schemas.category import CategoryResponse
from app.models.template import TemplateStatus  # ✅ importiamo l'enum

class TemplateBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    subject_template: str | None = Field(default=None, max_length=255)
    body_template: str = Field(..., min_length=10)

    @model_validator(mode='after')
    def validate_template_parameters(self) -> 'TemplateBase':
        body = self.body_template
        if body.count('[') != body.count(']'):
            raise ValueError("Parentesi '[' e ']' non bilanciate nel corpo.")

        if self.subject_template:
            subj = self.subject_template
            if subj.count('[') != subj.count(']'):
                raise ValueError("Parentesi '[' e ']' non bilanciate nell'oggetto.")

        parameters = re.findall(r'\[(.*?)\]', body)
        for param in parameters:
            if not re.match(r'^[A-Za-z0-9_]+$', param):
                raise ValueError(f"Parametro non valido '[{param}]'. Solo lettere, numeri e underscore.")

        return self

class TemplateCreate(TemplateBase):
    category_ids: List[int] = Field(default_factory=list)

class TemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=100)
    subject_template: str | None = Field(default=None, max_length=255)
    body_template: str | None = Field(default=None, min_length=10)
    category_ids: List[int] | None = Field(default=None)

    @model_validator(mode='after')
    def validate_template_parameters(self) -> 'TemplateUpdate':
        if self.body_template and self.body_template.count('[') != self.body_template.count(']'):
            raise ValueError("Parentesi sbilanciate nel corpo.")
        return self

# ✅ nuovo: schema per approvare o rifiutare un template proposto dall'agente
class TemplateReviewAction(BaseModel):
    action: str = Field(..., pattern="^(approve|reject)$")  # solo questi due valori

class TemplateResponse(TemplateBase):
    id: int
    status: TemplateStatus          # ✅ esposto nella response
    usage_count: int                # ✅ esposto nella response
    categories: List[CategoryResponse] = []
    model_config = ConfigDict(from_attributes=True)