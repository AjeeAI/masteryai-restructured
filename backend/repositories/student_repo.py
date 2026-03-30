from sqlalchemy.orm import Session
from sqlalchemy import and_
from uuid import UUID
from typing import List, Optional
from datetime import datetime, timezone

from backend.models.student import StudentProfile, StudentSubject, LearningPreference
from backend.models.subject import Subject
from backend.schemas.student_schema import (
    StudentProfileSetupRequest,
    StudentProfileUpdateRequest,
    LearningPreferenceUpdateRequest,
)

class StudentRepository:
    def __init__(self, db: Session):
        self.db = db

    def _get_subject_id_by_slug(self, slug: str) -> Optional[UUID]:
        """Helper to get subject UUID from its slug."""
        subject = self.db.query(Subject).filter(Subject.slug == slug).first()
        return subject.id if subject else None

    def validate_subjects_exist(self, subject_slugs: List[str]) -> bool:
        """
        Check if all given subject slugs exist in the subjects table.
        Raises ValueError with missing slugs if any not found.
        """
        existing = self.db.query(Subject.slug).filter(Subject.slug.in_(subject_slugs)).all()
        existing_slugs = {slug for (slug,) in existing}
        missing = set(subject_slugs) - existing_slugs
        if missing:
            raise ValueError(f"Subjects not found: {', '.join(missing)}")
        return True

    def create_profile(self, request: StudentProfileSetupRequest) -> StudentProfile:
        """Create a new student profile (assumes subjects already validated)."""
        student = StudentProfile(
            student_id=request.student_id,
            sss_level=request.sss_level.value,
            active_term=request.term.value,
        )
        self.db.add(student)
        self.db.flush()

        # Add subjects - lookup UUID from slug (already validated, so all should exist)
        for subject_enum in request.subjects:
            subject_id = self._get_subject_id_by_slug(subject_enum.value)
            # subject_id must exist because we validated
            student_subject = StudentSubject(
                student_profile_id=student.id,
                subject_id=subject_id,
            )
            self.db.add(student_subject)

        # Create preferences from setup payload or defaults.
        preferences = LearningPreference(student_profile_id=student.id)
        if request.preferences:
            if request.preferences.explanation_depth is not None:
                preferences.explanation_depth = request.preferences.explanation_depth.value
            if request.preferences.examples_first is not None:
                preferences.examples_first = request.preferences.examples_first
            if request.preferences.pace is not None:
                preferences.pace = request.preferences.pace.value
        self.db.add(preferences)

        self.db.commit()
        self.db.refresh(student)
        return student

    def get_profile(self, student_id: UUID) -> Optional[StudentProfile]:
        """Get student profile by the linking student_id (from auth)"""
        return self.db.query(StudentProfile).filter(StudentProfile.student_id == student_id).first()

    def get_profile_by_id(self, profile_id: UUID) -> Optional[StudentProfile]:
        """Get student profile by its internal UUID (if needed)"""
        return self.db.query(StudentProfile).filter(StudentProfile.id == profile_id).first()

    def update_profile(self, student_id: UUID, updates: StudentProfileUpdateRequest) -> Optional[StudentProfile]:
        """Update student profile (assumes subjects already validated if provided)."""
        student = self.get_profile(student_id)
        if not student:
            return None

        if updates.sss_level:
            student.sss_level = updates.sss_level.value
        if updates.current_term:
            student.active_term = updates.current_term.value

        # Update subjects if provided
        if updates.subjects is not None:
            # Delete all existing subject associations
            self.db.query(StudentSubject).filter(
                StudentSubject.student_profile_id == student.id
            ).delete()

            # Add new ones (already validated)
            for subject_enum in updates.subjects:
                subject_id = self._get_subject_id_by_slug(subject_enum.value)
                new_subject = StudentSubject(
                    student_profile_id=student.id,
                    subject_id=subject_id,
                )
                self.db.add(new_subject)

        # Apply preferences in the same update flow when provided.
        if updates.preferences is not None:
            pref = self.db.query(LearningPreference).filter(
                LearningPreference.student_profile_id == student.id
            ).first()
            if not pref:
                pref = LearningPreference(student_profile_id=student.id)
                self.db.add(pref)

            if updates.preferences.explanation_depth is not None:
                pref.explanation_depth = updates.preferences.explanation_depth.value
            if updates.preferences.examples_first is not None:
                pref.examples_first = updates.preferences.examples_first
            if updates.preferences.pace is not None:
                pref.pace = updates.preferences.pace.value
            pref.updated_at = datetime.now(timezone.utc)

        student.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(student)
        return student

    def update_preferences(self, student_id: UUID, updates: LearningPreferenceUpdateRequest) -> Optional[LearningPreference]:
        """Update learning preferences (by student_id)"""
        student = self.get_profile(student_id)
        if not student:
            return None

        pref = self.db.query(LearningPreference).filter(
            LearningPreference.student_profile_id == student.id
        ).first()
        if not pref:
            pref = LearningPreference(student_profile_id=student.id)
            self.db.add(pref)

        if updates.explanation_depth:
            pref.explanation_depth = updates.explanation_depth.value
        if updates.examples_first is not None:
            pref.examples_first = updates.examples_first
        if updates.pace:
            pref.pace = updates.pace.value

        pref.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(pref)
        return pref

    def get_active_subjects(self, profile_id: UUID) -> List[str]:
        """Get active subject slugs for a student profile."""
        results = (
            self.db.query(Subject.slug)
            .join(StudentSubject, StudentSubject.subject_id == Subject.id)
            .filter(StudentSubject.student_profile_id == profile_id)
            .all()
        )
        return [row.slug for row in results]
