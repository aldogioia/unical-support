import uuid
from enum import Enum
from sqlalchemy import String, Text, Enum as SQLEnum, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base
from app.models.category import template_category_association
from typing import List
from app.models.enumerators.enumerators import TemplateStatus
from app.api.audit_logging import Auditable

class Template(Base, Auditable):
    __tablename__ = "templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        index=True, 
        default=uuid.uuid4
    )
    
    name: Mapped[str] = mapped_column(String(255))
    
    subject_template: Mapped[str | None] = mapped_column(String(255))
    
    body_template: Mapped[str] = mapped_column(Text)

    status: Mapped[TemplateStatus] = mapped_column(
        SQLEnum(TemplateStatus), 
        default=TemplateStatus.ACTIVE
    )

    usage_count: Mapped[int] = mapped_column(default=0)

    categories: Mapped[List["Category"]] = relationship(
        "Category",
        secondary=template_category_association,
        back_populates="templates"
    )