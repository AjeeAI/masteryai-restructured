import uuid

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.database import Base
from backend.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class QuizAttempt(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "quiz_attempts"

    quiz_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quizzes.id", ondelete="CASCADE"), index=True, nullable=False
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    time_taken_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="submitted")

    # Mirrors the internal contract shape (list of answers), while keeping normalized quiz_answers table too.
    raw_answers: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)