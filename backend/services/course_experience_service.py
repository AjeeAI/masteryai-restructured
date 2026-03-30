from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from uuid import UUID

from sqlalchemy import desc
from sqlalchemy import select
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from backend.core.database import SessionLocal
from backend.core.telemetry import log_timed_event, now_ms
from backend.models.mastery_update_event import MasteryUpdateEvent
from backend.models.personalized_lesson import PersonalizedLesson
from backend.models.student import StudentProfile, StudentSubject
from backend.models.subject import Subject
from backend.models.topic import Topic
from backend.repositories.diagnostic_repo import DiagnosticRepository
from backend.repositories.graph_repo import GraphRepository
from backend.schemas.course_schema import (
    CourseBootstrapOut,
    CourseInitialLessonPlanOut,
    CourseInterventionEventOut,
    CourseBootstrapTopicOut,
    CourseRecentEvidenceOut,
    CourseRecommendationStoryOut,
    CourseEvidenceSummaryOut,
)
from backend.schemas.diagnostic_schema import (
    DiagnosticLearningGapSummaryOut,
    DiagnosticSubjectRunOut,
    DiagnosticWeakConceptOut,
)
from backend.schemas.learning_path_schema import LearningMapNodeOut, PathNextIn
from backend.repositories.lesson_repo import ensure_personalized_lessons_table
from backend.services.learning_path_service import LearningPathValidationError, learning_path_service
from backend.services.lesson_experience_service import LessonExperienceService
from backend.services.prewarm_job_service import PrewarmJobService
from backend.services.rag_retrieve_service import RagRetrieveService, RagRetrieveServiceError

logger = logging.getLogger(__name__)
CACHE_TTL_SECONDS = 30.0
_COURSE_BOOTSTRAP_CACHE: dict[str, tuple[float, CourseBootstrapOut]] = {}

_NOISY_DESCRIPTION_MARKERS = (
    "SECOND TERM E-LEARNING NOTE SUBJECT",
    "SCHEME OF WORK WEEK TOPIC",
    "WEEKEND ASSIGNMENT SECTION",
)
MASTERY_THRESHOLD = 0.7


def _clean_topic_description(raw: str | None) -> str | None:
    text = re.sub(r"\s+", " ", str(raw or "")).strip()
    if not text:
        return None
    if any(marker in text.upper() for marker in _NOISY_DESCRIPTION_MARKERS):
        return None
    if len(text) > 220:
        return f"{text[:217].rstrip()}..."
    return text


def _has_cached_personalized_lesson(lesson: PersonalizedLesson | None) -> bool:
    return bool(lesson and isinstance(lesson.content_blocks, list) and lesson.content_blocks)


class CourseExperienceError(ValueError):
    pass


class CourseExperienceService:
    def __init__(self, db: Session):
        self.db = db

    def _personalized_lessons_available(self) -> bool:
        bind = self.db.get_bind()
        inspector = inspect(bind)
        if inspector.has_table("personalized_lessons"):
            return True
        try:
            ensure_personalized_lessons_table(self.db)
        except Exception as exc:
            logger.warning("course.bootstrap.personalized_lessons_unavailable detail=%s", exc)
            return False
        return inspect(bind).has_table("personalized_lessons")

    @staticmethod
    def _readable_concept_label(concept_id: str | None) -> str | None:
        value = str(concept_id or "").strip()
        if not value:
            return None
        try:
            UUID(value)
            return None
        except ValueError:
            pass
        token = value.rsplit(":", 1)[-1].strip()
        token = re.sub(r"-(\d+)$", "", token)
        token = re.sub(r"[_-]+", " ", token)
        token = re.sub(r"\s+", " ", token).strip()
        return token.title() if token else None

    @staticmethod
    def _evidence_summary(nodes: list[LearningMapNodeOut]) -> CourseEvidenceSummaryOut:
        summary = CourseEvidenceSummaryOut()
        for node in nodes:
            score = float(getattr(node, "mastery_score", 0.0) or 0.0)
            if score >= MASTERY_THRESHOLD:
                summary.demonstrated += 1
            elif score > 0:
                summary.needs_review += 1
            else:
                summary.unassessed += 1
        return summary

    def _latest_scope_evidence(
        self,
        *,
        student_id: UUID,
        subject: str,
        sss_level: str,
        term: int,
    ) -> CourseRecentEvidenceOut | None:
        events = self._recent_scope_events(
            student_id=student_id,
            subject=subject,
            sss_level=sss_level,
            term=term,
            limit=1,
        )
        if not events:
            return None
        signal = self._event_signal(events[0])
        return CourseRecentEvidenceOut(
            source=signal["source"],
            created_at=signal["created_at"],
            strongest_gain_concept_label=signal["strongest_gain_concept_label"],
            strongest_drop_concept_label=signal["strongest_drop_concept_label"],
            summary=signal["summary"],
        )

    def _recent_scope_events(
        self,
        *,
        student_id: UUID,
        subject: str,
        sss_level: str,
        term: int,
        limit: int = 5,
    ) -> list[MasteryUpdateEvent]:
        return (
            self.db.query(MasteryUpdateEvent)
            .filter(
                MasteryUpdateEvent.student_id == student_id,
                MasteryUpdateEvent.subject == subject,
                MasteryUpdateEvent.sss_level == sss_level,
                MasteryUpdateEvent.term == term,
            )
            .order_by(desc(MasteryUpdateEvent.created_at))
            .limit(limit)
            .all()
        )

    @staticmethod
    def _event_kind_and_label(event: MasteryUpdateEvent) -> tuple[str, str]:
        source = str(getattr(event, "source", "") or "").strip().lower()
        if source == "practice":
            if getattr(event, "quiz_id", None):
                return "quiz", "Quiz result"
            return "checkpoint", "Tutor checkpoint"
        if source == "diagnostic":
            return "diagnostic", "Diagnostic"
        if source == "exam_prep":
            return "exam_prep", "Exam prep"
        return "practice", "Practice"

    def _event_signal(self, event: MasteryUpdateEvent) -> dict[str, str | None]:
        strongest_gain = None
        strongest_drop = None
        gain_delta = 0.0
        drop_delta = 0.0
        for entry in list(event.new_mastery or []):
            try:
                delta = float(entry.get("delta", 0.0))
            except (TypeError, ValueError):
                continue
            concept_label = self._readable_concept_label(entry.get("concept_id"))
            if delta > gain_delta:
                gain_delta = delta
                strongest_gain = concept_label
            if delta < drop_delta:
                drop_delta = delta
                strongest_drop = concept_label

        kind, source_label = self._event_kind_and_label(event)
        focus_concept_label = strongest_drop or strongest_gain
        if strongest_gain and strongest_drop:
            summary = f"{source_label} strengthened {strongest_gain} but exposed a gap in {strongest_drop}."
            action_label = "Review weak concept"
        elif strongest_drop:
            summary = f"{source_label} showed a weaker result in {strongest_drop}."
            action_label = "Repair prerequisite"
        elif strongest_gain:
            summary = f"{source_label} improved {strongest_gain}."
            action_label = "Push the next concept"
        else:
            summary = f"{source_label} updated your mastery profile."
            action_label = "Review latest evidence"

        created_at = event.created_at.isoformat() if getattr(event, "created_at", None) else ""
        return {
            "kind": kind,
            "source": str(event.source),
            "source_label": source_label,
            "created_at": created_at,
            "summary": summary,
            "focus_concept_label": focus_concept_label,
            "strongest_gain_concept_label": strongest_gain,
            "strongest_drop_concept_label": strongest_drop,
            "action_label": action_label,
        }

    def _scope_intervention_timeline(
        self,
        *,
        student_id: UUID,
        subject: str,
        sss_level: str,
        term: int,
    ) -> list[CourseInterventionEventOut]:
        events = self._recent_scope_events(
            student_id=student_id,
            subject=subject,
            sss_level=sss_level,
            term=term,
            limit=4,
        )
        timeline: list[CourseInterventionEventOut] = []
        for event in events:
            signal = self._event_signal(event)
            timeline.append(
                CourseInterventionEventOut(
                    kind=signal["kind"],  # type: ignore[arg-type]
                    source=signal["source"],  # type: ignore[arg-type]
                    source_label=signal["source_label"],  # type: ignore[arg-type]
                    created_at=signal["created_at"],  # type: ignore[arg-type]
                    summary=signal["summary"],  # type: ignore[arg-type]
                    focus_concept_label=signal["focus_concept_label"],
                    strongest_gain_concept_label=signal["strongest_gain_concept_label"],
                    strongest_drop_concept_label=signal["strongest_drop_concept_label"],
                    action_label=signal["action_label"],  # type: ignore[arg-type]
                )
            )
        return timeline

    @staticmethod
    def _recommendation_story(
        *,
        next_step,
        recent_evidence: CourseRecentEvidenceOut | None,
    ) -> CourseRecommendationStoryOut | None:
        if next_step is None:
            return None

        evidence_summary = recent_evidence.summary if recent_evidence is not None else None
        blocking_label = next_step.prereq_gap_labels[0] if next_step.prereq_gap_labels else None
        next_concept_label = next_step.recommended_concept_label or None

        if blocking_label:
            headline = f"Repair {blocking_label} before pushing forward."
            action_label = "Open prerequisite bridge"
            status = "bridge_prerequisite"
        elif next_step.recommended_topic_title or next_concept_label:
            headline = (
                f"Push into {next_step.recommended_topic_title or next_concept_label} next."
            )
            action_label = "Open recommended lesson"
            status = "advance_to_next"
        else:
            headline = "Stay on the current focus and consolidate mastery."
            action_label = "Review current lesson"
            status = "hold_current"

        return CourseRecommendationStoryOut(
            status=status,
            headline=headline,
            supporting_reason=next_step.reason,
            blocking_prerequisite_label=blocking_label,
            next_concept_label=next_concept_label,
            evidence_summary=evidence_summary,
            action_label=action_label,
        )

    @staticmethod
    def _scope_diagnostic_signal(
        *,
        db: Session,
        student_id: UUID,
        subject: str,
        sss_level: str,
        term: int,
    ) -> tuple[DiagnosticSubjectRunOut | None, DiagnosticLearningGapSummaryOut | None]:
        repo = DiagnosticRepository(db)
        latest_runs = repo.get_latest_scope_diagnostics(
            student_id=student_id,
            sss_level=sss_level,
            term=term,
            subjects=[subject],
        )
        diagnostic, attempt = latest_runs.get(subject, (None, None))
        if diagnostic is None:
            return DiagnosticSubjectRunOut(subject=subject, status="pending"), None

        question_count = len(list(diagnostic.questions or []))
        if diagnostic.status != "submitted" or attempt is None:
            return (
                DiagnosticSubjectRunOut(
                    subject=subject,
                    status="in_progress",
                    diagnostic_id=diagnostic.id,
                    question_count=question_count,
                ),
                None,
            )

        raw_gap_summary = dict(attempt.gap_summary or {})
        weakest_concepts = [
            DiagnosticWeakConceptOut(**item)
            for item in list(raw_gap_summary.get("weakest_concepts") or [])
            if isinstance(item, dict)
        ]
        gap_summary = DiagnosticLearningGapSummaryOut(
            weakest_concepts=weakest_concepts,
            blocking_prerequisite_id=raw_gap_summary.get("blocking_prerequisite_id"),
            blocking_prerequisite_label=raw_gap_summary.get("blocking_prerequisite_label"),
            recommended_start_topic_id=attempt.recommended_start_topic_id or raw_gap_summary.get("recommended_start_topic_id"),
            recommended_start_topic_title=attempt.recommended_start_topic_title or raw_gap_summary.get("recommended_start_topic_title"),
            next_best_action=raw_gap_summary.get("next_best_action"),
            rationale=raw_gap_summary.get("rationale"),
            question_count=int(raw_gap_summary.get("question_count") or question_count),
            completion_timestamp=raw_gap_summary.get("completion_timestamp")
            or (attempt.created_at.isoformat() if getattr(attempt, "created_at", None) else None),
        )
        diagnostic_status = DiagnosticSubjectRunOut(
            subject=subject,
            status="completed",
            diagnostic_id=diagnostic.id,
            question_count=question_count,
            recommended_start_topic_id=gap_summary.recommended_start_topic_id,
            recommended_start_topic_title=gap_summary.recommended_start_topic_title,
            weakest_concepts=weakest_concepts,
            blocking_prerequisite_id=gap_summary.blocking_prerequisite_id,
            blocking_prerequisite_label=gap_summary.blocking_prerequisite_label,
            completion_timestamp=gap_summary.completion_timestamp,
        )
        return diagnostic_status, gap_summary

    @staticmethod
    def _initial_lesson_plan(
        *,
        next_step,
        recommendation_story: CourseRecommendationStoryOut | None,
        gap_summary: DiagnosticLearningGapSummaryOut | None,
    ) -> CourseInitialLessonPlanOut | None:
        recommended_topic_id = (
            gap_summary.recommended_start_topic_id
            if gap_summary and gap_summary.recommended_start_topic_id
            else (next_step.recommended_topic_id if next_step else None)
        )
        recommended_topic_title = (
            gap_summary.recommended_start_topic_title
            if gap_summary and gap_summary.recommended_start_topic_title
            else (next_step.recommended_topic_title if next_step else None)
        )
        prerequisite_repair_label = (
            gap_summary.blocking_prerequisite_label
            if gap_summary and gap_summary.blocking_prerequisite_label
            else (next_step.prereq_gap_labels[0] if next_step and next_step.prereq_gap_labels else None)
        )
        next_best_action = (
            gap_summary.next_best_action
            if gap_summary and gap_summary.next_best_action
            else (recommendation_story.action_label if recommendation_story else None)
        )
        rationale = (
            gap_summary.rationale
            if gap_summary and gap_summary.rationale
            else (recommendation_story.supporting_reason if recommendation_story else (next_step.reason if next_step else None))
        )

        if not any([recommended_topic_id, recommended_topic_title, prerequisite_repair_label, next_best_action, rationale]):
            return None

        return CourseInitialLessonPlanOut(
            recommended_topic_id=recommended_topic_id,
            recommended_topic_title=recommended_topic_title,
            prerequisite_repair_label=prerequisite_repair_label,
            next_best_action=next_best_action,
            rationale=rationale,
        )

    @staticmethod
    def _candidate_prewarm_topic_ids(
        *,
        topics: list[CourseBootstrapTopicOut],
        next_step,
        max_topics: int = 3,
    ) -> list[UUID]:
        candidates: list[UUID] = []

        def _append(topic_id: str | UUID | None) -> None:
            if not topic_id:
                return
            try:
                parsed = topic_id if isinstance(topic_id, UUID) else UUID(str(topic_id))
            except (TypeError, ValueError):
                return
            if parsed in candidates:
                return
            candidates.append(parsed)

        if next_step and getattr(next_step, "recommended_topic_id", None):
            _append(next_step.recommended_topic_id)

        for topic in topics:
            if len(candidates) >= max_topics:
                break
            if not topic.lesson_ready:
                continue
            if topic.status not in {"current", "ready"} and not topic.is_recommended:
                continue
            _append(topic.topic_id)

        return candidates[:max_topics]

    @staticmethod
    def _scope_mastery_signature(
        *,
        db: Session,
        student_id: UUID,
        subject: str,
        sss_level: str,
        term: int,
    ) -> str:
        mastery_map = GraphRepository(db).get_mastery_map(
            student_id=student_id,
            subject=subject,
            sss_level=sss_level,
            term=term,
        )
        if not mastery_map:
            return "no_mastery"
        payload = json.dumps(sorted(mastery_map.items()), separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _cache_key(
        *,
        student_id: UUID,
        subject: str,
        sss_level: str,
        term: int,
        mastery_signature: str,
    ) -> str:
        return ":".join([str(student_id), subject, sss_level, str(term), mastery_signature])

    @staticmethod
    def _read_cached_bootstrap(*, cache_key: str) -> CourseBootstrapOut | None:
        entry = _COURSE_BOOTSTRAP_CACHE.get(cache_key)
        if entry is None:
            return None
        created_at, payload = entry
        if (time.time() - created_at) > CACHE_TTL_SECONDS:
            _COURSE_BOOTSTRAP_CACHE.pop(cache_key, None)
            return None
        return payload

    @staticmethod
    def _write_cached_bootstrap(*, cache_key: str, payload: CourseBootstrapOut) -> CourseBootstrapOut:
        _COURSE_BOOTSTRAP_CACHE[cache_key] = (time.time(), payload)
        return payload

    @classmethod
    def invalidate_scope_cache(
        cls,
        *,
        student_id: UUID,
        subject: str,
        sss_level: str,
        term: int,
    ) -> None:
        prefix = ":".join([str(student_id), subject, sss_level, str(term)])
        for cache_key in [key for key in list(_COURSE_BOOTSTRAP_CACHE.keys()) if key.startswith(prefix)]:
            _COURSE_BOOTSTRAP_CACHE.pop(cache_key, None)

    @classmethod
    def cache_snapshot(cls) -> dict:
        cls._prune_cache()
        return {
            "status": "ok",
            "bootstrap_cache": {
                "entries": len(_COURSE_BOOTSTRAP_CACHE),
                "ttl_seconds": CACHE_TTL_SECONDS,
            },
        }

    @classmethod
    def _prune_cache(cls) -> None:
        now = time.time()
        for cache_key, (created_at, _payload) in list(_COURSE_BOOTSTRAP_CACHE.items()):
            if (now - created_at) > CACHE_TTL_SECONDS:
                _COURSE_BOOTSTRAP_CACHE.pop(cache_key, None)

    @classmethod
    def prewarm_scope(
        cls,
        *,
        student_id: UUID,
        subject: str,
        term: int,
    ) -> bool:
        db = SessionLocal()
        try:
            cls(db).bootstrap(
                student_id=student_id,
                subject=subject,
                term=term,
            )
            logger.info(
                "course.bootstrap.prewarm_scope_success student_id=%s subject=%s term=%s",
                student_id,
                subject,
                term,
            )
            return True
        except Exception as exc:  # pragma: no cover - best effort prewarm
            logger.warning(
                "course.bootstrap.prewarm_scope_failed student_id=%s subject=%s term=%s detail=%s",
                student_id,
                subject,
                term,
                exc,
            )
            return False
        finally:
            db.close()

    def latest_intervention_bootstrap(self, *, student_id: UUID) -> CourseBootstrapOut | None:
        latest_event = (
            self.db.query(MasteryUpdateEvent)
            .filter(MasteryUpdateEvent.student_id == student_id)
            .order_by(desc(MasteryUpdateEvent.created_at))
            .first()
        )
        if latest_event is None:
            return None
        return self.bootstrap(
            student_id=student_id,
            subject=str(latest_event.subject),
            term=int(latest_event.term),
        )

    def bootstrap(
        self,
        *,
        student_id: UUID,
        subject: str,
        term: int,
    ) -> CourseBootstrapOut:
        started_at = now_ms()
        student_profile = self.db.execute(
            select(StudentProfile).where(StudentProfile.student_id == student_id)
        ).scalar_one_or_none()
        if not student_profile:
            raise CourseExperienceError("Student profile not found.")

        mastery_signature = self._scope_mastery_signature(
            db=self.db,
            student_id=student_id,
            subject=subject,
            sss_level=str(student_profile.sss_level),
            term=term,
        )
        cache_key = self._cache_key(
            student_id=student_id,
            subject=subject,
            sss_level=str(student_profile.sss_level),
            term=term,
            mastery_signature=mastery_signature,
        )
        cached = self._read_cached_bootstrap(cache_key=cache_key)
        if cached is not None:
            log_timed_event(
                logger,
                "course.bootstrap",
                started_at,
                cache_hit=True,
                student_id=student_id,
                subject=subject,
                term=term,
                topics=len(list(cached.topics or [])),
                map_nodes=len(list(cached.nodes or [])),
                timeline=len(list(cached.intervention_timeline or [])),
            )
            return cached

        enrolled_subject_ids = [
            row[0]
            for row in self.db.execute(
                select(StudentSubject.subject_id).where(StudentSubject.student_profile_id == student_profile.id)
            ).all()
        ]
        personalized_lessons_available = self._personalized_lessons_available()

        if personalized_lessons_available:
            query = (
                select(Topic, PersonalizedLesson, Subject.slug)
                .join(Subject, Subject.id == Topic.subject_id)
                .outerjoin(
                    PersonalizedLesson,
                    (PersonalizedLesson.topic_id == Topic.id)
                    & (PersonalizedLesson.student_id == student_id),
                )
                .where(
                    Topic.is_approved.is_(True),
                    Topic.sss_level == student_profile.sss_level,
                    Topic.term == term,
                    Topic.subject_id.in_(enrolled_subject_ids),
                    Subject.slug == subject.lower(),
                )
                .order_by(Topic.created_at.asc(), Topic.title.asc())
            )
            rows = self.db.execute(query).all()
        else:
            query = (
                select(Topic, Subject.slug)
                .join(Subject, Subject.id == Topic.subject_id)
                .where(
                    Topic.is_approved.is_(True),
                    Topic.sss_level == student_profile.sss_level,
                    Topic.term == term,
                    Topic.subject_id.in_(enrolled_subject_ids),
                    Subject.slug == subject.lower(),
                )
                .order_by(Topic.created_at.asc(), Topic.title.asc())
            )
            rows = [(topic, None, subject_slug) for topic, subject_slug in self.db.execute(query).all()]

        rag_service = RagRetrieveService()
        map_visual = None
        map_error = None
        try:
            map_visual = learning_path_service.get_learning_map_visual(
                self.db,
                student_id=student_id,
                subject=subject,
                sss_level=student_profile.sss_level,
                term=term,
                view="topic",
            )
        except LearningPathValidationError as exc:
            map_error = str(exc)

        node_map = {
            str(node.topic_id): node
            for node in (map_visual.nodes if map_visual is not None else [])
        }
        evidence_summary = self._evidence_summary(list(map_visual.nodes) if map_visual is not None else [])
        next_step = map_visual.next_step if map_visual is not None else None
        recommended_topic_id = str(next_step.recommended_topic_id) if next_step and next_step.recommended_topic_id else None

        topics: list[CourseBootstrapTopicOut] = []
        readiness_failures: list[str] = []

        for topic, personalized_lesson, _subject_slug in rows:
            topic_id = str(topic.id)
            lesson_ready = _has_cached_personalized_lesson(personalized_lesson)
            unavailable_reason = None

            if not lesson_ready:
                try:
                    lesson_ready = rag_service.topic_has_chunks(
                        subject=subject,
                        sss_level=str(topic.sss_level),
                        term=int(topic.term),
                        topic_id=topic.id,
                        approved_only=True,
                        curriculum_version_id=topic.curriculum_version_id,
                    )
                except RagRetrieveServiceError as exc:
                    unavailable_reason = str(exc)
                    readiness_failures.append(topic_id)

            if not lesson_ready and unavailable_reason is None:
                unavailable_reason = "No approved curriculum chunks found for this topic/scope."

            node = node_map.get(topic_id)
            status = node.status if node is not None else ("ready" if lesson_ready else "locked")

            topics.append(
                CourseBootstrapTopicOut(
                    topic_id=topic_id,
                    title=str(topic.title),
                    description=(
                        personalized_lesson.summary
                        if personalized_lesson and personalized_lesson.summary
                        else _clean_topic_description(topic.description)
                    ),
                    lesson_title=personalized_lesson.title if personalized_lesson else None,
                    estimated_duration_minutes=(
                        personalized_lesson.estimated_duration_minutes if personalized_lesson else None
                    ),
                    lesson_ready=lesson_ready,
                    lesson_unavailable_reason=unavailable_reason,
                    sss_level=str(topic.sss_level),
                    term=int(topic.term),
                    subject_id=str(topic.subject_id),
                    status=status,
                    mastery_score=float(node.mastery_score) if node is not None else 0.0,
                    concept_label=str(node.concept_label) if node and node.concept_label else None,
                    graph_details=str(node.details) if node and node.details else None,
                    is_recommended=bool(recommended_topic_id and recommended_topic_id == topic_id),
                )
            )

        if not topics and readiness_failures and map_error is None:
            map_error = "Lesson readiness checks failed for this scope."
        if not personalized_lessons_available and map_error is None:
            map_error = "Personalized lesson cache was missing and has been recreated. Scope topics are loading from approved curriculum."

        warmed_topic_ids: list[str] = []
        cache_hit_topic_ids: list[str] = []
        failed_topic_ids: list[str] = []
        prewarm_topic_ids = self._candidate_prewarm_topic_ids(topics=topics, next_step=next_step)
        if prewarm_topic_ids:
            queued_job_id = PrewarmJobService(self.db).enqueue_lesson_related(
                student_id=student_id,
                subject=subject,
                sss_level=str(student_profile.sss_level),
                term=term,
                topic_ids=prewarm_topic_ids,
            )
            logger.info(
                "course.bootstrap.prewarm_queued student_id=%s subject=%s term=%s candidate_topic_ids=%s queued_job_id=%s",
                student_id,
                subject,
                term,
                [str(topic_id) for topic_id in prewarm_topic_ids],
                str(queued_job_id) if queued_job_id else "deduped_or_disabled",
            )

        recent_evidence = self._latest_scope_evidence(
            student_id=student_id,
            subject=subject,
            sss_level=str(student_profile.sss_level),
            term=term,
        )
        intervention_timeline = self._scope_intervention_timeline(
            student_id=student_id,
            subject=subject,
            sss_level=str(student_profile.sss_level),
            term=term,
        )
        recommendation_story = self._recommendation_story(
            next_step=next_step,
            recent_evidence=recent_evidence,
        )
        diagnostic_status, learning_gap_summary = self._scope_diagnostic_signal(
            db=self.db,
            student_id=student_id,
            subject=subject,
            sss_level=str(student_profile.sss_level),
            term=term,
        )
        initial_lesson_plan = self._initial_lesson_plan(
            next_step=next_step,
            recommendation_story=recommendation_story,
            gap_summary=learning_gap_summary,
        )

        payload = CourseBootstrapOut(
            student_id=student_id,
            subject=subject,  # type: ignore[arg-type]
            sss_level=str(student_profile.sss_level),  # type: ignore[arg-type]
            term=term,  # type: ignore[arg-type]
            topics=topics,
            nodes=list(map_visual.nodes) if map_visual is not None else [],
            edges=list(map_visual.edges) if map_visual is not None else [],
            next_step=next_step,
            recent_evidence=recent_evidence,
            intervention_timeline=intervention_timeline,
            recommendation_story=recommendation_story,
            evidence_summary=evidence_summary,
            diagnostic_status=diagnostic_status,
            learning_gap_summary=learning_gap_summary,
            initial_lesson_plan=initial_lesson_plan,
            map_error=map_error,
            warmed_topic_ids=warmed_topic_ids,
            cache_hit_topic_ids=cache_hit_topic_ids,
            failed_topic_ids=failed_topic_ids,
        )
        output = self._write_cached_bootstrap(cache_key=cache_key, payload=payload)
        log_timed_event(
            logger,
            "course.bootstrap",
            started_at,
            cache_hit=False,
            student_id=student_id,
            subject=subject,
            term=term,
            topics=len(topics),
            ready_topics=sum(1 for item in topics if item.lesson_ready),
            map_nodes=len(list(output.nodes or [])),
            map_edges=len(list(output.edges or [])),
            next_step=output.next_step.recommended_topic_id if output.next_step else "none",
            prewarm_candidates=len(prewarm_topic_ids),
            warmed_topics=len(warmed_topic_ids),
            cache_hit_topics=len(cache_hit_topic_ids),
            failed_topics=len(failed_topic_ids),
            map_error=bool(map_error),
        )
        return output
