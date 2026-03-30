from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from uuid import UUID

from backend.repositories.teacher_repo import TeacherRepository
from backend.schemas.teacher_schema import (
    TeacherAssignmentCreateIn,
    TeacherAssignmentOut,
    TeacherBulkAssignmentCreateIn,
    TeacherBulkAssignmentOut,
    TeacherBulkInterventionCreateIn,
    TeacherBulkInterventionOut,
    TeacherClassCreateIn,
    TeacherClassEnrollIn,
    TeacherClassEnrollOut,
    TeacherClassListOut,
    TeacherClassOut,
    TeacherInterventionCreateIn,
    TeacherInterventionUpdateIn,
    TeacherInterventionOut,
)


class TeacherServiceValidationError(ValueError):
    pass


class TeacherServiceUnauthorizedError(PermissionError):
    pass


class TeacherServiceNotFoundError(LookupError):
    pass


class TeacherServiceConflictError(ValueError):
    pass


class TeacherService:
    def __init__(self, repo: TeacherRepository):
        self.repo = repo

    def _require_teacher_user(self, teacher_id: UUID):
        user = self.repo.get_user(teacher_id)
        if not user:
            raise TeacherServiceNotFoundError("Teacher user not found.")
        if not user.is_active:
            raise TeacherServiceUnauthorizedError("Teacher account is inactive.")
        if user.role not in {"teacher", "admin"}:
            raise TeacherServiceUnauthorizedError("Only teacher/admin role can access teacher operations.")
        return user

    def _require_teacher_class(self, *, teacher_id: UUID, class_id: UUID):
        row = self.repo.get_teacher_class(teacher_id=teacher_id, class_id=class_id)
        if not row:
            raise TeacherServiceNotFoundError("Class not found for this teacher.")
        return row

    @staticmethod
    def _to_class_out(row, enrolled_count: int) -> TeacherClassOut:
        return TeacherClassOut(
            id=row.id,
            teacher_id=row.teacher_id,
            name=row.name,
            description=row.description,
            subject=row.subject,
            sss_level=row.sss_level,
            term=row.term,
            is_active=row.is_active,
            enrolled_count=enrolled_count,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def list_classes(self, *, teacher_id: UUID) -> TeacherClassListOut:
        self._require_teacher_user(teacher_id)
        rows = self.repo.list_teacher_classes(teacher_id=teacher_id)
        return TeacherClassListOut(classes=[self._to_class_out(cls, count) for cls, count in rows])

    def create_class(self, *, teacher_id: UUID, payload: TeacherClassCreateIn) -> TeacherClassOut:
        self._require_teacher_user(teacher_id)

        try:
            row = self.repo.create_class(
                teacher_id=teacher_id,
                name=payload.name.strip(),
                description=payload.description.strip() if payload.description else None,
                subject=payload.subject,
                sss_level=payload.sss_level,
                term=payload.term,
            )
        except IntegrityError as exc:
            raise TeacherServiceConflictError(
                "A class with the same name/scope already exists for this teacher."
            ) from exc

        return self._to_class_out(row, enrolled_count=0)

    def enroll_students(
        self,
        *,
        teacher_id: UUID,
        class_id: UUID,
        payload: TeacherClassEnrollIn,
    ) -> TeacherClassEnrollOut:
        self._require_teacher_user(teacher_id)
        self._require_teacher_class(teacher_id=teacher_id, class_id=class_id)

        unique_student_ids = list(dict.fromkeys(payload.student_ids))
        users_map = self.repo.get_users_by_ids(unique_student_ids)

        missing_ids = [student_id for student_id in unique_student_ids if student_id not in users_map]
        if missing_ids:
            raise TeacherServiceValidationError(f"Unknown student_ids: {', '.join(map(str, missing_ids))}")

        non_student_ids = [
            student_id
            for student_id in unique_student_ids
            if users_map[student_id].role != "student" or not users_map[student_id].is_active
        ]
        if non_student_ids:
            raise TeacherServiceValidationError(
                f"Only active student accounts can be enrolled: {', '.join(map(str, non_student_ids))}"
            )

        enrolled_now, already_active = self.repo.upsert_enrollments(
            class_id=class_id,
            student_ids=unique_student_ids,
        )
        total = self.repo.count_active_enrollments(class_id=class_id)

        return TeacherClassEnrollOut(
            class_id=class_id,
            enrolled_student_ids=enrolled_now,
            already_enrolled_student_ids=already_active,
            total_enrolled=total,
        )

    def remove_student_enrollment(self, *, teacher_id: UUID, class_id: UUID, student_id: UUID) -> bool:
        self._require_teacher_user(teacher_id)
        self._require_teacher_class(teacher_id=teacher_id, class_id=class_id)
        return self.repo.remove_enrollment(class_id=class_id, student_id=student_id)

    def create_assignment(self, *, teacher_id: UUID, payload: TeacherAssignmentCreateIn) -> TeacherAssignmentOut:
        self._require_teacher_user(teacher_id)

        teacher_class = None
        if payload.class_id:
            teacher_class = self._require_teacher_class(teacher_id=teacher_id, class_id=payload.class_id)
            if (
                payload.subject != teacher_class.subject
                or payload.sss_level != teacher_class.sss_level
                or payload.term != teacher_class.term
            ):
                raise TeacherServiceValidationError(
                    "Assignment scope (subject/sss_level/term) must match target class scope."
                )

        if payload.student_id:
            target_user = self.repo.get_user(payload.student_id)
            if not target_user or target_user.role != "student" or not target_user.is_active:
                raise TeacherServiceValidationError("Assignment target student is invalid or inactive.")
            if teacher_class:
                active_students = set(self.repo.get_active_student_ids(class_id=teacher_class.id))
                if payload.student_id not in active_students:
                    raise TeacherServiceValidationError(
                        "Target student is not actively enrolled in the selected class."
                    )

        if payload.class_id is None and payload.student_id is None:
            raise TeacherServiceValidationError("At least one target is required: class_id or student_id.")

        row = self.repo.create_assignment(
            {
                "teacher_id": teacher_id,
                "class_id": payload.class_id,
                "student_id": payload.student_id,
                "assignment_type": payload.assignment_type,
                "concept_id": str(payload.concept_id).strip() if payload.concept_id else None,
                "concept_label": payload.concept_label.strip() if payload.concept_label else None,
                "ref_id": payload.ref_id.strip(),
                "title": payload.title.strip(),
                "instructions": payload.instructions.strip() if payload.instructions else None,
                "subject": payload.subject,
                "sss_level": payload.sss_level,
                "term": payload.term,
                "due_at": payload.due_at,
            }
        )
        return TeacherAssignmentOut(
            id=row.id,
            teacher_id=row.teacher_id,
            class_id=row.class_id,
            student_id=row.student_id,
            assignment_type=row.assignment_type,
            concept_id=row.concept_id,
            concept_label=row.concept_label,
            ref_id=row.ref_id,
            title=row.title,
            instructions=row.instructions,
            subject=row.subject,
            sss_level=row.sss_level,
            term=row.term,
            due_at=row.due_at,
            status=row.status,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def create_bulk_assignments(
        self,
        *,
        teacher_id: UUID,
        payload: TeacherBulkAssignmentCreateIn,
    ) -> TeacherBulkAssignmentOut:
        self._require_teacher_user(teacher_id)

        teacher_class = None
        if payload.class_id:
            teacher_class = self._require_teacher_class(teacher_id=teacher_id, class_id=payload.class_id)
            if (
                payload.subject != teacher_class.subject
                or payload.sss_level != teacher_class.sss_level
                or payload.term != teacher_class.term
            ):
                raise TeacherServiceValidationError(
                    "Assignment scope (subject/sss_level/term) must match target class scope."
                )

        unique_student_ids = list(dict.fromkeys(payload.student_ids))
        users_map = self.repo.get_users_by_ids(unique_student_ids)
        missing_ids = [student_id for student_id in unique_student_ids if student_id not in users_map]
        if missing_ids:
            raise TeacherServiceValidationError(f"Unknown student_ids: {', '.join(map(str, missing_ids))}")

        invalid_student_ids = [
            student_id
            for student_id in unique_student_ids
            if users_map[student_id].role != "student" or not users_map[student_id].is_active
        ]
        if invalid_student_ids:
            raise TeacherServiceValidationError(
                f"Only active student accounts can receive assignments: {', '.join(map(str, invalid_student_ids))}"
            )

        if teacher_class:
            active_students = set(self.repo.get_active_student_ids(class_id=teacher_class.id))
            unenrolled_ids = [student_id for student_id in unique_student_ids if student_id not in active_students]
            if unenrolled_ids:
                raise TeacherServiceValidationError(
                    "Some target students are not actively enrolled in the selected class."
                )

        rows = self.repo.create_assignments(
            [
                {
                    "teacher_id": teacher_id,
                    "class_id": payload.class_id,
                    "student_id": student_id,
                    "assignment_type": payload.assignment_type,
                    "concept_id": str(payload.concept_id).strip() if payload.concept_id else None,
                    "concept_label": payload.concept_label.strip() if payload.concept_label else None,
                    "ref_id": payload.ref_id.strip(),
                    "title": payload.title.strip(),
                    "instructions": payload.instructions.strip() if payload.instructions else None,
                    "subject": payload.subject,
                    "sss_level": payload.sss_level,
                    "term": payload.term,
                    "due_at": payload.due_at,
                }
                for student_id in unique_student_ids
            ]
        )
        return TeacherBulkAssignmentOut(
            created_count=len(rows),
            student_ids=[row.student_id for row in rows],
            assignment_ids=[row.id for row in rows],
        )

    def create_intervention(
        self,
        *,
        teacher_id: UUID,
        payload: TeacherInterventionCreateIn,
    ) -> TeacherInterventionOut:
        self._require_teacher_user(teacher_id)

        target_student = self.repo.get_user(payload.student_id)
        if not target_student or target_student.role != "student":
            raise TeacherServiceValidationError("Intervention target must be a valid student account.")

        teacher_class = None
        if payload.class_id:
            teacher_class = self._require_teacher_class(teacher_id=teacher_id, class_id=payload.class_id)
            if (
                payload.subject != teacher_class.subject
                or payload.sss_level != teacher_class.sss_level
                or payload.term != teacher_class.term
            ):
                raise TeacherServiceValidationError(
                    "Intervention scope (subject/sss_level/term) must match target class scope."
                )
            active_students = set(self.repo.get_active_student_ids(class_id=teacher_class.id))
            if payload.student_id not in active_students:
                raise TeacherServiceValidationError("Target student is not actively enrolled in the selected class.")

        row = self.repo.create_intervention(
            {
                "teacher_id": teacher_id,
                "class_id": payload.class_id,
                "student_id": payload.student_id,
                "intervention_type": payload.intervention_type,
                "concept_id": str(payload.concept_id).strip() if payload.concept_id else None,
                "concept_label": payload.concept_label.strip() if payload.concept_label else None,
                "severity": payload.severity,
                "subject": payload.subject,
                "sss_level": payload.sss_level,
                "term": payload.term,
                "notes": payload.notes.strip(),
                "action_plan": payload.action_plan.strip() if payload.action_plan else None,
            }
        )
        return TeacherInterventionOut(
            id=row.id,
            teacher_id=row.teacher_id,
            class_id=row.class_id,
            student_id=row.student_id,
            intervention_type=row.intervention_type,
            concept_id=row.concept_id,
            concept_label=row.concept_label,
            severity=row.severity,
            subject=row.subject,
            sss_level=row.sss_level,
            term=row.term,
            notes=row.notes,
            action_plan=row.action_plan,
            status=row.status,
            resolved_at=row.resolved_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def create_bulk_interventions(
        self,
        *,
        teacher_id: UUID,
        payload: TeacherBulkInterventionCreateIn,
    ) -> TeacherBulkInterventionOut:
        self._require_teacher_user(teacher_id)

        teacher_class = None
        if payload.class_id:
            teacher_class = self._require_teacher_class(teacher_id=teacher_id, class_id=payload.class_id)
            if (
                payload.subject != teacher_class.subject
                or payload.sss_level != teacher_class.sss_level
                or payload.term != teacher_class.term
            ):
                raise TeacherServiceValidationError(
                    "Intervention scope (subject/sss_level/term) must match target class scope."
                )

        unique_student_ids = list(dict.fromkeys(payload.student_ids))
        users_map = self.repo.get_users_by_ids(unique_student_ids)
        missing_ids = [student_id for student_id in unique_student_ids if student_id not in users_map]
        if missing_ids:
            raise TeacherServiceValidationError(f"Unknown student_ids: {', '.join(map(str, missing_ids))}")

        invalid_student_ids = [
            student_id
            for student_id in unique_student_ids
            if users_map[student_id].role != "student" or not users_map[student_id].is_active
        ]
        if invalid_student_ids:
            raise TeacherServiceValidationError(
                f"Only active student accounts can receive interventions: {', '.join(map(str, invalid_student_ids))}"
            )

        if teacher_class:
            active_students = set(self.repo.get_active_student_ids(class_id=teacher_class.id))
            unenrolled_ids = [student_id for student_id in unique_student_ids if student_id not in active_students]
            if unenrolled_ids:
                raise TeacherServiceValidationError(
                    "Some target students are not actively enrolled in the selected class."
                )

        rows = self.repo.create_interventions(
            [
                {
                    "teacher_id": teacher_id,
                    "class_id": payload.class_id,
                    "student_id": student_id,
                    "intervention_type": payload.intervention_type,
                    "concept_id": str(payload.concept_id).strip() if payload.concept_id else None,
                    "concept_label": payload.concept_label.strip() if payload.concept_label else None,
                    "severity": payload.severity,
                    "subject": payload.subject,
                    "sss_level": payload.sss_level,
                    "term": payload.term,
                    "notes": payload.notes.strip(),
                    "action_plan": payload.action_plan.strip() if payload.action_plan else None,
                }
                for student_id in unique_student_ids
            ]
        )
        return TeacherBulkInterventionOut(
            created_count=len(rows),
            student_ids=[row.student_id for row in rows],
            intervention_ids=[row.id for row in rows],
        )

    def update_intervention(
        self,
        *,
        teacher_id: UUID,
        intervention_id: UUID,
        payload: TeacherInterventionUpdateIn,
    ) -> TeacherInterventionOut:
        self._require_teacher_user(teacher_id)
        row = self.repo.get_teacher_intervention(teacher_id=teacher_id, intervention_id=intervention_id)
        if not row:
            raise TeacherServiceNotFoundError("Intervention not found for this teacher.")

        resolved_at = datetime.now(timezone.utc) if payload.status == "resolved" else None
        updated = self.repo.update_intervention_status(
            intervention_id=intervention_id,
            status=payload.status,
            resolved_at=resolved_at,
        )
        if not updated:
            raise TeacherServiceNotFoundError("Intervention not found.")

        return TeacherInterventionOut(
            id=updated.id,
            teacher_id=updated.teacher_id,
            class_id=updated.class_id,
            student_id=updated.student_id,
            intervention_type=updated.intervention_type,
            concept_id=updated.concept_id,
            concept_label=updated.concept_label,
            severity=updated.severity,
            subject=updated.subject,
            sss_level=updated.sss_level,
            term=updated.term,
            notes=updated.notes,
            action_plan=updated.action_plan,
            status=updated.status,
            resolved_at=updated.resolved_at,
            created_at=updated.created_at,
            updated_at=updated.updated_at,
        )
