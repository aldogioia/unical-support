import uuid
from enum import Enum
from typing import List
from sqlalchemy import String, Text, Enum as SQLEnum, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base
from app.models.category import email_category_association
from app.models.enumerators.enumerators import EmailStatus
from app.api.audit_logging import Auditable

class Email(Base, Auditable):
    __tablename__ = "emails"


    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        index=True, 
        default=uuid.uuid4
    )

    gmail_id: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    
    sender: Mapped[str] = mapped_column(String(255))
    
    subject: Mapped[str | None] = mapped_column(String(255))
    body: Mapped[str | None] = mapped_column(Text)
    
    status: Mapped[EmailStatus] = mapped_column(
        SQLEnum(EmailStatus), 
        default=EmailStatus.TO_CLASSIFY
    )
    
    generated_draft: Mapped[str | None] = mapped_column(Text)

    categories: Mapped[List["Category"]] = relationship(
        "Category",
        secondary=email_category_association,
        back_populates="emails"
    )