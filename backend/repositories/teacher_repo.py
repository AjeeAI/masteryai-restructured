from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from backend.models.activity import ActivityLog
from backend.models.class_enrollment import ClassEnrollment
from backend.models.curriculum_topic_map import CurriculumTopicMap
from backend.models.curriculum_version import CurriculumVersion
from backend.models.mastery_update_event import MasteryUpdateEvent
from backend.models.student_concept_mastery import StudentConceptMastery
from backend.models.teacher_assignment import TeacherAssignment
from backend.models.teacher_class import TeacherClass
from backend.models.teacher_intervention import TeacherIntervention
from backend.models.topic import Topic
from backend.models.tutor_session import TutorSession
from backend.models.user import User


class TeacherRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_user(self, user_id: UUID) -> User | None:
        return self.db.get(User, user_id)

    def get_users_by_ids(self, user_ids: list[UUID]) -> dict[UUID, User]:
        if not user_ids:
            return {}
        rows = self.db.query(User).filter(User.id.in_(user_ids)).all()
        return {row.id: row for row in rows}

    def get_class(self, class_id: UUID) -> TeacherClass | None:
        return self.db.get(TeacherClass, class_id)

    def get_teacher_class(self, *, teacher_id: UUID, class_id: UUID) -> TeacherClass | None:
        return (
            self.db.query(TeacherClass)
            .filter(TeacherClass.id == class_id, TeacherClass.teacher_id == teacher_id)
            .first()
        )

    def list_teacher_classes(self, *, teacher_id: UUID) -> list[tuple[TeacherClass, int]]:
        active_count = func.coalesce(
            func.sum(case((ClassEnrollment.status == "active", 1), else_=0)),
            0,
        ).label("active_student_count")
        rows = (
            self.db.query(TeacherClass, active_count)
            .outerjoin(ClassEnrollment, ClassEnrollment.class_id == TeacherClass.id)
            .filter(TeacherClass.teacher_id == teacher_id)
            .group_by(TeacherClass.id)
            .order_by(TeacherClass.created_at.desc())
            .all()
        )
        return [(teacher_class, int(count or 0)) for teacher_class, count in rows]

    def create_class(
        self,
        *,
        teacher_id: UUID,
        name: str,
        description: str | None,
        subject: str,
        sss_level: str,
        term: int,
    ) -> TeacherClass:
        row = TeacherClass(
            teacher_id=teacher_id,
            name=name,
            description=description,
            subject=subject,
            sss_level=sss_level,
            term=term,
            is_active=True,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_enrollments(self, *, class_id: UUID, student_ids: list[UUID]) -> dict[UUID, ClassEnrollment]:
        if not student_ids:
            return {}
        rows = (
            self.db.query(ClassEnrollment)
            .filter(ClassEnrollment.class_id == class_id, ClassEnrollment.student_id.in_(student_ids))
            .all()
        )
        return {row.student_id: row for row in rows}

    def upsert_enrollments(self, *, class_id: UUID, student_ids: list[UUID]) -> tuple[list[UUID], list[UUID]]:
        existing = self.get_enrollments(class_id=class_id, student_ids=student_ids)
        enrolled_now: list[UUID] = []
        already_active: list[UUID] = []

        for student_id in student_ids:
            row = existing.get(student_id)
            if row:
                if row.status == "active":
                    already_active.append(student_id)
                    continue
                row.status = "active"
                enrolled_now.append(student_id)
                continue
            self.db.add(ClassEnrollment(class_id=class_id, student_id=student_id, status="active"))
            enrolled_now.append(student_id)

        self.db.commit()
        return enrolled_now, already_active

    def remove_enrollment(self, *, class_id: UUID, student_id: UUID) -> bool:
        row = (
            self.db.query(ClassEnrollment)
            .filter(
                ClassEnrollment.class_id == class_id,
                ClassEnrollment.student_id == student_id,
                ClassEnrollment.status == "active",
            )
            .first()
        )
        if not row:
            return False
        row.status = "removed"
        self.db.commit()
        return True

    def count_active_enrollments(self, *, class_id: UUID) -> int:
        count = (
            self.db.query(func.count(ClassEnrollment.id))
            .filter(
                ClassEnrollment.class_id == class_id,
                ClassEnrollment.status == "active",
            )
            .scalar()
        )
        return int(count or 0)

    def create_assignment(self, payload: dict[str, Any]) -> TeacherAssignment:
        row = TeacherAssignment(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def create_assignments(self, payloads: list[dict[str, Any]]) -> list[TeacherAssignment]:
        rows = [TeacherAssignment(**payload) for payload in payloads]
        self.db.add_all(rows)
        self.db.commit()
        for row in rows:
            self.db.refresh(row)
        return rows

    def create_intervention(self, payload: dict[str, Any]) -> TeacherIntervention:
        row = TeacherIntervention(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def create_interventions(self, payloads: list[dict[str, Any]]) -> list[TeacherIntervention]:
        rows = [TeacherIntervention(**payload) for payload in payloads]
        self.db.add_all(rows)
        self.db.commit()
        for row in rows:
            self.db.refresh(row)
        return rows

    def get_teacher_intervention(self, *, teacher_id: UUID, intervention_id: UUID) -> TeacherIntervention | None:
        return (
            self.db.query(TeacherIntervention)
            .filter(
                TeacherIntervention.id == intervention_id,
                TeacherIntervention.teacher_id == teacher_id,
            )
            .first()
        )

    def update_intervention_status(
        self,
        *,
        intervention_id: UUID,
        status: str,
        resolved_at: datetime | None,
    ) -> TeacherIntervention | None:
        row = self.db.get(TeacherIntervention, intervention_id)
        if not row:
            return None
        row.status = status
        row.resolved_at = resolved_at
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_class_interventions(
        self,
        *,
        class_id: UUID,
        subject: str,
        term: int,
        limit: int = 50,
    ) -> list[TeacherIntervention]:
        return (
            self.db.query(TeacherIntervention)
            .filter(
                TeacherIntervention.class_id == class_id,
                TeacherIntervention.subject == subject,
                TeacherIntervention.term == term,
            )
            .order_by(TeacherIntervention.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_class_assignments(
        self,
        *,
        class_id: UUID,
        subject: str,
        term: int,
        limit: int = 50,
    ) -> list[TeacherAssignment]:
        return (
            self.db.query(TeacherAssignment)
            .filter(
                TeacherAssignment.class_id == class_id,
                TeacherAssignment.subject == subject,
                TeacherAssignment.term == term,
            )
            .order_by(TeacherAssignment.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_class_assignments(
        self,
        *,
        class_id: UUID,
        subject: str,
        term: int,
        limit: int = 50,
    ) -> list[TeacherAssignment]:
        return (
            self.db.query(TeacherAssignment)
            .filter(
                TeacherAssignment.class_id == class_id,
                TeacherAssignment.subject == subject,
                TeacherAssignment.term == term,
            )
            .order_by(TeacherAssignment.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_active_student_ids(self, *, class_id: UUID) -> list[UUID]:
        rows = (
            self.db.query(ClassEnrollment.student_id)
            .filter(
                ClassEnrollment.class_id == class_id,
                ClassEnrollment.status == "active",
            )
            .order_by(ClassEnrollment.student_id.asc())
            .all()
        )
        return [student_id for (student_id,) in rows]

    def get_recent_activity_stats(
        self,
        *,
        class_id: UUID,
        subject: str,
        term: int,
        since: datetime,
    ) -> dict[UUID, dict[str, int]]:
        student_ids = self.get_active_student_ids(class_id=class_id)
        if not student_ids:
            return {}
        rows = (
            self.db.query(
                ActivityLog.student_id,
                func.count(ActivityLog.id).label("event_count"),
                func.coalesce(func.sum(ActivityLog.duration_seconds), 0).label("duration_seconds"),
                func.coalesce(
                    func.sum(case((ActivityLog.event_type == "quiz_submitted", 1), else_=0)),
                    0,
                ).label("quiz_submitted_count"),
                func.coalesce(
                    func.sum(case((ActivityLog.event_type == "lesson_viewed", 1), else_=0)),
                    0,
                ).label("lesson_viewed_count"),
            )
            .filter(
                ActivityLog.student_id.in_(student_ids),
                ActivityLog.subject == subject,
                ActivityLog.term == term,
                ActivityLog.created_at >= since,
            )
            .group_by(ActivityLog.student_id)
            .all()
        )
        result: dict[UUID, dict[str, int]] = {}
        for row in rows:
            result[row.student_id] = {
                "event_count": int(row.event_count or 0),
                "duration_seconds": int(row.duration_seconds or 0),
                "quiz_submitted_count": int(row.quiz_submitted_count or 0),
                "lesson_viewed_count": int(row.lesson_viewed_count or 0),
            }
        return result

    def get_avg_mastery_by_student(self, *, class_id: UUID, subject: str, term: int) -> dict[UUID, float]:
        student_ids = self.get_active_student_ids(class_id=class_id)
        if not student_ids:
            return {}
        rows = (
            self.db.query(
                StudentConceptMastery.student_id,
                func.avg(StudentConceptMastery.mastery_score).label("avg_score"),
            )
            .filter(
                StudentConceptMastery.student_id.in_(student_ids),
                StudentConceptMastery.subject == subject,
                StudentConceptMastery.term == term,
            )
            .group_by(StudentConceptMastery.student_id)
            .all()
        )
        return {row.student_id: float(row.avg_score) for row in rows if row.avg_score is not None}

    def get_heatmap_points(self, *, class_id: UUID, subject: str, term: int) -> list[dict]:
        student_ids = self.get_active_student_ids(class_id=class_id)
        if not student_ids:
            return []
        rows = (
            self.db.query(
                StudentConceptMastery.concept_id,
                func.avg(StudentConceptMastery.mastery_score).label("avg_score"),
                func.count(func.distinct(StudentConceptMastery.student_id)).label("student_count"),
            )
            .filter(
                StudentConceptMastery.student_id.in_(student_ids),
                StudentConceptMastery.subject == subject,
                StudentConceptMastery.term == term,
            )
            .group_by(StudentConceptMastery.concept_id)
            .order_by(func.avg(StudentConceptMastery.mastery_score).asc())
            .all()
        )
        return [
            {
                "concept_id": str(row.concept_id),
                "avg_score": float(row.avg_score),
                "student_count": int(row.student_count),
            }
            for row in rows
        ]

    def get_scope_concept_rows(self, *, subject: str, sss_level: str, term: int) -> list[dict]:
        rows = (
            self.db.query(
                CurriculumTopicMap.concept_id,
                CurriculumTopicMap.prereq_concept_ids,
                Topic.id.label("topic_id"),
                Topic.title.label("topic_title"),
            )
            .join(Topic, Topic.id == CurriculumTopicMap.topic_id)
            .join(CurriculumVersion, CurriculumVersion.id == CurriculumTopicMap.version_id)
            .filter(
                Topic.is_approved.is_(True),
                Topic.sss_level == sss_level,
                Topic.term == term,
                CurriculumVersion.subject == subject,
                CurriculumVersion.sss_level == sss_level,
                CurriculumVersion.term == term,
                CurriculumVersion.status == "published",
            )
            .order_by(Topic.created_at.asc(), Topic.title.asc(), CurriculumTopicMap.concept_id.asc())
            .all()
        )
        return [
            {
                "concept_id": str(row.concept_id),
                "prereq_concept_ids": [str(value).strip() for value in list(row.prereq_concept_ids or []) if str(value).strip()],
                "topic_id": row.topic_id,
                "topic_title": str(row.topic_title or "").strip() or None,
            }
            for row in rows
        ]

    def get_student_concept_rows(
        self,
        *,
        class_id: UUID,
        subject: str,
        term: int,
        concept_ids: list[str],
    ) -> list[dict]:
        student_ids = self.get_active_student_ids(class_id=class_id)
        if not student_ids or not concept_ids:
            return []
        rows = (
            self.db.query(
                StudentConceptMastery.student_id,
                StudentConceptMastery.concept_id,
                StudentConceptMastery.mastery_score,
                StudentConceptMastery.last_evaluated_at,
            )
            .filter(
                StudentConceptMastery.student_id.in_(student_ids),
                StudentConceptMastery.subject == subject,
                StudentConceptMastery.term == term,
                StudentConceptMastery.concept_id.in_(concept_ids),
            )
            .all()
        )
        return [
            {
                "student_id": row.student_id,
                "concept_id": str(row.concept_id),
                "mastery_score": float(row.mastery_score),
                "last_evaluated_at": row.last_evaluated_at,
            }
            for row in rows
        ]

    def get_negative_mastery_delta_by_student(
        self,
        *,
        class_id: UUID,
        subject: str,
        term: int,
        since: datetime,
    ) -> dict[UUID, float]:
        student_ids = set(self.get_active_student_ids(class_id=class_id))
        if not student_ids:
            return {}

        rows = (
            self.db.query(MasteryUpdateEvent.student_id, MasteryUpdateEvent.new_mastery)
            .filter(
                MasteryUpdateEvent.student_id.in_(student_ids),
                MasteryUpdateEvent.subject == subject,
                MasteryUpdateEvent.term == term,
                MasteryUpdateEvent.created_at >= since,
            )
            .all()
        )

        totals: dict[UUID, float] = defaultdict(float)
        for student_id, new_mastery in rows:
            for entry in (new_mastery or []):
                delta = float(entry.get("delta", 0.0))
                if delta < 0:
                    totals[student_id] += delta
        return dict(totals)

    def get_low_mastery_students(
        self,
        *,
        class_id: UUID,
        subject: str,
        term: int,
        threshold: float,
    ) -> dict[UUID, float]:
        averages = self.get_avg_mastery_by_student(class_id=class_id, subject=subject, term=term)
        return {student_id: score for student_id, score in averages.items() if score < threshold}

    def get_student_timeline(self, *, class_id: UUID, student_id: UUID, limit: int = 50) -> list[dict]:
        teacher_class = self.get_class(class_id)
        if not teacher_class:
            return []

        events: list[dict] = []

        activity_rows = (
            self.db.query(ActivityLog)
            .filter(
                ActivityLog.student_id == student_id,
                ActivityLog.subject == teacher_class.subject,
                ActivityLog.term == teacher_class.term,
            )
            .order_by(ActivityLog.created_at.desc())
            .limit(limit)
            .all()
        )
        topic_ids: set[UUID] = set()
        for row in activity_rows:
            raw_ref = str(row.ref_id or "").strip()
            if not raw_ref:
                continue
            try:
                topic_ids.add(UUID(raw_ref))
            except (TypeError, ValueError):
                continue
        topic_title_map: dict[str, str] = {}
        if topic_ids:
            topic_rows = (
                self.db.query(Topic.id, Topic.title)
                .filter(Topic.id.in_(list(topic_ids)))
                .all()
            )
            topic_title_map = {
                str(row.id): str(row.title or "").strip()
                for row in topic_rows
                if row and row.title is not None and str(row.title).strip()
            }
        for row in activity_rows:
            ref_id = str(row.ref_id or "").strip() or None
            ref_label = topic_title_map.get(str(ref_id)) if ref_id else None
            events.append(
                {
                    "event_type": "activity",
                    "occurred_at": row.created_at,
                    "details": {
                        "activity_type": row.event_type,
                        "duration_seconds": row.duration_seconds,
                        "ref_id": ref_id,
                        "ref_label": ref_label,
                        "ref_type": "topic" if ref_label else None,
                    },
                }
            )

        mastery_rows = (
            self.db.query(MasteryUpdateEvent)
            .filter(
                MasteryUpdateEvent.student_id == student_id,
                MasteryUpdateEvent.subject == teacher_class.subject,
                MasteryUpdateEvent.term == teacher_class.term,
            )
            .order_by(MasteryUpdateEvent.created_at.desc())
            .limit(limit)
            .all()
        )
        for row in mastery_rows:
            events.append(
                {
                    "event_type": "mastery_update",
                    "occurred_at": row.created_at,
                    "details": {
                        "source": row.source,
                        "updated_concepts": len(row.new_mastery or []),
                    },
                }
            )

        session_rows = (
            self.db.query(TutorSession)
            .filter(
                TutorSession.student_id == student_id,
                TutorSession.subject == teacher_class.subject,
                TutorSession.term == teacher_class.term,
            )
            .order_by(TutorSession.started_at.desc())
            .limit(limit)
            .all()
        )
        for row in session_rows:
            events.append(
                {
                    "event_type": "tutor_session",
                    "occurred_at": row.started_at,
                    "details": {
                        "session_id": str(row.id),
                        "status": row.status,
                        "duration_seconds": row.duration_seconds,
                    },
                }
            )

        intervention_rows = (
            self.db.query(TeacherIntervention)
            .filter(
                TeacherIntervention.student_id == student_id,
                TeacherIntervention.class_id == class_id,
            )
            .order_by(TeacherIntervention.created_at.desc())
            .limit(limit)
            .all()
        )
        for row in intervention_rows:
            events.append(
                {
                    "event_type": "intervention",
                    "occurred_at": row.created_at,
                    "details": {
                        "intervention_type": row.intervention_type,
                        "severity": row.severity,
                        "status": row.status,
                    },
                }
            )

        events.sort(key=lambda item: item["occurred_at"], reverse=True)
        return events[:limit]

    def get_mastery_events_for_students_since(
        self,
        *,
        student_ids: list[UUID],
        subject: str,
        term: int,
        since: datetime,
    ) -> list[MasteryUpdateEvent]:
        if not student_ids:
            return []
        return (
            self.db.query(MasteryUpdateEvent)
            .filter(
                MasteryUpdateEvent.student_id.in_(student_ids),
                MasteryUpdateEvent.subject == subject,
                MasteryUpdateEvent.term == term,
                MasteryUpdateEvent.created_at >= since,
            )
            .order_by(MasteryUpdateEvent.created_at.desc())
            .all()
        )

    def get_activity_rows_for_students_since(
        self,
        *,
        student_ids: list[UUID],
        subject: str,
        term: int,
        since: datetime,
    ) -> list[ActivityLog]:
        if not student_ids:
            return []
        return (
            self.db.query(ActivityLog)
            .filter(
                ActivityLog.student_id.in_(student_ids),
                ActivityLog.subject == subject,
                ActivityLog.term == term,
                ActivityLog.created_at >= since,
            )
            .order_by(ActivityLog.created_at.desc())
            .all()
        )

    def get_activity_rows_for_students_since(
        self,
        *,
        student_ids: list[UUID],
        subject: str,
        term: int,
        since: datetime,
    ) -> list[ActivityLog]:
        if not student_ids:
            return []
        return (
            self.db.query(ActivityLog)
            .filter(
                ActivityLog.student_id.in_(student_ids),
                ActivityLog.subject == subject,
                ActivityLog.term == term,
                ActivityLog.created_at >= since,
            )
            .order_by(ActivityLog.created_at.desc())
            .all()
        )
