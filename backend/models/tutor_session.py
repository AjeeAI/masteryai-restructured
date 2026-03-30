import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, relationship, mapped_column

from backend.core.database import Base
from backend.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class TutorSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tutor_sessions"
    __table_args__ = (
        CheckConstraint("subject IN ('math','english','civic')", name="ck_tutor_sessions_subject"),
        CheckConstraint("term BETWEEN 1 AND 3", name="ck_tutor_sessions_term"),
        CheckConstraint("status IN ('active','ended')", name="ck_tutor_sessions_status"),
        CheckConstraint("duration_seconds >= 0", name="ck_tutor_sessions_duration"),
        CheckConstraint("total_tokens >= 0", name="ck_tutor_sessions_total_tokens"),
        CheckConstraint("prompt_tokens >= 0", name="ck_tutor_sessions_prompt_tokens"),
        CheckConstraint("completion_tokens >= 0", name="ck_tutor_sessions_completion_tokens"),
        CheckConstraint("cost_usd >= 0", name="ck_tutor_sessions_cost_usd"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    term: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    end_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)

    messages: Mapped[list["TutorMessage"]] = relationship(
        "TutorMessage",
        back_populates="session",
        cascade="all, delete-orphan",
    )
