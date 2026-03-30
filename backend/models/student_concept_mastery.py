import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.core.database import Base
from backend.models.base import UUIDPrimaryKeyMixin


class StudentConceptMastery(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "student_concept_mastery"
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "subject",
            "sss_level",
            "term",
            "concept_id",
            name="uq_student_concept_mastery_scope",
        ),
        CheckConstraint("subject IN ('math','english','civic')", name="ck_student_concept_mastery_subject"),
        CheckConstraint("sss_level IN ('SSS1','SSS2','SSS3')", name="ck_student_concept_mastery_sss_level"),
        CheckConstraint("term BETWEEN 1 AND 3", name="ck_student_concept_mastery_term"),
        CheckConstraint(
            "mastery_score >= 0 AND mastery_score <= 1",
            name="ck_student_concept_mastery_score",
        ),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    sss_level: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    term: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    concept_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    mastery_score: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.0)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="diagnostic")
    last_evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
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
