from sqlalchemy import Column, Integer, String, Text, Table, ForeignKey
from sqlalchemy.orm import relationship
from app.db.database import Base

template_category_association = Table(
    "template_category",
    Base.metadata,
    Column("template_id", Integer, ForeignKey("templates.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", Integer, ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
)

email_category_association = Table(
    "email_category",
    Base.metadata,
    Column("email_id", Integer, ForeignKey("emails.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", Integer, ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
)

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)

    templates = relationship("Template", secondary=template_category_association, back_populates="categories")
    emails = relationship("Email", secondary=email_category_association, back_populates="categories")
    documents = relationship("Document", back_populates="category")
