from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.core.database import Base
from backend.models.base import UUIDPrimaryKeyMixin


class CurriculumTopicMap(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "curriculum_topic_maps"
    __table_args__ = (
        UniqueConstraint("version_id", "topic_id", "concept_id", name="uq_curriculum_topic_maps_triplet"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_curriculum_topic_maps_confidence"),
    )

    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("curriculum_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    concept_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    prereq_concept_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    confidence: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.5)
    is_manual_override: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
