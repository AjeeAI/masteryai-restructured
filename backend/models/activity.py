import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.database import Base
from backend.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class ActivityLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "activity_logs"

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    subject: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    term: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    ref_id: Mapped[str] = mapped_column(String(255), nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class DailyActivitySummary(Base):
    __tablename__ = "daily_activity_summary"

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, nullable=False
    )
    activity_date: Mapped[date] = mapped_column(Date, primary_key=True, nullable=False)
    total_duration: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    points_earned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class StudentStats(Base, TimestampMixin):
    __tablename__ = "student_stats"

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, nullable=False
    )
    current_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_mastery_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_study_time_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_activity_date: Mapped[date | None] = mapped_column(Date, nullable=True)
