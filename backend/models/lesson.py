"""Lesson + LessonBlock ORM models.

Logic:
- Lesson is attached to a Topic.
- LessonBlocks store structured content in a stable display order.
"""

import uuid
from sqlalchemy import String, Integer, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import UUIDPrimaryKeyMixin, TimestampMixin
from backend.core.database import Base

class Lesson(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lessons"
    __table_args__ = (
        # Ensure 1:1 topic -> lesson
        UniqueConstraint("topic_id", name="uq_lesson_topic"),
    )

    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True, nullable=False)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(String(800), nullable=True)
    estimated_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    topic = relationship("Topic", back_populates="lesson")
    blocks = relationship("LessonBlock", back_populates="lesson", cascade="all, delete-orphan", order_by="LessonBlock.order_index")


class LessonBlock(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lesson_blocks"
    __table_args__ = (
        UniqueConstraint("lesson_id", "order_index", name="uq_lesson_block_order"),
        CheckConstraint(
            "block_type IN ('text','video','image','example','exercise')",
            name="ck_lesson_block_type",
        ),
    )

    lesson_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True, nullable=False)

    # text | video | image | example | exercise
    block_type: Mapped[str] = mapped_column(String(30), index=True, nullable=False)

    # JSONB supports storing structured block payloads cleanly
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)

    order_index: Mapped[int] = mapped_column(Integer, index=True, nullable=False)

    lesson = relationship("Lesson", back_populates="blocks")
