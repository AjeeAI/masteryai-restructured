import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.core.database import Base


class InternalQuizAttempt(Base):
    __tablename__ = "internal_quiz_attempts"
    __table_args__ = (
        CheckConstraint("subject IN ('math','english','civic')", name="ck_internal_quiz_attempts_subject"),
        CheckConstraint("sss_level IN ('SSS1','SSS2','SSS3')", name="ck_internal_quiz_attempts_sss_level"),
        CheckConstraint("term BETWEEN 1 AND 3", name="ck_internal_quiz_attempts_term"),
        CheckConstraint("time_taken_seconds >= 0", name="ck_internal_quiz_attempts_time"),
        CheckConstraint("score >= 0 AND score <= 100", name="ck_internal_quiz_attempts_score"),
    )

    attempt_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    quiz_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    sss_level: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    term: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    answers: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    time_taken_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
