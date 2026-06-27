import uuid
from sqlalchemy import String, Boolean, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base
from app.models.enumerators.enumerators import UserRole 
from app.core.audit_logging import Auditable

class User(Base, Auditable):
    __tablename__ = "users"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, index=True, default=uuid.uuid4)

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    
    hashed_password: Mapped[str] = mapped_column(String(255))
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole))