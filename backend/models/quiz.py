import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.database import Base
from backend.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class Quiz(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "quizzes"

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    subject: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    sss_level: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    term: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    topic_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("topics.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    purpose: Mapped[str | None] = mapped_column(String(50), nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String(20), nullable=True)

    num_questions: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="generated")

    time_limit_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Use a non-reserved Python attribute name while preserving DB column name.
    extra_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)


# Compatibility re-exports for code/tests that import all quiz models from this module.
from backend.models.quiz_question import QuizQuestion  # noqa: E402
from backend.models.quiz_attempt import QuizAttempt  # noqa: E402
from backend.models.quiz_answer import QuizAnswer  # noqa: E402
