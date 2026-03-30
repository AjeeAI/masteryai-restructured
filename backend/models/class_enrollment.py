from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from backend.core.database import Base
from backend.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class ClassEnrollment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "class_enrollments"
    __table_args__ = (
        UniqueConstraint("class_id", "student_id", name="uq_class_enrollments_class_student"),
        CheckConstraint("status IN ('active','removed')", name="ck_class_enrollments_status"),
    )

    class_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teacher_classes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    teacher_class: Mapped["TeacherClass"] = relationship("TeacherClass", back_populates="enrollments")
