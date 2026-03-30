from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from backend.models.activity import ActivityLog, StudentStats
from backend.models.class_enrollment import ClassEnrollment
from backend.models.curriculum_topic_map import CurriculumTopicMap
from backend.models.curriculum_version import CurriculumVersion
from backend.models.mastery_update_event import MasteryUpdateEvent
from backend.models.student import StudentProfile, StudentSubject
from backend.models.student_concept_mastery import StudentConceptMastery
from backend.models.subject import Subject
from backend.models.teacher_class import TeacherClass
from backend.models.topic import Topic
from backend.models.user import User


@dataclass(frozen=True)
class _Scope:
    subject: str
    sss_level: str
    term: int


def _read_env(name: str, default: str) -> str:
    return (os.getenv(name) or default).strip()


def _status_payload(status: str, *, detail: str | None = None, **extra: Any) -> dict[str, Any]:
    payload = {"status": status}
    if detail:
        payload["detail"] = detail
    if extra:
        payload.update(extra)
    return payload


class DemoValidationService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _scope_from_env() -> _Scope:
        subject = _read_env("DEMO_SUBJECT", "math").lower()
        sss_level = _read_env("DEMO_SSS_LEVEL", "SSS1").upper()
        try:
            term = int(_read_env("DEMO_TERM", "1"))
        except ValueError:
            term = 1
        return _Scope(subject=subject, sss_level=sss_level, term=term)

    def snapshot(self) -> dict[str, Any]:
        scope = self._scope_from_env()
        checks: dict[str, Any] = {
            "scope": {
                "subject": scope.subject,
                "sss_level": scope.sss_level,
                "term": scope.term,
            },
        }

        subject_row = self.db.query(Subject).filter(Subject.slug == scope.subject).first()
        checks["subject"] = (
            _status_payload("ok", name=subject_row.name if subject_row else None)
            if subject_row
            else _status_payload("missing", detail="Subject not found for demo scope.")
        )

        topic_query = (
            self.db.query(Topic)
            .filter(
                Topic.sss_level == scope.sss_level,
                Topic.term == scope.term,
                Topic.is_approved.is_(True),
            )
        )
        if subject_row:
            topic_query = topic_query.filter(Topic.subject_id == subject_row.id)
        topics = topic_query.all()
        checks["topics"] = (
            _status_payload("ok", count=len(topics))
            if topics
            else _status_payload("missing", detail="No approved topics in demo scope.")
        )

        version = (
            self.db.query(CurriculumVersion)
            .filter(
                CurriculumVersion.subject == scope.subject,
                CurriculumVersion.sss_level == scope.sss_level,
                CurriculumVersion.term == scope.term,
                CurriculumVersion.status.in_(["approved", "published"]),
            )
            .order_by(CurriculumVersion.approved_at.desc().nullslast(), CurriculumVersion.created_at.desc())
            .first()
        )
        checks["curriculum_version"] = (
            _status_payload("ok", version_id=str(version.id), status=version.status)
            if version
            else _status_payload("missing", detail="No approved curriculum version for demo scope.")
        )

        map_count = 0
        if version and topics:
            topic_ids = [topic.id for topic in topics]
            map_count = (
                self.db.query(CurriculumTopicMap)
                .filter(
                    CurriculumTopicMap.version_id == version.id,
                    CurriculumTopicMap.topic_id.in_(topic_ids),
                )
                .count()
            )
        checks["topic_mappings"] = (
            _status_payload("ok", count=map_count)
            if map_count
            else _status_payload("missing", detail="No topic-to-concept mappings for demo scope.")
        )

        student_email = _read_env("DEMO_STUDENT_EMAIL", "demo.student@masteryai.local")
        teacher_email = _read_env("DEMO_TEACHER_EMAIL", "demo.teacher@masteryai.local")

        student = self.db.query(User).filter(User.email == student_email).first()
        checks["demo_student"] = _status_payload("ok", user_id=str(student.id)) if student else _status_payload(
            "missing", detail=f"Demo student user not found ({student_email})."
        )

        if student:
            profile = self.db.query(StudentProfile).filter(StudentProfile.student_id == student.id).first()
            checks["demo_student_profile"] = (
                _status_payload("ok", sss_level=profile.sss_level, term=profile.active_term)
                if profile
                else _status_payload("missing", detail="Demo student profile missing.")
            )
            if profile and subject_row:
                enrollment = (
                    self.db.query(StudentSubject)
                    .filter(
                        StudentSubject.student_profile_id == profile.id,
                        StudentSubject.subject_id == subject_row.id,
                    )
                    .first()
                )
            else:
                enrollment = None
            checks["demo_student_enrollment"] = (
                _status_payload("ok")
                if enrollment
                else _status_payload("missing", detail="Demo student is not enrolled in demo subject.")
            )

            mastery_count = (
                self.db.query(StudentConceptMastery)
                .filter(
                    StudentConceptMastery.student_id == student.id,
                    StudentConceptMastery.subject == scope.subject,
                    StudentConceptMastery.sss_level == scope.sss_level,
                    StudentConceptMastery.term == scope.term,
                )
                .count()
            )
            checks["demo_mastery"] = (
                _status_payload("ok", count=mastery_count)
                if mastery_count
                else _status_payload("missing", detail="No mastery entries for demo student.")
            )

            evidence_count = (
                self.db.query(MasteryUpdateEvent)
                .filter(
                    MasteryUpdateEvent.student_id == student.id,
                    MasteryUpdateEvent.subject == scope.subject,
                    MasteryUpdateEvent.sss_level == scope.sss_level,
                    MasteryUpdateEvent.term == scope.term,
                )
                .count()
            )
            checks["demo_evidence"] = (
                _status_payload("ok", count=evidence_count)
                if evidence_count
                else _status_payload("missing", detail="No mastery update events for demo student.")
            )

            activity_count = (
                self.db.query(ActivityLog)
                .filter(ActivityLog.student_id == student.id)
                .count()
            )
            stats = self.db.query(StudentStats).filter(StudentStats.student_id == student.id).first()
            checks["demo_activity"] = (
                _status_payload("ok", activity_events=activity_count, has_stats=bool(stats))
                if activity_count or stats
                else _status_payload("missing", detail="No activity or stats logged for demo student.")
            )

        teacher = self.db.query(User).filter(User.email == teacher_email).first()
        checks["demo_teacher"] = _status_payload("ok", user_id=str(teacher.id)) if teacher else _status_payload(
            "missing", detail=f"Demo teacher user not found ({teacher_email})."
        )

        if teacher:
            teacher_class = (
                self.db.query(TeacherClass)
                .filter(
                    TeacherClass.teacher_id == teacher.id,
                    TeacherClass.subject == scope.subject,
                    TeacherClass.sss_level == scope.sss_level,
                    TeacherClass.term == scope.term,
                )
                .first()
            )
            checks["demo_teacher_class"] = (
                _status_payload("ok", class_id=str(teacher_class.id), name=teacher_class.name)
                if teacher_class
                else _status_payload("missing", detail="No demo teacher class found for scope.")
            )

            if teacher_class:
                enrollment_count = (
                    self.db.query(ClassEnrollment)
                    .filter(ClassEnrollment.class_id == teacher_class.id)
                    .count()
                )
                checks["demo_class_enrollment"] = (
                    _status_payload("ok", count=enrollment_count)
                    if enrollment_count
                    else _status_payload("missing", detail="Demo teacher class has no enrolled students.")
                )

        core_ok = all(
            checks[key]["status"] == "ok"
            for key in ("subject", "topics", "curriculum_version", "topic_mappings")
        )
        user_ok = checks.get("demo_student", {}).get("status") == "ok" and checks.get("demo_teacher", {}).get("status") == "ok"

        if not core_ok:
            overall = "unavailable"
        elif not user_ok:
            overall = "attention"
        else:
            overall = "ready"

        return {
            "status": overall,
            "checks": checks,
        }
