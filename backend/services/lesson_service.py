"""Lesson service (scope enforcement + remote AI Core generation)."""

from __future__ import annotations

import httpx
import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.telemetry import log_timed_event, now_ms
from backend.models.student_concept_mastery import StudentConceptMastery
from backend.repositories.lesson_repo import (
    ensure_personalized_lessons_table,
    get_lesson_with_blocks,
    get_personalized_lesson,
    get_student_profile,
    get_topic_with_subject,
    student_enrolled_in_subject,
    upsert_personalized_lesson,
)
from backend.schemas.internal_rag_schema import InternalRagRetrieveRequest
from backend.services.rag_retrieve_service import RagRetrieveService, RagRetrieveServiceError

logger = logging.getLogger(__name__)

class LessonNotFound(Exception): pass
class ForbiddenLessonAccess(Exception): pass
class LessonGenerationError(Exception): pass

GENERATOR_VERSION = "rag_mastery_v2"
ALLOWED_BLOCK_TYPES = {"text", "video", "image", "example", "exercise"}

def _normalize_text(value: str) -> str:
    return value.strip() if value else ""

def _lesson_response_from_blocks(*, topic, title, summary, estimated_duration_minutes, content_blocks, graph_context, covered_concepts=None):
    # Formats the final dictionary for the frontend
    return {
        "topic_id": str(topic.id),
        "title": title,
        "summary": summary,
        "estimated_duration_minutes": estimated_duration_minutes,
        "content_blocks": content_blocks,
        "covered_concepts": covered_concepts or [],
        "why_this_matters": getattr(graph_context, "why_this_matters", None),
        "assessment_ready": bool(getattr(graph_context, "current_concepts", [])),
    }

def _get_mastery_rows(db: Session, *, student_id: uuid.UUID, subject: str, sss_level: str, term: int) -> list[StudentConceptMastery]:
    stmt = select(StudentConceptMastery).where(
        StudentConceptMastery.student_id == student_id,
        StudentConceptMastery.subject == subject,
        StudentConceptMastery.sss_level == sss_level,
        StudentConceptMastery.term == term,
    ).order_by(StudentConceptMastery.mastery_score.asc())
    return list(db.execute(stmt).scalars().all())

def _mastery_signature(rows: list[StudentConceptMastery]) -> str:
    if not rows: return "no_mastery"
    payload = "|".join([f"{r.concept_id}:{float(r.mastery_score):.4f}" for r in rows])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]

def _retrieve_rag_context(*, topic_id: uuid.UUID, topic_title: str, subject: str, sss_level: str, term: int):
    service = RagRetrieveService()
    query = f"{topic_title} for {sss_level} term {term}"
    payload = InternalRagRetrieveRequest(
        query=query, subject=subject, sss_level=sss_level, term=term, topic_ids=[topic_id], top_k=8, approved_only=True
    )
    response = service.retrieve(payload)
    return response.chunks

async def _generate_personalized_lesson(*, topic_id, topic_title, subject, sss_level, term, preference, mastery_rows) -> dict:
    """Calls the AI Core to generate the actual lesson content."""
    rag_chunks = _retrieve_rag_context(topic_id=topic_id, topic_title=topic_title, subject=subject, sss_level=sss_level, term=term)
    if not rag_chunks:
        raise LessonGenerationError("No curriculum context found.")

    # Prepare payload for AI Core
    weak_concepts = [{"id": r.concept_id, "score": float(r.mastery_score)} for r in mastery_rows[:5]]
    curriculum_context = [c.text for c in rag_chunks if c.text]
    
    payload = {
        "topic_id": str(topic_id),
        "topic_title": topic_title,
        "subject": subject,
        "sss_level": sss_level,
        "term": term,
        "preferences": {
            "depth": getattr(preference, "explanation_depth", "standard"),
            "pace": getattr(preference, "pace", "normal")
        },
        "mastery_gaps": weak_concepts,
        "curriculum_context": curriculum_context
    }

    async with httpx.AsyncClient(timeout=90.0) as client:
        try:
            response = await client.post(
                f"{settings.ai_core_base_url.rstrip('/')}/lesson/generate",
                json=payload,
                headers={"X-Internal-Service-Key": settings.internal_service_key}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Remote Lesson Generation Failed: {e}")
            raise LessonGenerationError(f"AI Core unreachable: {e}")

async def fetch_topic_lesson(db: Session, topic_id: uuid.UUID, student_id: uuid.UUID) -> dict:
    """Main entrypoint. Now Async to support remote AI Core calls."""
    started_at = now_ms()
    profile = get_student_profile(db, student_id)
    if not profile: raise ForbiddenLessonAccess("Profile not found.")

    topic_subject = get_topic_with_subject(db, topic_id)
    if not topic_subject: raise LessonNotFound("Topic not found.")
    topic, subject = topic_subject
    
    mastery_rows = _get_mastery_rows(db, student_id=student_id, subject=subject.slug, sss_level=profile.sss_level, term=int(profile.active_term))
    mastery_sig = _mastery_signature(mastery_rows)

    # 1. Check Cache
    cached = get_personalized_lesson(db, student_id=student_id, topic_id=topic.id)
    if cached and dict(cached.generation_metadata or {}).get("mastery_signature") == mastery_sig:
        return _lesson_response_from_blocks(topic=topic, title=cached.title, summary=cached.summary, 
                                            estimated_duration_minutes=cached.estimated_duration_minutes, 
                                            content_blocks=list(cached.content_blocks), graph_context=None)

    # 2. Generate Fresh via AI Core
    generated = await _generate_personalized_lesson(topic_id=topic.id, topic_title=topic.title, subject=subject.slug,
                                                    sss_level=profile.sss_level, term=int(profile.active_term),
                                                    preference=getattr(profile, "preference", None), mastery_rows=mastery_rows)

    # 3. Save to Cache & Return
    metadata = {**generated.get("generation_metadata", {}), "mastery_signature": mastery_sig, "generator_version": GENERATOR_VERSION}
    upsert_personalized_lesson(db, student_id=student_id, topic_id=topic.id, curriculum_version_id=topic.curriculum_version_id,
                               title=generated["title"], summary=generated["summary"], 
                               estimated_duration_minutes=generated["estimated_duration_minutes"],
                               content_blocks=generated["content_blocks"], source_chunk_ids=[], generation_metadata=metadata)
    db.commit()
    
    return _lesson_response_from_blocks(topic=topic, title=generated["title"], summary=generated["summary"],
                                        estimated_duration_minutes=generated["estimated_duration_minutes"],
                                        content_blocks=generated["content_blocks"], graph_context=None)