from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.core.database import Base
from backend.models.base import UUIDPrimaryKeyMixin


class GovernanceHallucination(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "governance_hallucinations"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('low','medium','high')",
            name="ck_governance_hallucinations_severity",
        ),
        CheckConstraint(
            "status IN ('open','quarantined','dismissed','resolved')",
            name="ck_governance_hallucinations_status",
        ),
    )

    student_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tutor_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    endpoint: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    reason_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="medium", index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)
    prompt_excerpt: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    response_excerpt: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    citation_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    evidence_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    resolution_note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
