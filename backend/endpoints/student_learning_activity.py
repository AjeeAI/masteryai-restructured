"""Student activity tracking and simple gamification endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.repositories.activity_repo import ActivityRepository
from backend.schemas.activity_schema import (
    ActivityLogCreate,
    ActivityLogOut,
    LeaderboardEntryOut,
    StudentStatsOut,
)
from backend.services.activity_service import ActivityService

learning_router = APIRouter(prefix="/learning", tags=["Learning Activity"])
student_router = APIRouter(prefix="/students", tags=["Student Stats"])


def _service(db: Session) -> ActivityService:
    return ActivityService(ActivityRepository(db))


@learning_router.post("/activity/log", response_model=ActivityLogOut, status_code=status.HTTP_201_CREATED)
def log_activity(
    payload: ActivityLogCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Log a scoped student activity event.

    Events are used for streak/points accumulation and engagement analytics.
    Security rule: payload student id must match authenticated user id.
    """
    if payload.student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="student_id must match authenticated user id",
        )

    return _service(db).log_activity(payload)


@student_router.get("/stats", response_model=StudentStatsOut)
def get_student_stats(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return current student's KPI stats (streak, points, study time)."""
    return _service(db).get_student_stats(current_user.id)


@student_router.get("/leaderboard", response_model=list[LeaderboardEntryOut])
def get_leaderboard(
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return ranked leaderboard entries ordered by mastery points.

    Auth is currently required; role-based filters can be tightened later.
    """
    # Auth required for now; role filtering can be refined in teacher/admin sections.
    _ = current_user
    return _service(db).get_leaderboard(limit)
