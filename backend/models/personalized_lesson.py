"""Per-student persisted lesson drafts generated from RAG + mastery context."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.database import Base
from backend.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class PersonalizedLesson(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "personalized_lessons"
    __table_args__ = (
        UniqueConstraint("student_id", "topic_id", name="uq_personalized_lesson_student_topic"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    curriculum_version_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(String(1200), nullable=True)
    estimated_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    content_blocks: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    source_chunk_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    generation_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
