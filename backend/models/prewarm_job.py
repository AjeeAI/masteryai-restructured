from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.core.database import Base
from backend.models.base import UUIDPrimaryKeyMixin


class PrewarmJob(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "prewarm_jobs"
    __table_args__ = (
        CheckConstraint(
            "job_type IN ('lesson_related','course_scope')",
            name="ck_prewarm_jobs_job_type",
        ),
        CheckConstraint(
            "status IN ('queued','running','completed','failed')",
            name="ck_prewarm_jobs_status",
        ),
        CheckConstraint("attempts >= 0", name="ck_prewarm_jobs_attempts"),
    )

    job_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued", index=True)
    dedupe_key: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
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
