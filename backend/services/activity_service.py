from __future__ import annotations

from uuid import UUID

from backend.repositories.activity_repo import ActivityRepository
from backend.schemas.activity_schema import (
    ActivityLogCreate,
    ActivityLogOut,
    LeaderboardEntryOut,
    StudentStatsOut,
)


class ActivityService:
    def __init__(self, repo: ActivityRepository):
        self.repo = repo

    def log_activity(self, payload: ActivityLogCreate) -> ActivityLogOut:
        points = self.repo.log_activity(
            student_id=payload.student_id,
            subject=payload.subject,
            term=payload.term,
            event_type=payload.event_type,
            ref_id=payload.ref_id,
            duration_seconds=payload.duration_seconds,
        )
        return ActivityLogOut(
            status="success",
            message="Activity logged",
            points_awarded=points,
        )

    def get_student_stats(self, student_id: UUID) -> StudentStatsOut:
        stats = self.repo.get_student_stats(student_id)
        if stats is None:
            return StudentStatsOut(streak=0, mastery_points=0, study_time_seconds=0)
        return StudentStatsOut(
            streak=stats.current_streak,
            mastery_points=stats.total_mastery_points,
            study_time_seconds=stats.total_study_time_seconds,
        )

    def get_leaderboard(self, limit: int) -> list[LeaderboardEntryOut]:
        rows = self.repo.get_leaderboard(limit)
        entries: list[LeaderboardEntryOut] = []
        previous_points = None
        current_rank = 0

        for index, row in enumerate(rows, start=1):
            if previous_points != row.total_mastery_points:
                current_rank = index
            entries.append(
                LeaderboardEntryOut(
                    student_id=row.student_id,
                    total_mastery_points=row.total_mastery_points,
                    rank=current_rank,
                )
            )
            previous_points = row.total_mastery_points

        return entries
