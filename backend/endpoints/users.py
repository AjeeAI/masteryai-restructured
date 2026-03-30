"""User identity profile endpoints.

These routes expose personal profile fields (name/avatar/phone) for
authenticated users, plus the normalized preference route.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.repositories.user_repo import UserRepository
from backend.schemas.student_schema import LearningPreferenceResponse, LearningPreferenceUpdateRequest
from backend.schemas.user_schema import UserProfileOut, UserProfileUpdateIn
from backend.services.student_service import StudentService
from backend.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


def _user_service(db: Session) -> UserService:
    return UserService(UserRepository(db))


@router.get("/me", response_model=UserProfileOut)
def get_my_profile(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return identity profile for the authenticated user.

    Used by dashboard header/account settings pages.
    """
    return _user_service(db).get_me(current_user.id)


@router.put("/me", response_model=UserProfileOut)
def update_my_profile(
    payload: UserProfileUpdateIn,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Update identity profile fields for the authenticated user.

    Supports first/last/display name, phone, and avatar URL updates.
    """
    return _user_service(db).update_me(current_user.id, payload)


@router.put("/{user_id}/preferences", response_model=LearningPreferenceResponse)
def update_preferences(
    user_id: UUID,
    updates: LearningPreferenceUpdateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Update learning preferences via canonical `/users` route.

    This route mirrors `/students/users/{user_id}/preferences` but should be
    preferred by frontend integrations going forward.
    """
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this user's preferences",
        )

    return StudentService(db).update_preferences(user_id, updates)
