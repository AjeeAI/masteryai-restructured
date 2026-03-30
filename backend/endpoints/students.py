"""Student onboarding and learning-scope profile endpoints.

These routes manage curriculum scope (SSS level, term, subjects) and
student learning preferences.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

from backend.core.database import get_db
from backend.services.student_service import StudentService
from backend.schemas.student_schema import (
    StudentProfileSetupRequest,
    StudentProfileResponse,
    StudentProfileStatusResponse,
    StudentProfileUpdateRequest,
    LearningPreferenceUpdateRequest,
    LearningPreferenceResponse,
)
from backend.core.auth import get_current_user  # Assumes auth team provides this

router = APIRouter(prefix="/students", tags=["Students"])


@router.post("/profile/setup", response_model=StudentProfileResponse)
async def setup_profile(
    request: StudentProfileSetupRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),  # Ensures user is authenticated
):
    """Create the initial student learning profile.

    This endpoint is usually called once after registration/login.
    It accepts initial curriculum scope and optional learning preferences.
    Security rule: `request.student_id` must match authenticated user id.
    """
    if request.student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="student_id must match authenticated user id",
        )

    service = StudentService(db)
    return service.setup_profile(request)


@router.get("/profile", response_model=StudentProfileResponse)
async def get_profile(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return the authenticated student's profile and active learning scope.

    Used by dashboard/settings pages to preload profile data.
    """
    service = StudentService(db)
    return service.get_profile(current_user.id)


@router.get("/profile/status", response_model=StudentProfileStatusResponse)
async def get_profile_status(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return onboarding profile presence as a stable 200 response.

    This avoids using 404 for normal onboarding flow checks on the frontend.
    """
    service = StudentService(db)
    return service.get_profile_status(current_user.id)


@router.put("/profile", response_model=StudentProfileResponse)
async def update_profile(
    updates: StudentProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Update the authenticated student's profile scope fields.

    Supports changing SSS level, active term, enrolled subjects,
    and optional learning preferences in one payload.
    """
    service = StudentService(db)
    return service.update_profile(current_user.id, updates)


@router.put("/users/{user_id}/preferences", response_model=LearningPreferenceResponse)
async def update_preferences(
    user_id: UUID,
    updates: LearningPreferenceUpdateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Legacy-compatible path for updating learning preferences.

    Security rule: users can only update their own preference record.
    """
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this user's preferences",
        )
    service = StudentService(db)
    return service.update_preferences(user_id, updates)
