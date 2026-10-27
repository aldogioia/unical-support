import uuid
from datetime import datetime
from typing import List
from sqlalchemy import String, Text, Float, Integer, Boolean, DateTime, Index, func, text, CheckConstraint, Enum as SQLEnum, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base
from app.models.category import email_category_association
from app.models.enumerators.enumerators import EmailStatus
from app.core.audit_logging import Auditable

class Email(Base, Auditable):
    __tablename__ = "emails"
    __table_args__ = (CheckConstraint("ai_confidence >= 0 AND ai_confidence <= 1", name="ck_emails_ai_confidence_range"), Index("ix_emails_received_id", "received_at", "id"))


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
    
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    draft_revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default='0', default=0)
    processing_generation: Mapped[int] = mapped_column(Integer, nullable=False, server_default='0', default=0)
    manually_edited: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'), default=False)
    processing_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_stage: Mapped[str | None] = mapped_column(String(16), nullable=True)

    generated_draft: Mapped[str | None] = mapped_column(Text)
    ai_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    response_language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    ai_disclaimer: Mapped[str | None] = mapped_column(Text, nullable=True)

    categories: Mapped[List["Category"]] = relationship(
        "Category",
        secondary=email_category_association,
        back_populates="emails"
    )
