import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.core.database import Base
from backend.models.base import UUIDPrimaryKeyMixin


class MasteryUpdateEvent(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "mastery_update_events"
    __table_args__ = (
        CheckConstraint("subject IN ('math','english','civic')", name="ck_mastery_update_events_subject"),
        CheckConstraint("sss_level IN ('SSS1','SSS2','SSS3')", name="ck_mastery_update_events_sss_level"),
        CheckConstraint("term BETWEEN 1 AND 3", name="ck_mastery_update_events_term"),
        CheckConstraint(
            "source IN ('practice','diagnostic','exam_prep')",
            name="ck_mastery_update_events_source",
        ),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quiz_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    attempt_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    subject: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    sss_level: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    term: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    concept_breakdown: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    new_mastery: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
