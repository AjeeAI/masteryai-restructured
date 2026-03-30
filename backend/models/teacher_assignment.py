from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base
from backend.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class TeacherAssignment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "teacher_assignments"
    __table_args__ = (
        CheckConstraint("assignment_type IN ('topic','quiz','revision')", name="ck_teacher_assignments_type"),
        CheckConstraint("subject IN ('math','english','civic')", name="ck_teacher_assignments_subject"),
        CheckConstraint("sss_level IN ('SSS1','SSS2','SSS3')", name="ck_teacher_assignments_sss_level"),
        CheckConstraint("term BETWEEN 1 AND 3", name="ck_teacher_assignments_term"),
        CheckConstraint("status IN ('assigned','completed','cancelled')", name="ck_teacher_assignments_status"),
        CheckConstraint(
            "(class_id IS NOT NULL) OR (student_id IS NOT NULL)",
            name="ck_teacher_assignments_target_required",
        ),
    )

    teacher_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    class_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("teacher_classes.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    student_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    assignment_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    concept_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    concept_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ref_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    instructions: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    subject: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    sss_level: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    term: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="assigned", index=True)

    teacher_class: Mapped["TeacherClass"] = relationship("TeacherClass", back_populates="assignments")
