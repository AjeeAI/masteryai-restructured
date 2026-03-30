import uuid
from sqlalchemy import String, Integer, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import UUIDPrimaryKeyMixin, TimestampMixin
from backend.core.database import Base

class Topic(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "topics"
    __table_args__ = (
        # Prevent duplicate topics for same scope + title within a curriculum version
        UniqueConstraint("subject_id", "sss_level", "term", "title", name="uq_topic_scope_title"),
    )

    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id", ondelete="RESTRICT"), index=True, nullable=False)

    sss_level: Mapped[str] = mapped_column(String(10), index=True, nullable=False)  # SSS1/SSS2/SSS3
    term: Mapped[int] = mapped_column(Integer, index=True, nullable=False)          # 1/2/3

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    curriculum_version_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)

    is_approved: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)

    subject = relationship("Subject")
    lesson = relationship("Lesson", back_populates="topic", uselist=False, cascade="all, delete-orphan")  # 1:1