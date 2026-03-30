from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.core.database import Base
from backend.models.base import UUIDPrimaryKeyMixin


class CurriculumIngestionJob(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "curriculum_ingestion_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','parsing','chunking','embedding','indexing','completed','failed')",
            name="ck_curriculum_ingestion_jobs_status",
        ),
        CheckConstraint("progress_percent BETWEEN 0 AND 100", name="ck_curriculum_ingestion_jobs_progress"),
        CheckConstraint("processed_files_count >= 0", name="ck_curriculum_ingestion_jobs_files_count"),
        CheckConstraint("processed_chunks_count >= 0", name="ck_curriculum_ingestion_jobs_chunks_count"),
    )

    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("curriculum_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued", index=True)
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    processed_files_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_chunks_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    logs_payload: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
