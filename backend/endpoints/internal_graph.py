"""Internal Graph contract endpoints.

Service-to-service APIs used by orchestration components to read and update
concept mastery context. Not intended for direct frontend usage.
"""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.internal_service_auth import require_internal_service_key
from backend.schemas.internal_graph_schema import (
    InternalGraphContextOut,
    InternalGraphUpdateIn,
    InternalGraphUpdateOut,
)
from backend.services.graph_client_service import GraphClientValidationError, graph_client_service

router = APIRouter(
    prefix="/internal/graph",
    tags=["Internal Graph APIs"],
    dependencies=[Depends(require_internal_service_key)],
)


@router.get("/context", response_model=InternalGraphContextOut)
def get_graph_context(
    student_id: UUID,
    subject: Literal["math", "english", "civic"],
    sss_level: Literal["SSS1", "SSS2", "SSS3"],
    term: int = Query(..., ge=1, le=3),
    topic_id: str | None = None,
    db: Session = Depends(get_db),
):
    """Fetch graph-derived learning context for a student scope.

    Returns mastery slice, prerequisite edges, unlocked nodes, and summary score.
    """
    try:
        return graph_client_service.get_student_graph_context(
            db,
            student_id=student_id,
            subject=subject,
            sss_level=sss_level,
            term=term,
            topic_id=topic_id,
        )
    except GraphClientValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/update-mastery", response_model=InternalGraphUpdateOut)
def update_graph_mastery(payload: InternalGraphUpdateIn, db: Session = Depends(get_db)):
    """Apply concept mastery updates from quiz/assessment outcomes.

    Accepts normalized concept breakdown payload used across services.
    """
    try:
        return graph_client_service.push_mastery_update(db, payload=payload)
    except GraphClientValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
