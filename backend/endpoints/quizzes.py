"""Quiz lifecycle endpoints.

Public APIs for quiz generation, submission, and post-attempt results.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.schemas.quiz_schema import (
    QuizGenerateRequest,
    QuizGenerateResponse,
    QuizSubmitRequest,
    QuizSubmitResponse,
    QuizResultsResponse,
)
from backend.services.quiz_generate_service import QuizGenerateService
from backend.services.quiz_submit_service import QuizSubmitService
from backend.services.quiz_results_service import QuizResultsService


router = APIRouter(prefix="/learning/quizzes", tags=["Quizzes"])


@router.post(
    "/generate",
    response_model=QuizGenerateResponse,
    status_code=status.HTTP_200_OK,
)
async def generate_quiz(
    payload: QuizGenerateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Generate a targeted quiz for a student and persist it.

    Uses AI-core question generation contract and stores normalized quiz records.
    """
    if payload.student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="student_id must match authenticated user id",
        )
    service = QuizGenerateService(db)
    return await service.generate_quiz(payload)


@router.post(
    "/{quiz_id}/submit",
    response_model=QuizSubmitResponse,
)
async def submit_quiz(
    quiz_id: UUID,
    payload: QuizSubmitRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Submit answers for a generated quiz and return scored attempt summary.

    This endpoint also triggers activity logging and graph mastery update push.
    """
    if payload.student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="student_id must match authenticated user id",
        )
    service = QuizSubmitService(db)
    return await service.submit_quiz(quiz_id=quiz_id, request=payload)


@router.get(
    "/{quiz_id}/results",
    response_model=QuizResultsResponse,
)
async def get_quiz_results(
    quiz_id: UUID,
    student_id: UUID,
    attempt_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return scored quiz results with concept breakdown and tutor insights.

    Requires `quiz_id`, `student_id`, and `attempt_id` to resolve a unique attempt.
    """
    if student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="student_id must match authenticated user id",
        )
    service = QuizResultsService(db)
    return await service.get_results(
        quiz_id=quiz_id,
        student_id=student_id,
        attempt_id=attempt_id,
    )
