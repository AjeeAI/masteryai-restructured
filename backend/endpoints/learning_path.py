"""Adaptive learning path endpoints.

Public APIs that expose next-step recommendations and map visualization.
"""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.schemas.learning_path_schema import LearningMapVisualOut, PathNextIn, PathNextOut
from backend.services.learning_path_service import LearningPathValidationError, learning_path_service

router = APIRouter(prefix="/learning/path", tags=["Learning Path"])


@router.post("/next", response_model=PathNextOut)
def get_next_path_step(payload: PathNextIn, db: Session = Depends(get_db)):
    """Return the next recommended topic based on mastery/prerequisite logic.

    Response includes recommendation reason and prerequisite gap hints.
    """
    try:
        return learning_path_service.calculate_next_step(db=db, payload=payload)
    except LearningPathValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/map/visual", response_model=LearningMapVisualOut)
def get_learning_map_visual(
    student_id: UUID,
    subject: Literal["math", "english", "civic"],
    sss_level: Literal["SSS1", "SSS2", "SSS3"],
    term: int = Query(..., ge=1, le=3),
    view: Literal["topic", "concept"] = "topic",
    db: Session = Depends(get_db),
):
    """Return a visualizable learning map snapshot for the provided scope.

    Supports topic or concept views to power progress-map UI components.
    """
    try:
        return learning_path_service.get_learning_map_visual(
            db,
            student_id=student_id,
            subject=subject,
            sss_level=sss_level,
            term=term,
            view=view,
        )
    except LearningPathValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
