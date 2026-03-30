from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from uuid import UUID

from backend.core.config import settings
from backend.core.database import SessionLocal
from backend.repositories.prewarm_job_repo import PrewarmJobRepository

logger = logging.getLogger(__name__)
_worker_thread: threading.Thread | None = None
_worker_stop_event = threading.Event()
_worker_lock = threading.Lock()


class PrewarmJobService:
    def __init__(self, db):
        self.db = db
        self.repo = PrewarmJobRepository(db)

    @staticmethod
    def _dedupe_key(*, job_type: str, payload: dict) -> str:
        normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(f"{job_type}:{normalized}".encode("utf-8")).hexdigest()

    @staticmethod
    def _lesson_related_payload(
        *,
        student_id: UUID,
        subject: str,
        sss_level: str,
        term: int,
        topic_ids: list[UUID],
    ) -> dict:
        normalized_topic_ids = sorted({str(topic_id) for topic_id in topic_ids if str(topic_id).strip()})
        return {
            "student_id": str(student_id),
            "subject": subject,
            "sss_level": sss_level,
            "term": int(term),
            "topic_ids": normalized_topic_ids,
        }

    @staticmethod
    def _course_scope_payload(
        *,
        student_id: UUID,
        subject: str,
        term: int,
    ) -> dict:
        return {
            "student_id": str(student_id),
            "subject": subject,
            "term": int(term),
        }

    def enqueue_lesson_related(
        self,
        *,
        student_id: UUID,
        subject: str,
        sss_level: str,
        term: int,
        topic_ids: list[UUID],
    ) -> UUID | None:
        if not settings.prewarm_queue_enabled:
            return None
        payload = self._lesson_related_payload(
            student_id=student_id,
            subject=subject,
            sss_level=sss_level,
            term=term,
            topic_ids=topic_ids,
        )
        if not payload["topic_ids"]:
            return None
        dedupe_key = self._dedupe_key(job_type="lesson_related", payload=payload)
        existing = self.repo.find_active_by_dedupe_key(job_type="lesson_related", dedupe_key=dedupe_key)
        if existing is not None:
            return existing.id
        return self.repo.create_job(
            job_type="lesson_related",
            dedupe_key=dedupe_key,
            payload=payload,
        ).id

    @classmethod
    def enqueue_lesson_related_job(
        cls,
        *,
        student_id: UUID,
        subject: str,
        sss_level: str,
        term: int,
        topic_ids: list[UUID],
    ) -> UUID | None:
        db = SessionLocal()
        try:
            return cls(db).enqueue_lesson_related(
                student_id=student_id,
                subject=subject,
                sss_level=sss_level,
                term=term,
                topic_ids=topic_ids,
            )
        finally:
            db.close()

    def enqueue_course_scope(
        self,
        *,
        student_id: UUID,
        subject: str,
        term: int,
    ) -> UUID | None:
        if not settings.prewarm_queue_enabled:
            return None
        payload = self._course_scope_payload(
            student_id=student_id,
            subject=subject,
            term=term,
        )
        dedupe_key = self._dedupe_key(job_type="course_scope", payload=payload)
        existing = self.repo.find_active_by_dedupe_key(job_type="course_scope", dedupe_key=dedupe_key)
        if existing is not None:
            return existing.id
        return self.repo.create_job(
            job_type="course_scope",
            dedupe_key=dedupe_key,
            payload=payload,
        ).id

    @classmethod
    def enqueue_course_scope_job(
        cls,
        *,
        student_id: UUID,
        subject: str,
        term: int,
    ) -> UUID | None:
        db = SessionLocal()
        try:
            return cls(db).enqueue_course_scope(
                student_id=student_id,
                subject=subject,
                term=term,
            )
        finally:
            db.close()

    @staticmethod
    def _process_lesson_related_job(payload: dict) -> None:
        from backend.services.course_experience_service import CourseExperienceService
        from backend.services.dashboard_experience_service import DashboardExperienceService
        from backend.services.lesson_experience_service import LessonExperienceService

        LessonExperienceService.prewarm_related_topics(
            student_id=UUID(str(payload["student_id"])),
            subject=str(payload["subject"]),
            sss_level=str(payload["sss_level"]),
            term=int(payload["term"]),
            topic_ids=[UUID(str(topic_id)) for topic_id in list(payload.get("topic_ids") or [])],
        )
        CourseExperienceService.prewarm_scope(
            student_id=UUID(str(payload["student_id"])),
            subject=str(payload["subject"]),
            term=int(payload["term"]),
        )
        DashboardExperienceService.prewarm(
            student_id=UUID(str(payload["student_id"])),
            subject=str(payload["subject"]),
        )

    @staticmethod
    def _process_course_scope_job(payload: dict) -> None:
        from backend.services.course_experience_service import CourseExperienceService
        from backend.services.dashboard_experience_service import DashboardExperienceService

        CourseExperienceService.prewarm_scope(
            student_id=UUID(str(payload["student_id"])),
            subject=str(payload["subject"]),
            term=int(payload["term"]),
        )
        DashboardExperienceService.prewarm(
            student_id=UUID(str(payload["student_id"])),
            subject=str(payload["subject"]),
        )

    @classmethod
    def process_once(cls, *, batch_size: int | None = None) -> int:
        processed = 0
        remaining = max(int(batch_size or settings.prewarm_worker_batch_size), 1)
        if not (_worker_thread and _worker_thread.is_alive()):
            recovered = cls.requeue_running_jobs()
            if recovered:
                logger.info("prewarm.job.recovered_stale_jobs count=%s", recovered)
        while remaining > 0:
            db = SessionLocal()
            try:
                repo = PrewarmJobRepository(db)
                job = repo.claim_next_job()
                if job is None:
                    break
                payload = dict(job.payload or {})
                if job.job_type == "lesson_related":
                    cls._process_lesson_related_job(payload)
                elif job.job_type == "course_scope":
                    cls._process_course_scope_job(payload)
                else:
                    raise RuntimeError(f"Unsupported prewarm job type: {job.job_type}")
                repo.mark_completed(job)
                processed += 1
                remaining -= 1
            except Exception as exc:  # pragma: no cover - worker safety
                if "repo" in locals() and "job" in locals() and job is not None:
                    try:
                        db.rollback()
                    except Exception:  # pragma: no cover - best-effort cleanup
                        logger.warning("prewarm.job.rollback_failed", exc_info=True)
                    try:
                        repo.mark_failed(job, error_message=str(exc))
                    except Exception:  # pragma: no cover - best-effort cleanup
                        try:
                            db.rollback()
                        except Exception:
                            logger.warning("prewarm.job.secondary_rollback_failed", exc_info=True)
                        logger.warning("prewarm.job.mark_failed_failed", exc_info=True)
                logger.warning("prewarm.job.process_failed detail=%s", exc)
                remaining -= 1
            finally:
                db.close()
        return processed

    @classmethod
    def requeue_running_jobs(cls) -> int:
        db = SessionLocal()
        try:
            repo = PrewarmJobRepository(db)
            requeue = getattr(repo, "requeue_running_jobs", None)
            if not callable(requeue):
                return 0
            return requeue()
        finally:
            db.close()

    @classmethod
    def snapshot(cls) -> dict:
        db = SessionLocal()
        try:
            counts = PrewarmJobRepository(db).queue_counts()
        finally:
            db.close()
        return {
            "status": "ok" if settings.prewarm_queue_enabled else "disabled",
            "worker_enabled": settings.prewarm_worker_enabled,
            "worker_alive": bool(_worker_thread and _worker_thread.is_alive()),
            "poll_seconds": settings.prewarm_worker_poll_seconds,
            "batch_size": settings.prewarm_worker_batch_size,
            "counts": counts,
        }


def _worker_loop() -> None:
    logger.info("prewarm.job.worker_started poll_seconds=%s batch_size=%s", settings.prewarm_worker_poll_seconds, settings.prewarm_worker_batch_size)
    while not _worker_stop_event.is_set():
        processed = PrewarmJobService.process_once(batch_size=settings.prewarm_worker_batch_size)
        if processed <= 0:
            _worker_stop_event.wait(max(settings.prewarm_worker_poll_seconds, 1.0))
    logger.info("prewarm.job.worker_stopped")


def start_prewarm_worker() -> None:
    global _worker_thread
    if os.getenv("PYTEST_CURRENT_TEST"):
        return
    if not settings.prewarm_queue_enabled or not settings.prewarm_worker_enabled:
        return
    with _worker_lock:
        if _worker_thread and _worker_thread.is_alive():
            return
        PrewarmJobService.requeue_running_jobs()
        _worker_stop_event.clear()
        _worker_thread = threading.Thread(target=_worker_loop, name="prewarm-job-worker", daemon=True)
        _worker_thread.start()


def stop_prewarm_worker() -> None:
    global _worker_thread
    with _worker_lock:
        if _worker_thread is None:
            return
        _worker_stop_event.set()
        _worker_thread.join(timeout=3.0)
        _worker_thread = None
