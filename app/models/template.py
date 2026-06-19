from sqlalchemy import Column, Integer, String, Text, Enum
from sqlalchemy.orm import relationship
from app.db.database import Base
from app.models.category import template_category_association
import enum

class TemplateStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"               # creato dall'umano o approvato
    PENDING_APPROVAL = "PENDING_APPROVAL"   # proposto dall'agente, in attesa
    REJECTED = "REJECTED"           # rifiutato dall'operatore

class Template(Base):
    __tablename__ = "templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    subject_template = Column(String(255), nullable=True)
    body_template = Column(Text, nullable=False)

    status = Column(Enum(TemplateStatus), default=TemplateStatus.ACTIVE, nullable=False)

    usage_count = Column(Integer, default=0, nullable=False)

    categories = relationship(
        "Category",
        secondary=template_category_association,
        back_populates="templates"
    )