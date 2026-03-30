"""Diagnostic assessment endpoints.

Implements stateful baseline diagnostic flow:
`status -> start -> submit -> mastery baseline update`.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.schemas.diagnostic_schema import (
    DiagnosticStatusOut,
    DiagnosticStartIn,
    DiagnosticStartOut,
    DiagnosticSubmitIn,
    DiagnosticSubmitOut,
)
from backend.services.diagnostic_service import (
    DiagnosticAlreadySubmittedError,
    DiagnosticNotFoundError,
    DiagnosticValidationError,
    diagnostic_service,
)

router = APIRouter(prefix="/learning/diagnostic", tags=["Learning Diagnostic"])


@router.get("/status", response_model=DiagnosticStatusOut)
def diagnostic_status(
    student_id: UUID = Query(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="student_id must match authenticated user id",
        )
    try:
        return diagnostic_service.get_diagnostic_status(db=db, student_id=student_id)
    except DiagnosticValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/start", response_model=DiagnosticStartOut, status_code=status.HTTP_201_CREATED)
def start_diagnostic(
    payload: DiagnosticStartIn,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Start a diagnostic session for a scoped student/subject/term.

    Returns a diagnostic id, concept targets, and generated diagnostic questions.
    """
    if payload.student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="student_id must match authenticated user id",
        )
    try:
        return diagnostic_service.create_diagnostic_session(db=db, payload=payload)
    except DiagnosticValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/submit", response_model=DiagnosticSubmitOut)
def submit_diagnostic(
    payload: DiagnosticSubmitIn,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Submit diagnostic answers and compute baseline mastery updates.

    Returns concept-level score changes and recommended starting topic id.
    """
    if payload.student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="student_id must match authenticated user id",
        )
    try:
        return diagnostic_service.process_diagnostic_submission(db=db, payload=payload)
    except DiagnosticValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except DiagnosticNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except DiagnosticAlreadySubmittedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
