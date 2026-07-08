import uuid
from sqlalchemy import String, Text, ForeignKey, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base
from app.core.audit_logging import Auditable

class Feedback(Base, Auditable):
    __tablename__ = "feedbacks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        index=True, 
        default=uuid.uuid4
    )
    
    description: Mapped[str] = mapped_column(Text, nullable=False)
    image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False
    )
    
    user: Mapped["User"] = relationship(
        "User"
    )
