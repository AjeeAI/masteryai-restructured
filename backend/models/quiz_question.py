import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.database import Base
from backend.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class QuizQuestion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "quiz_questions"

    quiz_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quizzes.id", ondelete="CASCADE"), index=True, nullable=False
    )

    question_number: Mapped[int] = mapped_column(Integer, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    concept_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # For MCQ etc.
    options: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # Optional: For objective questions where the system can auto-grade.
    correct_answer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
