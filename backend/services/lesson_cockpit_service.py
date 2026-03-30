from __future__ import annotations

import hashlib
import json
import logging
import time
from uuid import UUID

from sqlalchemy.orm import Session

from backend.repositories.graph_repo import GraphRepository
from backend.core.telemetry import log_timed_event, now_ms
from backend.schemas.graph_learning_schema import WhyThisTopicOut
from backend.schemas.lesson_cockpit_schema import LessonCockpitBootstrapIn, LessonCockpitBootstrapOut
from backend.schemas.tutor_schema import TutorSessionBootstrapIn
from backend.services.course_experience_service import CourseExperienceService
from backend.services.lesson_experience_service import LessonExperienceService
from backend.services.prewarm_job_service import PrewarmJobService


COCKPIT_CACHE_TTL_SECONDS = 30.0
_LESSON_COCKPIT_CACHE: dict[str, tuple[float, LessonCockpitBootstrapOut]] = {}
logger = logging.getLogger(__name__)


class LessonCockpitService:
    def __init__(self, db: Session):
        self.db = db
        self.course_service = CourseExperienceService(db)
        self.lesson_service = LessonExperienceService(db)

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
        topic_id: UUID,
        session_id: UUID | None,
        mastery_signature: str,
    ) -> str:
        session_token = str(session_id) if session_id else "auto"
        return ":".join(
            [
                str(student_id),
                subject,
                sss_level,
                str(term),
                str(topic_id),
                session_token,
                mastery_signature,
            ]
        )

    @staticmethod
    def _read_cached_bootstrap(*, cache_key: str) -> LessonCockpitBootstrapOut | None:
        entry = _LESSON_COCKPIT_CACHE.get(cache_key)
        if entry is None:
            return None
        created_at, payload = entry
        if (time.time() - created_at) > COCKPIT_CACHE_TTL_SECONDS:
            _LESSON_COCKPIT_CACHE.pop(cache_key, None)
            return None
        return payload

    @staticmethod
    def _write_cached_bootstrap(*, cache_key: str, payload: LessonCockpitBootstrapOut) -> LessonCockpitBootstrapOut:
        _LESSON_COCKPIT_CACHE[cache_key] = (time.time(), payload)
        return payload

    @classmethod
    def invalidate_scope_cache(
        cls,
        *,
        student_id: UUID,
        subject: str,
        sss_level: str,
        term: int,
        topic_id: UUID | None = None,
    ) -> None:
        prefix = ":".join([str(student_id), subject, sss_level, str(term)])
        for cache_key in list(_LESSON_COCKPIT_CACHE.keys()):
            if not cache_key.startswith(prefix):
                continue
            if topic_id is not None and f":{topic_id}:" not in cache_key:
                continue
            _LESSON_COCKPIT_CACHE.pop(cache_key, None)

    @staticmethod
    def invalidate_session_cache(*, session_id: UUID) -> None:
        session_token = f":{session_id}:"
        for cache_key in list(_LESSON_COCKPIT_CACHE.keys()):
            if session_token in cache_key:
                _LESSON_COCKPIT_CACHE.pop(cache_key, None)

    @classmethod
    def cache_snapshot(cls) -> dict:
        cls._prune_cache()
        return {
            "status": "ok",
            "bootstrap_cache": {
                "entries": len(_LESSON_COCKPIT_CACHE),
                "ttl_seconds": COCKPIT_CACHE_TTL_SECONDS,
            },
        }

    @classmethod
    def _prune_cache(cls) -> None:
        now = time.time()
        for cache_key, (created_at, _payload) in list(_LESSON_COCKPIT_CACHE.items()):
            if (now - created_at) > COCKPIT_CACHE_TTL_SECONDS:
                _LESSON_COCKPIT_CACHE.pop(cache_key, None)

    @staticmethod
    def _why_topic_detail(*, payload: LessonCockpitBootstrapIn, tutor_bootstrap) -> WhyThisTopicOut:
        graph_context = tutor_bootstrap.graph_context
        status = getattr(graph_context, "status", "ready")
        unavailable_reason = graph_context.unavailable_reason if status == "unavailable" else None
        weakest_prerequisite = min(
            list(graph_context.prerequisite_concepts or []),
            key=lambda item: item.mastery_score,
            default=None,
        )
        return WhyThisTopicOut(
            student_id=payload.student_id,
            subject=payload.subject,  # type: ignore[arg-type]
            sss_level=payload.sss_level,  # type: ignore[arg-type]
            term=payload.term,
            topic_id=str(graph_context.topic_id),
            topic_title=str(graph_context.topic_title),
            status=status,
            unavailable_reason=unavailable_reason,
            explanation=(
                unavailable_reason
                if status == "unavailable"
                else (
                    graph_context.why_this_matters
                    or f"{graph_context.topic_title} connects your prerequisites to what unlocks next."
                )
            ),
            prerequisite_labels=[item.label for item in list(graph_context.prerequisite_concepts or [])],
            unlock_labels=[item.label for item in list(graph_context.downstream_concepts or [])],
            weakest_prerequisite_label=(weakest_prerequisite.label if weakest_prerequisite is not None else None),
            recommended_next=tutor_bootstrap.next_unlock,
        )

    def bootstrap(self, payload: LessonCockpitBootstrapIn) -> LessonCockpitBootstrapOut:
        started_at = now_ms()
        mastery_signature = self._scope_mastery_signature(
            db=self.db,
            student_id=payload.student_id,
            subject=payload.subject,
            sss_level=payload.sss_level,
            term=int(payload.term),
        )
        cache_key = self._cache_key(
            student_id=payload.student_id,
            subject=payload.subject,
            sss_level=payload.sss_level,
            term=int(payload.term),
            topic_id=payload.topic_id,
            session_id=payload.session_id,
            mastery_signature=mastery_signature,
        )
        cached = self._read_cached_bootstrap(cache_key=cache_key)
        if cached is not None:
            log_timed_event(
                logger,
                "lesson.cockpit.bootstrap",
                started_at,
                cache_hit=True,
                student_id=payload.student_id,
                topic_id=payload.topic_id,
                subject=payload.subject,
                term=int(payload.term),
                warmed_topics=len(list(cached.warmed_topic_ids or [])),
            )
            return cached

        course_bootstrap = self.course_service.bootstrap(
            student_id=payload.student_id,
            subject=payload.subject,
            term=int(payload.term),
        )
        tutor_bootstrap = self.lesson_service.bootstrap(
            TutorSessionBootstrapIn(
                student_id=payload.student_id,
                subject=payload.subject,
                sss_level=payload.sss_level,
                term=payload.term,
                topic_id=payload.topic_id,
                session_id=payload.session_id,
            )
        )

        course_topics = list(course_bootstrap.topics)
        current_index = next(
            (index for index, topic in enumerate(course_topics) if str(topic.topic_id) == str(payload.topic_id)),
            -1,
        )
        candidate_ids: list[UUID] = []

        def _append_topic(topic_id: str | None) -> None:
            if not topic_id:
                return
            try:
                parsed = UUID(str(topic_id))
            except (TypeError, ValueError):
                return
            if parsed == payload.topic_id:
                return
            if parsed in candidate_ids:
                return
            candidate_ids.append(parsed)

        if current_index >= 0:
            if current_index + 1 < len(course_topics):
                _append_topic(course_topics[current_index + 1].topic_id)
            if current_index - 1 >= 0:
                _append_topic(course_topics[current_index - 1].topic_id)

        _append_topic(course_bootstrap.next_step.recommended_topic_id if course_bootstrap.next_step else None)
        _append_topic(tutor_bootstrap.next_unlock.topic_id if tutor_bootstrap.next_unlock else None)
        weakest_prereq_topic_id = next(
            (item.topic_id for item in tutor_bootstrap.graph_context.prerequisite_concepts if item.topic_id),
            None,
        )
        _append_topic(weakest_prereq_topic_id)

        prewarm = LessonExperienceService.prewarm_related_topics(
            student_id=payload.student_id,
            subject=payload.subject,
            sss_level=payload.sss_level,
            term=int(payload.term),
            topic_ids=candidate_ids,
        )
        PrewarmJobService(self.db).enqueue_lesson_related(
            student_id=payload.student_id,
            subject=payload.subject,
            sss_level=payload.sss_level,
            term=int(payload.term),
            topic_ids=candidate_ids,
        )
        why_topic_detail = self._why_topic_detail(payload=payload, tutor_bootstrap=tutor_bootstrap)

        output = self._write_cached_bootstrap(
            cache_key=cache_key,
            payload=LessonCockpitBootstrapOut(
                student_id=payload.student_id,
                topic_id=payload.topic_id,
                subject=payload.subject,
                sss_level=payload.sss_level,
                term=payload.term,
                topics=course_topics,
                next_step=course_bootstrap.next_step,
                recent_evidence=course_bootstrap.recent_evidence,
                intervention_timeline=course_bootstrap.intervention_timeline,
                map_error=course_bootstrap.map_error,
                tutor_bootstrap=tutor_bootstrap,
                why_topic_detail=why_topic_detail,
                warmed_topic_ids=prewarm["warmed_topic_ids"],
                cache_hit_topic_ids=prewarm["cache_hit_topic_ids"],
                failed_topic_ids=prewarm["failed_topic_ids"],
            ),
        )
        log_timed_event(
            logger,
            "lesson.cockpit.bootstrap",
            started_at,
            cache_hit=False,
            student_id=payload.student_id,
            topic_id=payload.topic_id,
            subject=payload.subject,
            term=int(payload.term),
            warmed_topics=len(list(output.warmed_topic_ids or [])),
            cache_hit_topics=len(list(output.cache_hit_topic_ids or [])),
            failed_topics=len(list(output.failed_topic_ids or [])),
            prerequisites=len(list(output.tutor_bootstrap.graph_context.prerequisite_concepts or [])),
            downstream=len(list(output.tutor_bootstrap.graph_context.downstream_concepts or [])),
        )
        return output
