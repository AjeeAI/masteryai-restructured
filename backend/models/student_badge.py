import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.core.database import Base
from backend.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class StudentBadge(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "student_badges"
    __table_args__ = (
        UniqueConstraint("student_id", "badge_code", name="uq_student_badges_student_code"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    badge_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    badge_name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    metadata_payload: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    awarded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
