import uuid
from typing import List
from sqlalchemy import String, Text, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base
from app.models.category import document_category_association
from app.core.audit_logging import Auditable

class Document(Base, Auditable):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        index=True, 
        default=uuid.uuid4
    )
    
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    
    extracted_text: Mapped[str | None] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(500))

    categories: Mapped[List["Category"]] = relationship(
        "Category",
        secondary=document_category_association,
        back_populates="documents"
    )
