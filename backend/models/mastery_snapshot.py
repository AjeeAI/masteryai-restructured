import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.database import Base
from backend.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class MasterySnapshot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "mastery_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "subject",
            "term",
            "view",
            "snapshot_date",
            name="uq_mastery_snapshots_scope_date",
        ),
        CheckConstraint("subject IN ('math','english','civic')", name="ck_mastery_snapshots_subject"),
        CheckConstraint("term BETWEEN 1 AND 3", name="ck_mastery_snapshots_term"),
        CheckConstraint("view IN ('concept','topic')", name="ck_mastery_snapshots_view"),
        CheckConstraint(
            "overall_mastery >= 0 AND overall_mastery <= 1",
            name="ck_mastery_snapshots_overall",
        ),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    term: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    view: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    mastery_payload: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    overall_mastery: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.0)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="dashboard")
