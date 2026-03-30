from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.schemas.course_schema import CourseBootstrapOut
from backend.services.course_experience_service import CourseExperienceError, CourseExperienceService

router = APIRouter(prefix="/learning/course", tags=["Course Learning"])


@router.get("/bootstrap", response_model=CourseBootstrapOut)
def get_course_bootstrap(
    student_id: UUID = Query(...),
    subject: Literal["math", "english", "civic"] = Query(...),
    term: int = Query(..., ge=1, le=3),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if student_id != current_user.id:
        raise HTTPException(status_code=403, detail="student_id must match authenticated user id")

    try:
        return CourseExperienceService(db).bootstrap(
            student_id=student_id,
            subject=subject,
            term=int(term),
        )
    except CourseExperienceError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/latest-intervention", response_model=CourseBootstrapOut)
def get_latest_intervention_bootstrap(
    student_id: UUID = Query(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if student_id != current_user.id:
        raise HTTPException(status_code=403, detail="student_id must match authenticated user id")

    try:
        payload = CourseExperienceService(db).latest_intervention_bootstrap(student_id=student_id)
    except CourseExperienceError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if payload is None:
        raise HTTPException(status_code=404, detail="No recent intervention found for this student.")
    return payload
