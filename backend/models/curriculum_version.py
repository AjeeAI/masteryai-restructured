from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.core.database import Base
from backend.models.base import UUIDPrimaryKeyMixin


class CurriculumVersion(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "curriculum_versions"
    __table_args__ = (
        CheckConstraint("subject IN ('math','english','civic')", name="ck_curriculum_versions_subject"),
        CheckConstraint("sss_level IN ('SSS1','SSS2','SSS3')", name="ck_curriculum_versions_sss_level"),
        CheckConstraint("term BETWEEN 1 AND 3", name="ck_curriculum_versions_term"),
        CheckConstraint(
            "status IN ('draft','ingesting','pending_approval','approved','published','rolled_back','failed')",
            name="ck_curriculum_versions_status",
        ),
    )

    version_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    subject: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    sss_level: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    term: Mapped[int] = mapped_column(nullable=False, index=True)
    source_root: Mapped[str] = mapped_column(String(500), nullable=False)
    source_file_count: Mapped[int] = mapped_column(nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft", index=True)
    metadata_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
