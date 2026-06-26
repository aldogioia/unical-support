import uuid
from typing import List
from sqlalchemy import String, Text, Table, ForeignKey, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base
from app.api.audit_logging import Auditable

template_category_association = Table(
    "template_category",
    Base.metadata,
    mapped_column("template_id", UUID(as_uuid=True), ForeignKey("templates.id", ondelete="CASCADE"), primary_key=True),
    mapped_column("category_id", UUID(as_uuid=True), ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
)

email_category_association = Table(
    "email_category",
    Base.metadata,
    mapped_column("email_id", UUID(as_uuid=True), ForeignKey("emails.id", ondelete="CASCADE"), primary_key=True),
    mapped_column("category_id", UUID(as_uuid=True), ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
)


class Category(Base, Auditable):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        index=True, 
        default=uuid.uuid4
    )

    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)

    templates: Mapped[List["Template"]] = relationship(
        "Template", 
        secondary=template_category_association, 
        back_populates="categories"
    )
    
    emails: Mapped[List["Email"]] = relationship(
        "Email", 
        secondary=email_category_association, 
        back_populates="categories"
    )

    documents: Mapped[List["Document"]] = relationship(
        "Document", 
        back_populates="category"
    )