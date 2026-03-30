import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.database import Base
from backend.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class Diagnostic(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "diagnostics"
    __table_args__ = (
        CheckConstraint("subject IN ('math','english','civic')", name="ck_diagnostics_subject"),
        CheckConstraint("sss_level IN ('SSS1','SSS2','SSS3')", name="ck_diagnostics_sss_level"),
        CheckConstraint("term BETWEEN 1 AND 3", name="ck_diagnostics_term"),
        CheckConstraint("status IN ('started','submitted')", name="ck_diagnostics_status"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    sss_level: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    term: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="started")
    concept_targets: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    questions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
