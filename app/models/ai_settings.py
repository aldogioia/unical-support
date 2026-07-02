import uuid
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import UUID
from app.db.database import Base
from app.core.audit_logging import Auditable


class AISettings(Base, Auditable):
    """
    Tabella singleton: contiene un'unica riga con i nomi dei modelli LLM
    attualmente in uso per classificazione e generazione risposte.
    Modificabile a runtime dal frontend, senza richiedere un redeploy.
    """
    __tablename__ = "ai_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        index=True,
        default=uuid.uuid4
    )

    classifier_provider: Mapped[str] = mapped_column(String(50), default="groq")
    classifier_model: Mapped[str] = mapped_column(String(100), default="openai/gpt-oss-20b")

    classifier_base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)

    responder_provider: Mapped[str] = mapped_column(String(50), default="google")
    responder_model: Mapped[str] = mapped_column(String(100), default="gemini-3.1-flash-lite")
    responder_base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)