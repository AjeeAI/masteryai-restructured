from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.database import SessionLocal
from backend.core.telemetry import log_timed_event, now_ms
from backend.models.student import StudentProfile, StudentSubject
from backend.models.subject import Subject
from backend.schemas.diagnostic_schema import DiagnosticStatusOut
from backend.schemas.dashboard_schema import DashboardBootstrapOut, StudentExportSectionOut, StudentPathBriefingOut
from backend.services.course_experience_service import CourseExperienceService
from backend.services.diagnostic_service import DiagnosticValidationError, diagnostic_service
from backend.services.prewarm_job_service import PrewarmJobService

logger = logging.getLogger(__name__)
DASHBOARD_CACHE_TTL_SECONDS = 30.0
_DASHBOARD_BOOTSTRAP_CACHE: dict[str, tuple[float, DashboardBootstrapOut]] = {}


class DashboardExperienceError(ValueError):
    pass


class DashboardExperienceService:
    def __init__(self, db: Session):
        self.db = db
        self.course_service = CourseExperienceService(db)

    @staticmethod
    def _profile_signature(*, profile: StudentProfile, subjects: list[str]) -> str:
        payload = {
            "updated_at": profile.updated_at.isoformat() if getattr(profile, "updated_at", None) else "",
            "sss_level": str(profile.sss_level),
            "term": int(profile.active_term),
            "subjects": sorted(subjects),
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _cache_key(*, student_id: UUID, subject: str | None, profile_signature: str) -> str:
        return ":".join([str(student_id), subject or "auto", profile_signature])

    @staticmethod
    def _read_cached_bootstrap(*, cache_key: str) -> DashboardBootstrapOut | None:
        entry = _DASHBOARD_BOOTSTRAP_CACHE.get(cache_key)
        if entry is None:
            return None
        created_at, payload = entry
        if (time.time() - created_at) > DASHBOARD_CACHE_TTL_SECONDS:
            _DASHBOARD_BOOTSTRAP_CACHE.pop(cache_key, None)
            return None
        return payload

    @staticmethod
    def _write_cached_bootstrap(*, cache_key: str, payload: DashboardBootstrapOut) -> DashboardBootstrapOut:
        _DASHBOARD_BOOTSTRAP_CACHE[cache_key] = (time.time(), payload)
        return payload

    @classmethod
    def invalidate_student_cache(cls, *, student_id: UUID) -> None:
        prefix = f"{student_id}:"
        for cache_key in [key for key in list(_DASHBOARD_BOOTSTRAP_CACHE.keys()) if key.startswith(prefix)]:
            _DASHBOARD_BOOTSTRAP_CACHE.pop(cache_key, None)

    @classmethod
    def cache_snapshot(cls) -> dict:
        cls._prune_cache()
        return {
            "status": "ok",
            "bootstrap_cache": {
                "entries": len(_DASHBOARD_BOOTSTRAP_CACHE),
                "ttl_seconds": DASHBOARD_CACHE_TTL_SECONDS,
            },
        }

    @classmethod
    def _prune_cache(cls) -> None:
        now = time.time()
        for cache_key, (created_at, _payload) in list(_DASHBOARD_BOOTSTRAP_CACHE.items()):
            if (now - created_at) > DASHBOARD_CACHE_TTL_SECONDS:
                _DASHBOARD_BOOTSTRAP_CACHE.pop(cache_key, None)

    @classmethod
    def prewarm(
        cls,
        *,
        student_id: UUID,
        subject: Literal["math", "english", "civic"] | None = None,
    ) -> bool:
        db = SessionLocal()
        try:
            cls(db).bootstrap(student_id=student_id, subject=subject)
            logger.info(
                "dashboard.bootstrap.prewarm_success student_id=%s subject=%s",
                student_id,
                subject or "auto",
            )
            return True
        except Exception as exc:  # pragma: no cover - best effort prewarm
            logger.warning(
                "dashboard.bootstrap.prewarm_failed student_id=%s subject=%s detail=%s",
                student_id,
                subject or "auto",
                exc,
            )
            return False
        finally:
            db.close()

    def _profile_and_subjects(
        self,
        *,
        student_id: UUID,
    ) -> tuple[StudentProfile, list[Literal["math", "english", "civic"]]]:
        profile = self.db.execute(
            select(StudentProfile).where(StudentProfile.student_id == student_id)
        ).scalar_one_or_none()
        if profile is None:
            raise DashboardExperienceError("Student profile not found.")

        rows = self.db.execute(
            select(Subject.slug)
            .join(StudentSubject, StudentSubject.subject_id == Subject.id)
            .where(StudentSubject.student_profile_id == profile.id)
            .order_by(Subject.slug.asc())
        ).all()
        subjects = [str(row[0]) for row in rows if str(row[0]) in {"math", "english", "civic"}]
        return profile, subjects  # type: ignore[return-value]

    @staticmethod
    def _subject_from_diagnostic_status(
        diagnostic_status: DiagnosticStatusOut | None,
    ) -> Literal["math", "english", "civic"] | None:
        if diagnostic_status is None:
            return None
        completed_runs = [run for run in list(diagnostic_status.subject_runs or []) if run.status == "completed"]
        if not completed_runs:
            return None

        def weakest_score(run) -> float:
            weakest = [float(item.mastery_score) for item in list(run.weakest_concepts or [])]
            return min(weakest) if weakest else 1.0

        ranked_runs = sorted(
            completed_runs,
            key=lambda run: (weakest_score(run), run.completion_timestamp or ""),
        )
        subject = ranked_runs[0].subject if ranked_runs else None
        return subject if subject in {"math", "english", "civic"} else None  # type: ignore[return-value]

    @staticmethod
    def _course_attr(course_bootstrap, key: str):
        if course_bootstrap is None:
            return None
        if isinstance(course_bootstrap, dict):
            return course_bootstrap.get(key)
        return getattr(course_bootstrap, key, None)

    def bootstrap(
        self,
        *,
        student_id: UUID,
        subject: Literal["math", "english", "civic"] | None = None,
    ) -> DashboardBootstrapOut:
        started_at = now_ms()
        profile, available_subjects = self._profile_and_subjects(student_id=student_id)
        diagnostic_status = None
        try:
            diagnostic_status = diagnostic_service.get_diagnostic_status(db=self.db, student_id=student_id)
        except (DiagnosticValidationError, AttributeError, TypeError):
            diagnostic_status = None
        profile_signature = self._profile_signature(profile=profile, subjects=available_subjects)
        cache_key = self._cache_key(
            student_id=student_id,
            subject=subject,
            profile_signature=profile_signature,
        )
        cached = self._read_cached_bootstrap(cache_key=cache_key)
        if cached is not None:
            log_timed_event(
                logger,
                "dashboard.bootstrap",
                started_at,
                cache_hit=True,
                student_id=student_id,
                requested_subject=subject or "auto",
                active_subject=cached.active_subject or "none",
                warmed_subjects=len(list(cached.warmed_subjects or [])),
            )
            return cached

        course_bootstrap = None
        active_subject = subject if subject in available_subjects else None
        course_bootstrap_source = "none"

        if active_subject is None:
            latest = self.course_service.latest_intervention_bootstrap(student_id=student_id)
            if latest is not None:
                course_bootstrap = latest
                active_subject = latest.subject
                course_bootstrap_source = "latest_intervention"

        if active_subject is None and available_subjects:
            active_subject = self._subject_from_diagnostic_status(diagnostic_status) or available_subjects[0]

        if active_subject is not None and course_bootstrap is None:
            course_bootstrap = self.course_service.bootstrap(
                student_id=student_id,
                subject=active_subject,
                term=int(profile.active_term),
            )
            course_bootstrap_source = "scope_bootstrap"

        warmed_subjects: list[Literal["math", "english", "civic"]] = []
        failed_subjects: list[Literal["math", "english", "civic"]] = []
        prewarm_service = PrewarmJobService(self.db)
        for candidate_subject in available_subjects:
            if candidate_subject == active_subject:
                continue
            if prewarm_service.enqueue_course_scope(
                student_id=student_id,
                subject=candidate_subject,
                term=int(profile.active_term),
            ):
                warmed_subjects.append(candidate_subject)

        payload = DashboardBootstrapOut(
            student_id=student_id,
            sss_level=str(profile.sss_level),  # type: ignore[arg-type]
            term=int(profile.active_term),  # type: ignore[arg-type]
            available_subjects=available_subjects,
            active_subject=active_subject,
            warmed_subjects=warmed_subjects,
            failed_subjects=failed_subjects,
            diagnostic_status=diagnostic_status,
            learning_gap_summary=self._course_attr(course_bootstrap, "learning_gap_summary"),
            initial_lesson_plan=self._course_attr(course_bootstrap, "initial_lesson_plan"),
            course_bootstrap=course_bootstrap,
        )
        output = self._write_cached_bootstrap(cache_key=cache_key, payload=payload)
        log_timed_event(
            logger,
            "dashboard.bootstrap",
            started_at,
            cache_hit=False,
            student_id=student_id,
            requested_subject=subject or "auto",
            active_subject=active_subject or "none",
            course_bootstrap_source=course_bootstrap_source,
            warmed_subjects=len(warmed_subjects),
            failed_subjects=len(failed_subjects),
        )
        return output

    @staticmethod
    def _build_markdown(*, title: str, subtitle: str, sections: list[StudentExportSectionOut]) -> str:
        lines = [f"# {title}", "", subtitle]
        for section in sections:
            lines.extend(["", f"## {section.title}"])
            if not section.items:
                lines.append("- No export-ready evidence yet.")
                continue
            lines.extend([f"- {item}" for item in section.items])
        lines.append("")
        return "\n".join(lines)

    def get_path_briefing_export(
        self,
        *,
        student_id: UUID,
        subject: Literal["math", "english", "civic"] | None = None,
    ) -> StudentPathBriefingOut:
        bootstrap = self.bootstrap(student_id=student_id, subject=subject)
        active_subject = bootstrap.active_subject
        course = bootstrap.course_bootstrap
        if active_subject is None or course is None:
            raise DashboardExperienceError("Student graph path is unavailable for this scope.")

        next_step = course.next_step
        story = course.recommendation_story
        recent = course.recent_evidence
        timeline = list(course.intervention_timeline or [])
        topics = list(course.topics or [])

        ready_topics = [
            topic.title
            for topic in topics
            if topic.status in {"ready", "current"}
        ][:5]
        blocked_topics = [
            f"{topic.title}: {topic.graph_details or topic.lesson_unavailable_reason or 'Waiting on prerequisite mastery.'}"
            for topic in topics
            if topic.status == "locked"
        ][:5]
        timeline_items = [
            f"{event.source_label}: {event.summary}"
            for event in timeline[:5]
        ]

        sections = [
            StudentExportSectionOut(
                title="Graph signal",
                items=[
                    story.headline if story else (next_step.recommended_topic_title or next_step.recommended_concept_label or "Stay on your current graph path.") if next_step else "No graph recommendation is available yet.",
                    story.supporting_reason if story else (next_step.reason if next_step else "Collect more evidence from lessons, checkpoints, or quizzes."),
                ],
            ),
            StudentExportSectionOut(
                title="Best next lesson",
                items=[
                    next_step.recommended_topic_title if next_step and next_step.recommended_topic_title else "No lesson has been recommended yet.",
                    next_step.reason if next_step else "The graph needs more evidence before changing your route.",
                ],
            ),
            StudentExportSectionOut(
                title="Repair first",
                items=(
                    list(next_step.prereq_gap_labels)
                    if next_step and next_step.prereq_gap_labels
                    else blocked_topics
                )[:5],
            ),
            StudentExportSectionOut(
                title="Ready now",
                items=ready_topics,
            ),
            StudentExportSectionOut(
                title="Recent evidence",
                items=timeline_items or ([recent.summary] if recent else []),
            ),
        ]

        generated_at = datetime.now(timezone.utc).isoformat()
        title = f"{active_subject.title()} learning path briefing"
        subtitle = (
            f"{bootstrap.sss_level} Term {bootstrap.term}. "
            "Graph-backed student summary of next lesson, blockers, and recent evidence."
        )

        return StudentPathBriefingOut(
            student_id=student_id,
            subject=active_subject,
            sss_level=bootstrap.sss_level,
            term=bootstrap.term,
            title=title,
            subtitle=subtitle,
            generated_at=generated_at,
            file_name=f"{active_subject}-learning-path-briefing.md",
            markdown=self._build_markdown(title=title, subtitle=subtitle, sections=sections),
            sections=sections,
        )
