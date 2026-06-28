from app.core.audit_logging import Auditable
from app.db.database import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, DateTime, UUID
from datetime import datetime
import uuid

class Blacklist(Base, Auditable):
    __tablename__ = "blacklist"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    token: Mapped[str] = mapped_column(String(500), nullable=False, unique=True, index=True)
    
    expires_at: Mapped[datetime]= mapped_column(DateTime(timezone=True), nullable=False)
    
    