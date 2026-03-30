from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from backend.core.database import SessionLocal
from backend.core.telemetry import log_timed_event, now_ms
from backend.repositories.graph_repo import GraphRepository
from backend.repositories.tutor_session_repo import TutorSessionRepository
from backend.schemas.tutor_schema import (
    TutorPendingAssessmentOut,
    TutorQuickActionOut,
    TutorSessionBootstrapIn,
    TutorSessionBootstrapOut,
)
from backend.schemas.graph_learning_schema import LessonGraphContextOut
from backend.services.lesson_graph_service import LessonGraphValidationError, lesson_graph_service
from backend.services.lesson_service import fetch_topic_lesson
from backend.services.tutor_assessment_service import TutorAssessmentService

BOOTSTRAP_CACHE_TTL_SECONDS = 30.0
_BOOTSTRAP_CACHE: dict[str, tuple[float, TutorSessionBootstrapOut]] = {}
TOPIC_SNAPSHOT_CACHE_TTL_SECONDS = 180.0
_TOPIC_SNAPSHOT_CACHE: dict[str, tuple[float, "_TopicSnapshot"]] = {}
_PREVIEW_SESSION_ID = UUID("00000000-0000-0000-0000-000000000000")
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _TopicSnapshot:
    lesson: dict
    graph_context: object
    why_this_topic: str | None
    next_unlock: object | None
    graph_nodes: list
    graph_edges: list


class LessonExperienceService:
    def __init__(self, db: Session):
        self.db = db
        self.session_repo = TutorSessionRepository(db)
        self.assessment_service = TutorAssessmentService(db)

    def _get_or_create_session(self, *, payload: TutorSessionBootstrapIn) -> tuple[UUID, bool]:
        if payload.session_id and self.session_repo.session_exists_for_student(
            session_id=payload.session_id,
            student_id=payload.student_id,
        ):
            return payload.session_id, False

        row = self.session_repo.create_session(
            student_id=payload.student_id,
            subject=payload.subject,
            term=int(payload.term),
        )
        return UUID(str(row["id"])), True

    @staticmethod
    def _cache_key(*, payload: TutorSessionBootstrapIn, session_id: UUID) -> str:
        return ":".join(
            [
                str(payload.student_id),
                payload.subject,
                payload.sss_level,
                str(payload.term),
                str(payload.topic_id),
                str(session_id),
            ]
        )

    @staticmethod
    def _preview_cache_key(
        *,
        student_id: UUID,
        subject: str,
        sss_level: str,
        term: int,
        topic_id: UUID,
    ) -> str:
        return ":".join(
            [
                str(student_id),
                subject,
                sss_level,
                str(term),
                str(topic_id),
                "preview",
            ]
        )

    @staticmethod
    def _topic_snapshot_key(
        *,
        student_id: UUID,
        subject: str,
        sss_level: str,
        term: int,
        topic_id: UUID,
        mastery_signature: str,
    ) -> str:
        return ":".join(
            [
                str(student_id),
                subject,
                sss_level,
                str(term),
                str(topic_id),
                mastery_signature,
            ]
        )

    @staticmethod
    def _read_cached_bootstrap(*, cache_key: str) -> TutorSessionBootstrapOut | None:
        entry = _BOOTSTRAP_CACHE.get(cache_key)
        if entry is None:
            return None
        created_at, payload = entry
        if (time.time() - created_at) > BOOTSTRAP_CACHE_TTL_SECONDS:
            _BOOTSTRAP_CACHE.pop(cache_key, None)
            return None
        return payload

    @staticmethod
    def _write_cached_bootstrap(*, cache_key: str, payload: TutorSessionBootstrapOut) -> TutorSessionBootstrapOut:
        _BOOTSTRAP_CACHE[cache_key] = (time.time(), payload)
        return payload

    @staticmethod
    def _read_cached_topic_snapshot(*, cache_key: str) -> _TopicSnapshot | None:
        entry = _TOPIC_SNAPSHOT_CACHE.get(cache_key)
        if entry is None:
            return None
        created_at, payload = entry
        if (time.time() - created_at) > TOPIC_SNAPSHOT_CACHE_TTL_SECONDS:
            _TOPIC_SNAPSHOT_CACHE.pop(cache_key, None)
            return None
        return payload

    @staticmethod
    def _write_cached_topic_snapshot(*, cache_key: str, payload: _TopicSnapshot) -> _TopicSnapshot:
        _TOPIC_SNAPSHOT_CACHE[cache_key] = (time.time(), payload)
        return payload

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

    @classmethod
    def invalidate_topic_snapshot_cache(
        cls,
        *,
        student_id: UUID,
        subject: str,
        sss_level: str,
        term: int,
        topic_id: UUID | None = None,
    ) -> None:
        prefix = ":".join([str(student_id), subject, sss_level, str(term)])
        for key in list(_TOPIC_SNAPSHOT_CACHE.keys()):
            if not key.startswith(prefix):
                continue
            if topic_id is not None and f":{topic_id}:" not in key:
                continue
            _TOPIC_SNAPSHOT_CACHE.pop(key, None)

    @staticmethod
    def invalidate_session_cache(*, session_id: UUID) -> None:
        session_token = f":{session_id}"
        for key in [cache_key for cache_key in list(_BOOTSTRAP_CACHE.keys()) if cache_key.endswith(session_token)]:
            _BOOTSTRAP_CACHE.pop(key, None)

    @classmethod
    def cache_snapshot(cls) -> dict:
        cls._prune_cache()
        preview_entries = sum(1 for key in _BOOTSTRAP_CACHE if key.endswith(":preview"))
        return {
            "status": "ok",
            "bootstrap_cache": {
                "entries": len(_BOOTSTRAP_CACHE),
                "preview_entries": preview_entries,
                "ttl_seconds": BOOTSTRAP_CACHE_TTL_SECONDS,
            },
            "topic_snapshot_cache": {
                "entries": len(_TOPIC_SNAPSHOT_CACHE),
                "ttl_seconds": TOPIC_SNAPSHOT_CACHE_TTL_SECONDS,
            },
        }

    @classmethod
    def _prune_cache(cls) -> None:
        now = time.time()
        for cache_key, (created_at, _payload) in list(_BOOTSTRAP_CACHE.items()):
            if (now - created_at) > BOOTSTRAP_CACHE_TTL_SECONDS:
                _BOOTSTRAP_CACHE.pop(cache_key, None)
        for cache_key, (created_at, _payload) in list(_TOPIC_SNAPSHOT_CACHE.items()):
            if (now - created_at) > TOPIC_SNAPSHOT_CACHE_TTL_SECONDS:
                _TOPIC_SNAPSHOT_CACHE.pop(cache_key, None)

    @classmethod
    def _build_topic_snapshot(
        cls,
        *,
        db: Session,
        student_id: UUID,
        subject: str,
        sss_level: str,
        term: int,
        topic_id: UUID,
    ) -> tuple[_TopicSnapshot, str]:
        mastery_signature = cls._scope_mastery_signature(
            db=db,
            student_id=student_id,
            subject=subject,
            sss_level=sss_level,
            term=term,
        )
        cache_key = cls._topic_snapshot_key(
            student_id=student_id,
            subject=subject,
            sss_level=sss_level,
            term=term,
            topic_id=topic_id,
            mastery_signature=mastery_signature,
        )
        cached = cls._read_cached_topic_snapshot(cache_key=cache_key)
        if cached is not None:
            return cached, "cache"

        lesson = fetch_topic_lesson(db=db, topic_id=topic_id, student_id=student_id)
        try:
            graph_context = lesson_graph_service.get_lesson_graph_context(
                db,
                student_id=student_id,
                subject=subject,
                sss_level=sss_level,
                term=term,
                topic_id=topic_id,
            )
        except LessonGraphValidationError as exc:
            topic_title = str(lesson.get("title") or "Current Topic").strip() or "Current Topic"
            graph_context = LessonGraphContextOut(
                student_id=student_id,
                subject=subject,  # type: ignore[arg-type]
                sss_level=sss_level,  # type: ignore[arg-type]
                term=term,
                topic_id=str(topic_id),
                topic_title=topic_title,
                overall_mastery=0.0,
                status="unavailable",
                unavailable_reason=str(exc),
            )
        snapshot = _TopicSnapshot(
            lesson=lesson,
            graph_context=graph_context,
            why_this_topic=graph_context.why_this_matters,
            next_unlock=graph_context.next_unlock,
            graph_nodes=list(graph_context.graph_nodes),
            graph_edges=list(graph_context.graph_edges),
        )
        cls._write_cached_topic_snapshot(cache_key=cache_key, payload=snapshot)
        return snapshot, "fresh"

    @classmethod
    def prewarm_topics(
        cls,
        *,
        student_id: UUID,
        subject: str,
        sss_level: str,
        term: int,
        topic_ids: list[UUID],
    ) -> dict[str, list[str]]:
        result = {
            "warmed_topic_ids": [],
            "cache_hit_topic_ids": [],
            "failed_topic_ids": [],
        }
        if not topic_ids:
            return result
        db = SessionLocal()
        try:
            seen: set[str] = set()
            for topic_id in topic_ids:
                topic_token = str(topic_id)
                if not topic_token or topic_token in seen:
                    continue
                seen.add(topic_token)
                try:
                    _, source = cls._build_topic_snapshot(
                        db=db,
                        student_id=student_id,
                        subject=subject,
                        sss_level=sss_level,
                        term=term,
                        topic_id=topic_id,
                    )
                    logger.info(
                        "lesson.bootstrap.prewarm_success student_id=%s topic_id=%s subject=%s level=%s term=%s source=%s",
                        student_id,
                        topic_id,
                        subject,
                        sss_level,
                        term,
                        source,
                    )
                    if source == "cache":
                        result["cache_hit_topic_ids"].append(topic_token)
                    else:
                        result["warmed_topic_ids"].append(topic_token)
                except Exception as exc:  # pragma: no cover - best effort prewarm
                    db.rollback()
                    logger.warning(
                        "lesson.bootstrap.prewarm_failed student_id=%s topic_id=%s detail=%s",
                        student_id,
                        topic_id,
                        exc,
                    )
                    result["failed_topic_ids"].append(topic_token)
        finally:
            db.close()
        return result

    @classmethod
    def prewarm_bootstrap_preview(
        cls,
        *,
        student_id: UUID,
        subject: str,
        sss_level: str,
        term: int,
        topic_ids: list[UUID],
    ) -> dict[str, list[str]]:
        result = {
            "warmed_topic_ids": [],
            "cache_hit_topic_ids": [],
            "failed_topic_ids": [],
        }
        if not topic_ids:
            return result
        db = SessionLocal()
        try:
            seen: set[str] = set()
            service = cls(db)
            for topic_id in topic_ids:
                topic_token = str(topic_id)
                if not topic_token or topic_token in seen:
                    continue
                seen.add(topic_token)
                preview_key = cls._preview_cache_key(
                    student_id=student_id,
                    subject=subject,
                    sss_level=sss_level,
                    term=term,
                    topic_id=topic_id,
                )
                cached = cls._read_cached_bootstrap(cache_key=preview_key)
                if cached is not None:
                    result["cache_hit_topic_ids"].append(topic_token)
                    continue
                try:
                    snapshot, _ = cls._build_topic_snapshot(
                        db=db,
                        student_id=student_id,
                        subject=subject,
                        sss_level=sss_level,
                        term=term,
                        topic_id=topic_id,
                    )
                    bootstrap = service._build_bootstrap_payload(
                        payload=TutorSessionBootstrapIn(
                            student_id=student_id,
                            subject=subject,
                            sss_level=sss_level,
                            term=term,
                            topic_id=topic_id,
                            session_id=None,
                        ),
                        session_id=_PREVIEW_SESSION_ID,
                        session_started=False,
                        snapshot=snapshot,
                        pending_assessment=None,
                    )
                    cls._write_cached_bootstrap(cache_key=preview_key, payload=bootstrap)
                    result["warmed_topic_ids"].append(topic_token)
                except Exception as exc:  # pragma: no cover - best effort prewarm
                    db.rollback()
                    logger.warning(
                        "lesson.bootstrap.prewarm_preview_failed student_id=%s topic_id=%s detail=%s",
                        student_id,
                        topic_id,
                        exc,
                    )
                    result["failed_topic_ids"].append(topic_token)
        finally:
            db.close()
        return result

    @classmethod
    def prewarm_related_topics(
        cls,
        *,
        student_id: UUID,
        subject: str,
        sss_level: str,
        term: int,
        topic_ids: list[UUID],
    ) -> dict[str, list[str]]:
        result = cls.prewarm_topics(
            student_id=student_id,
            subject=subject,
            sss_level=sss_level,
            term=term,
            topic_ids=topic_ids,
        )
        preview = cls.prewarm_bootstrap_preview(
            student_id=student_id,
            subject=subject,
            sss_level=sss_level,
            term=term,
            topic_ids=topic_ids,
        )
        for key in ("warmed_topic_ids", "cache_hit_topic_ids", "failed_topic_ids"):
            merged = list(dict.fromkeys(list(result[key]) + list(preview[key])))
            result[key] = merged
        return result

    @staticmethod
    def _suggested_actions(topic_title: str) -> list[TutorQuickActionOut]:
        return [
            TutorQuickActionOut(
                id="teach-simple",
                label="Explain Simpler",
                prompt=f"Teach {topic_title} like I am new to it and keep it step-by-step.",
                icon="sparkles",
                intent="teach",
            ),
            TutorQuickActionOut(
                id="real-life-example",
                label="Real-life Example",
                prompt=f"Give me one real-life example that makes {topic_title} easy to understand.",
                icon="lightbulb",
                intent="teach",
            ),
            TutorQuickActionOut(
                id="why-this-topic",
                label="Why This Topic?",
                prompt=f"Why am I learning {topic_title} now, and what does it unlock next?",
                icon="git-branch",
                intent="diagnose",
            ),
            TutorQuickActionOut(
                id="checkpoint",
                label="1-Min Checkpoint",
                prompt=f"Ask me one focused question on {topic_title}.",
                icon="target",
                intent="assessment_start",
            ),
            TutorQuickActionOut(
                id="prereq-bridge",
                label="Connect to Previous Topic",
                prompt=f"Bridge the prerequisite idea I need before mastering {topic_title}.",
                icon="route",
                intent="socratic",
            ),
            TutorQuickActionOut(
                id="common-mistake",
                label="Common Mistake",
                prompt=f"Show me a common mistake students make in {topic_title} and fix it.",
                icon="shield-alert",
                intent="diagnose",
            ),
            TutorQuickActionOut(
                id="waec-mode",
                label="WAEC Mode",
                prompt=f"Give me one WAEC-style coaching explanation for {topic_title}.",
                icon="graduation-cap",
                intent="exam-practice",
            ),
            TutorQuickActionOut(
                id="recap",
                label="Recap",
                prompt=f"Recap {topic_title} in three sharp points and one memory hook.",
                icon="notebook-pen",
                intent="recap",
            ),
        ]

    def _build_bootstrap_payload(
        self,
        *,
        payload: TutorSessionBootstrapIn,
        session_id: UUID,
        session_started: bool,
        snapshot: _TopicSnapshot,
        pending_assessment: TutorPendingAssessmentOut | None,
    ) -> TutorSessionBootstrapOut:
        graph_context = snapshot.graph_context
        lesson = snapshot.lesson
        if graph_context.status == "unavailable":
            reason = str(graph_context.unavailable_reason or "Graph context is warming up.").strip()
            greeting = (
                f"You are in {lesson.get('title')}. "
                f"Graph context is unavailable right now: {reason} "
                "You can still review the lesson and try a checkpoint."
            )
        else:
            greeting = (
                f"You are in {lesson.get('title')}. "
                f"Your weakest focus here is {graph_context.weakest_concepts[0].label if graph_context.weakest_concepts else 'the current lesson core idea'}, "
                "and the graph is showing what unlocks next."
            )
        return TutorSessionBootstrapOut(
            session_id=session_id,
            session_started=session_started,
            greeting=greeting,
            topic_id=payload.topic_id,
            lesson=lesson,
            graph_context=graph_context,
            suggested_actions=self._suggested_actions(graph_context.topic_title),
            pending_assessment=pending_assessment,
            next_unlock=snapshot.next_unlock,
            why_this_topic=snapshot.why_this_topic,
            graph_nodes=snapshot.graph_nodes,
            graph_edges=snapshot.graph_edges,
            assessment_ready=bool(graph_context.current_concepts),
        )

    def bootstrap(self, payload: TutorSessionBootstrapIn) -> TutorSessionBootstrapOut:
        started_at = now_ms()
        preview = None
        if payload.session_id is None:
            preview = self._read_cached_bootstrap(
                cache_key=self._preview_cache_key(
                    student_id=payload.student_id,
                    subject=payload.subject,
                    sss_level=payload.sss_level,
                    term=int(payload.term),
                    topic_id=payload.topic_id,
                )
            )

        session_id, session_started = self._get_or_create_session(payload=payload)
        cache_key = self._cache_key(payload=payload, session_id=session_id)
        cached = self._read_cached_bootstrap(cache_key=cache_key)
        if cached is not None:
            log_timed_event(
                logger,
                "lesson.bootstrap",
                started_at,
                cache_hit=True,
                source="session_cache",
                student_id=payload.student_id,
                session_id=session_id,
                topic_id=payload.topic_id,
                session_started=session_started,
                assessment_ready=bool(cached.assessment_ready),
            )
            if session_started:
                return cached.model_copy(update={"session_started": True, "session_id": session_id})
            return cached

        pending_state = self.assessment_service.get_pending_assessment(session_id=session_id)
        pending_assessment = None
        if pending_state is not None:
            pending_assessment = TutorPendingAssessmentOut(
                assessment_id=UUID(str(pending_state["assessment_id"])),
                question=str(pending_state.get("question") or ""),
                concept_id=str(pending_state.get("concept_id") or ""),
                concept_label=str(pending_state.get("concept_label") or ""),
                hint=str(pending_state.get("hint") or "").strip() or None,
                difficulty=str(pending_state.get("difficulty") or "").strip() or None,
            )

        if preview is not None:
            bootstrap = preview.model_copy(
                update={
                    "session_id": session_id,
                    "session_started": session_started,
                    "pending_assessment": pending_assessment,
                }
            )
            log_timed_event(
                logger,
                "lesson.bootstrap",
                started_at,
                cache_hit=False,
                source="preview_cache",
                student_id=payload.student_id,
                session_id=session_id,
                topic_id=payload.topic_id,
                session_started=session_started,
                pending_assessment=bool(pending_assessment),
                graph_nodes=len(list(bootstrap.graph_nodes or [])),
            )
            return self._write_cached_bootstrap(cache_key=cache_key, payload=bootstrap)

        snapshot, snapshot_source = self._build_topic_snapshot(
            db=self.db,
            student_id=payload.student_id,
            subject=payload.subject,
            sss_level=payload.sss_level,
            term=int(payload.term),
            topic_id=payload.topic_id,
        )

        bootstrap = self._build_bootstrap_payload(
            payload=payload,
            session_id=session_id,
            session_started=session_started,
            snapshot=snapshot,
            pending_assessment=pending_assessment,
        )
        output = self._write_cached_bootstrap(cache_key=cache_key, payload=bootstrap)
        lesson_context_source = None
        if isinstance(snapshot.lesson, dict):
            lesson_context_source = str(snapshot.lesson.get("context_source") or "").strip() or None
        log_timed_event(
            logger,
            "lesson.bootstrap",
            started_at,
            cache_hit=False,
            source=snapshot_source,
            student_id=payload.student_id,
            session_id=session_id,
            topic_id=payload.topic_id,
            session_started=session_started,
            pending_assessment=bool(pending_assessment),
            graph_nodes=len(list(output.graph_nodes or [])),
            graph_edges=len(list(output.graph_edges or [])),
            assessment_ready=bool(output.assessment_ready),
            lesson_context_source=lesson_context_source or "response_model",
        )
        return output


lesson_experience_service = LessonExperienceService
