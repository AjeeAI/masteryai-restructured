from __future__ import annotations

import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base
from backend.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class TeacherClass(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "teacher_classes"
    __table_args__ = (
        UniqueConstraint(
            "teacher_id",
            "name",
            "subject",
            "sss_level",
            "term",
            name="uq_teacher_classes_scope_name",
        ),
        CheckConstraint("subject IN ('math','english','civic')", name="ck_teacher_classes_subject"),
        CheckConstraint("sss_level IN ('SSS1','SSS2','SSS3')", name="ck_teacher_classes_sss_level"),
        CheckConstraint("term BETWEEN 1 AND 3", name="ck_teacher_classes_term"),
    )

    teacher_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    subject: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    sss_level: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    term: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    enrollments: Mapped[list["ClassEnrollment"]] = relationship(
        "ClassEnrollment",
        back_populates="teacher_class",
        cascade="all, delete-orphan",
    )
    assignments: Mapped[list["TeacherAssignment"]] = relationship(
        "TeacherAssignment",
        back_populates="teacher_class",
        cascade="all, delete-orphan",
    )
    interventions: Mapped[list["TeacherIntervention"]] = relationship(
        "TeacherIntervention",
        back_populates="teacher_class",
        cascade="all, delete-orphan",
    )
