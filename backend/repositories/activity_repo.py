from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.activity import ActivityLog, DailyActivitySummary, StudentStats


class ActivityRepository:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _points_for_event(event_type: str) -> int:
        return 50 if event_type == "quiz_submitted" else 10

    def log_activity(
        self,
        *,
        student_id: UUID,
        subject: str,
        term: int,
        event_type: str,
        ref_id: str,
        duration_seconds: int,
    ) -> int:
        today = date.today()
        points = self._points_for_event(event_type)

        activity = ActivityLog(
            student_id=student_id,
            subject=subject,
            term=term,
            event_type=event_type,
            ref_id=ref_id,
            duration_seconds=duration_seconds,
        )
        self.db.add(activity)

        daily = self.db.get(DailyActivitySummary, (student_id, today))
        if daily is None:
            daily = DailyActivitySummary(
                student_id=student_id,
                activity_date=today,
                total_duration=0,
                points_earned=0,
            )
            self.db.add(daily)

        daily.total_duration += duration_seconds
        daily.points_earned += points

        stats = self.db.get(StudentStats, student_id)
        if stats is None:
            stats = StudentStats(
                student_id=student_id,
                current_streak=0,
                max_streak=0,
                total_mastery_points=0,
                total_study_time_seconds=0,
                last_activity_date=None,
            )
            self.db.add(stats)
            self.db.flush()

        if stats.last_activity_date == today:
            pass
        elif stats.last_activity_date == today - timedelta(days=1):
            stats.current_streak += 1
        else:
            stats.current_streak = 1

        stats.max_streak = max(stats.max_streak, stats.current_streak)
        stats.total_mastery_points += points
        stats.total_study_time_seconds += duration_seconds
        stats.last_activity_date = today

        self.db.commit()
        return points

    def get_student_stats(self, student_id: UUID) -> StudentStats | None:
        return self.db.get(StudentStats, student_id)

    def get_leaderboard(self, limit: int) -> list[StudentStats]:
        stmt = (
            select(StudentStats)
            .order_by(StudentStats.total_mastery_points.desc(), StudentStats.student_id.asc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())
