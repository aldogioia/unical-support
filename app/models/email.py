from sqlalchemy import Column, Integer, String, Text, Enum
from sqlalchemy.orm import relationship
import enum
from app.db.database import Base
from app.models.category import email_category_association

class EmailStatus(str, enum.Enum):
    UNREAD = "UNREAD"
    PROCESSING = "PROCESSING"
    DRAFT = "DRAFT"
    SENT = "SENT"
    IGNORED = "IGNORED"
    FAILED = "FAILED" 

class Email(Base):
    __tablename__ = "emails"

    id = Column(Integer, primary_key=True, index=True)
    gmail_id = Column(String(255), unique=True, index=True)
    sender = Column(String(255), nullable=False)
    subject = Column(String(255), nullable=True)
    body = Column(Text, nullable=True)
    status = Column(Enum(EmailStatus), default=EmailStatus.UNREAD)
    generated_draft = Column(Text, nullable=True)
    categories = relationship("Category", secondary=email_category_association, back_populates="emails")