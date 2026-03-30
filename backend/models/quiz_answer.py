import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.database import Base
from backend.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class QuizAnswer(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "quiz_answers"

    attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quiz_attempts.id", ondelete="CASCADE"), index=True, nullable=False
    )

    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quiz_questions.id", ondelete="CASCADE"), index=True, nullable=False
    )

    selected_answer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)