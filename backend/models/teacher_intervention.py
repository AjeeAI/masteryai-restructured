from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base
from backend.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class TeacherIntervention(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "teacher_interventions"
    __table_args__ = (
        CheckConstraint(
            "intervention_type IN ('note','flag','support_plan','parent_contact')",
            name="ck_teacher_interventions_type",
        ),
        CheckConstraint("severity IN ('low','medium','high')", name="ck_teacher_interventions_severity"),
        CheckConstraint("subject IN ('math','english','civic')", name="ck_teacher_interventions_subject"),
        CheckConstraint("sss_level IN ('SSS1','SSS2','SSS3')", name="ck_teacher_interventions_sss_level"),
        CheckConstraint("term BETWEEN 1 AND 3", name="ck_teacher_interventions_term"),
        CheckConstraint("status IN ('open','resolved','dismissed')", name="ck_teacher_interventions_status"),
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
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    intervention_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    concept_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    concept_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="medium", index=True)
    subject: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    sss_level: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    term: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    notes: Mapped[str] = mapped_column(String(2000), nullable=False)
    action_plan: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    teacher_class: Mapped["TeacherClass"] = relationship("TeacherClass", back_populates="interventions")
