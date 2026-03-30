import uuid

from sqlalchemy import ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.database import Base
from backend.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class DiagnosticAttempt(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "diagnostic_attempts"
    __table_args__ = (
        UniqueConstraint("diagnostic_id", name="uq_diagnostic_attempt_diagnostic"),
    )

    diagnostic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("diagnostics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    answers: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    baseline_mastery_updates: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    gap_summary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    recommended_start_topic_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    recommended_start_topic_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
