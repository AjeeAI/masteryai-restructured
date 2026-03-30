"""Mastery dashboard endpoint."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.repositories.mastery_repo import MasteryRepository
from backend.schemas.mastery_schema import MasteryDashboardOut, MasteryView
from backend.services.mastery_dashboard_service import MasteryDashboardService

router = APIRouter(prefix="/learning", tags=["Mastery"])


def _service(db: Session) -> MasteryDashboardService:
    return MasteryDashboardService(MasteryRepository(db))


@router.get("/mastery", response_model=MasteryDashboardOut, status_code=status.HTTP_200_OK)
def get_mastery_dashboard(
    student_id: UUID,
    subject: Literal["math", "english", "civic"],
    term: int = Query(..., ge=1, le=3),
    view: MasteryView = "concept",
    persist_snapshot: bool = Query(default=True),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return student mastery dashboard for a given subject/term scope.

    Includes mastery list, streak metrics, and earned badge names.
    """
    if student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="student_id must match authenticated user id",
        )

    try:
        return _service(db).get_dashboard(
            student_id=student_id,
            subject=subject,
            term=term,
            view=view,
            persist_snapshot=persist_snapshot,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
