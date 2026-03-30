from sqlalchemy.orm import Session
from uuid import UUID
from fastapi import HTTPException, status

from backend.repositories.student_repo import StudentRepository
from backend.schemas.student_schema import (
    StudentProfileSetupRequest,
    StudentProfileResponse,
    StudentProfileStatusResponse,
    StudentProfileUpdateRequest,
    LearningPreferenceUpdateRequest,
    LearningPreferenceResponse,
)

class StudentService:
    def __init__(self, db: Session):
        self.repo = StudentRepository(db)

    def setup_profile(self, request: StudentProfileSetupRequest) -> StudentProfileResponse:
        """Create initial student profile and optional initial preferences."""
        # Check if profile already exists
        existing = self.repo.get_profile(request.student_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Profile already exists for this student"
            )

        # Validate that all subjects exist in the database
        subject_slugs = [s.value for s in request.subjects]
        try:
            self.repo.validate_subjects_exist(subject_slugs)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

        student = self.repo.create_profile(request)
        return self._to_profile_response(student)

    def get_profile(self, student_id: UUID) -> StudentProfileResponse:
        """Get profile by the student_id (from auth token)."""
        student = self.repo.get_profile(student_id)
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student profile not found"
            )
        return self._to_profile_response(student)

    def get_profile_status(self, student_id: UUID) -> StudentProfileStatusResponse:
        """Return simple onboarding status without raising 404 for missing profile."""
        student = self.repo.get_profile(student_id)
        return StudentProfileStatusResponse(
            has_profile=student is not None,
            user_id=student_id,
        )

    def update_profile(self, student_id: UUID, updates: StudentProfileUpdateRequest) -> StudentProfileResponse:
        """Update profile fields and optional preferences in one request."""
        # Validate subjects if they are being updated
        if updates.subjects is not None:
            subject_slugs = [s.value for s in updates.subjects]
            try:
                self.repo.validate_subjects_exist(subject_slugs)
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e)
                )

        student = self.repo.update_profile(student_id, updates)
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student profile not found"
            )
        return self._to_profile_response(student)

    def update_preferences(self, user_id: UUID, updates: LearningPreferenceUpdateRequest) -> LearningPreferenceResponse:
        """Update learning preferences for a user (user_id = student_id from auth)."""
        pref = self.repo.update_preferences(user_id, updates)
        if not pref:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student profile not found"
            )
        return self._to_preference_response(pref)

    # ----- helper mapping methods -----

    def _to_profile_response(self, student) -> StudentProfileResponse:
        """Convert StudentProfile ORM object to response schema."""
        active_subjects = self.repo.get_active_subjects(student.id)

        preferences = None
        if student.preference:
            preferences = self._to_preference_response(student.preference)

        return StudentProfileResponse(
            id=student.id,
            user_id=student.student_id,
            sss_level=student.sss_level,
            current_term=student.active_term,
            subjects=active_subjects,
            preferences=preferences,
            created_at=student.created_at,
            updated_at=student.updated_at
        )

    def _to_preference_response(self, pref) -> LearningPreferenceResponse:
        """Convert LearningPreference ORM object to response schema."""
        return LearningPreferenceResponse(
            student_id=pref.student_profile.student_id,
            explanation_depth=pref.explanation_depth,
            examples_first=pref.examples_first,
            pace=pref.pace,
            updated_at=pref.updated_at
        )
