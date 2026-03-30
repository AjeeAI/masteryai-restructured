from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.schemas.dashboard_schema import DashboardBootstrapOut, StudentPathBriefingOut
from backend.services.dashboard_experience_service import DashboardExperienceError, DashboardExperienceService

router = APIRouter(prefix="/learning/dashboard", tags=["Dashboard Learning"])


@router.get("/bootstrap", response_model=DashboardBootstrapOut)
def get_dashboard_bootstrap(
    student_id: UUID = Query(...),
    subject: Literal["math", "english", "civic"] | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if student_id != current_user.id:
        raise HTTPException(status_code=403, detail="student_id must match authenticated user id")

    try:
        return DashboardExperienceService(db).bootstrap(student_id=student_id, subject=subject)
    except DashboardExperienceError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/briefing/export", response_model=StudentPathBriefingOut)
def get_student_path_briefing(
    student_id: UUID = Query(...),
    subject: Literal["math", "english", "civic"] | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if student_id != current_user.id:
        raise HTTPException(status_code=403, detail="student_id must match authenticated user id")

    try:
        return DashboardExperienceService(db).get_path_briefing_export(student_id=student_id, subject=subject)
    except DashboardExperienceError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
