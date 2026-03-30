"""Lesson service (scope enforcement + personalized lesson generation/cache)."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

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


class LessonNotFound(Exception):
    pass


class ForbiddenLessonAccess(Exception):
    pass


class LessonGenerationError(Exception):
    pass


GENERATOR_VERSION = "rag_mastery_v1"
ALLOWED_BLOCK_TYPES = {"text", "video", "image", "example", "exercise"}
LOW_VALUE_PHRASES = (
    "introduces the core ideas",
    "worked examples, and checkpoints",
    "needed for mastery progression",
)


@dataclass(frozen=True)
class _LLMAttempt:
    provider: str
    model: str
    api_key: str
    base_url: str | None = None


def _extract_json_object(raw: str) -> dict | None:
    content = (raw or "").strip()
    if not content:
        return None
    try:
        parsed = json.loads(content)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", content)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _normalize_generated_blocks(raw_blocks: Any) -> list[dict]:
    if not isinstance(raw_blocks, list):
        return []

    normalized: list[dict] = []
    for block in raw_blocks:
        if not isinstance(block, dict):
            continue
        block_type = str(block.get("type") or block.get("block_type") or "").strip().lower()
        if block_type not in ALLOWED_BLOCK_TYPES:
            continue

        if block_type in {"video", "image"}:
            url = block.get("url") or block.get("value")
            if url is None:
                continue
            normalized.append({"type": block_type, "url": str(url)})
            continue

        value = block.get("value")
        if value is None:
            if "content" in block:
                value = block["content"]
            elif "text" in block:
                value = block["text"]
        if value is None:
            continue
        if isinstance(value, str):
            value = _normalize_text(value)
            if not value:
                continue
        normalized.append({"type": block_type, "value": value})

    return normalized


def _map_legacy_lesson_blocks(lesson: Any) -> list[dict]:
    blocks = sorted(
        list(getattr(lesson, "blocks", []) or []),
        key=lambda item: int(getattr(item, "order_index", 0) or 0),
    )
    normalized: list[dict] = []
    for block in blocks:
        block_type = str(getattr(block, "block_type", "") or "").strip().lower()
        payload = getattr(block, "content", None) or {}
        if block_type not in ALLOWED_BLOCK_TYPES:
            continue
        if block_type in {"video", "image"}:
            url = ""
            if isinstance(payload, dict):
                url = str(payload.get("url") or payload.get("value") or "").strip()
            elif payload is not None:
                url = str(payload).strip()
            if url:
                normalized.append({"type": block_type, "url": url})
            continue

        value: Any = payload
        heading_applied = False
        if isinstance(payload, dict):
            heading = _normalize_text(str(payload.get("heading") or ""))
            value = payload.get("text")
            if value is None and "value" in payload:
                value = payload.get("value")
            if isinstance(value, str):
                value = _normalize_text(value)
                if heading and value:
                    value = f"{heading}\n\n{value}"
                    heading_applied = True
        if isinstance(value, str) and not heading_applied:
            value = _normalize_text(value)
        if value:
            normalized.append({"type": block_type, "value": value})
    return normalized


def _lesson_response_from_blocks(
    *,
    topic: Any,
    title: str,
    summary: str | None,
    estimated_duration_minutes: int | None,
    content_blocks: list[dict],
    graph_context: Any,
    covered_concepts: list[dict] | None = None,
) -> dict:
    prerequisites: list[dict] = []
    for node in list(getattr(graph_context, "prerequisite_concepts", []) or []):
        prerequisites.append(
            {
                "concept_id": str(node.concept_id),
                "label": str(node.label),
                "mastery_score": node.mastery_score,
                "mastery_state": node.mastery_state,
            }
        )

    weakest_concepts: list[dict] = []
    for node in list(getattr(graph_context, "weakest_concepts", []) or []):
        weakest_concepts.append(
            {
                "concept_id": str(node.concept_id),
                "label": str(node.label),
                "mastery_score": node.mastery_score,
                "mastery_state": node.mastery_state,
            }
        )

    next_unlock = None
    graph_next_unlock = getattr(graph_context, "next_unlock", None)
    if graph_next_unlock is not None:
        next_unlock = {
            "concept_id": graph_next_unlock.concept_id,
            "concept_label": graph_next_unlock.concept_label,
            "topic_id": graph_next_unlock.topic_id,
            "topic_title": graph_next_unlock.topic_title,
            "reason": graph_next_unlock.reason,
        }

    if covered_concepts is None:
        covered_concepts = []
        for node in list(getattr(graph_context, "current_concepts", []) or []):
            covered_concepts.append(
                {
                    "concept_id": str(node.concept_id),
                    "label": str(node.label),
                    "mastery_score": node.mastery_score,
                    "mastery_state": node.mastery_state,
                }
            )

    return {
        "topic_id": str(topic.id),
        "title": title,
        "summary": summary,
        "estimated_duration_minutes": estimated_duration_minutes,
        "content_blocks": content_blocks,
        "covered_concepts": covered_concepts,
        "prerequisites": prerequisites,
        "weakest_concepts": weakest_concepts,
        "next_unlock": next_unlock,
        "why_this_matters": getattr(graph_context, "why_this_matters", None),
        "assessment_ready": bool(getattr(graph_context, "current_concepts", []) or []),
    }


def _extract_block_texts(blocks: list[dict]) -> list[str]:
    texts: list[str] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        value = block.get("value")
        if isinstance(value, str):
            normalized = _normalize_text(value).lower()
            if normalized:
                texts.append(normalized)
        elif isinstance(value, dict):
            for key in ("note", "solution", "question", "expected_answer", "prompt"):
                inner = value.get(key)
                if isinstance(inner, str):
                    normalized = _normalize_text(inner).lower()
                    if normalized:
                        texts.append(normalized)
    return texts


def _extract_covered_concepts(rag_chunks: list[Any]) -> tuple[list[str], dict[str, str]]:
    covered_ids: list[str] = []
    covered_labels: dict[str, str] = {}
    seen: set[str] = set()

    for chunk in rag_chunks:
        metadata = dict(getattr(chunk, "metadata", None) or {})
        concept_id = str(metadata.get("concept_id") or "").strip()
        if not concept_id or concept_id in seen:
            continue
        seen.add(concept_id)
        covered_ids.append(concept_id)

        concept_label = (
            str(
                metadata.get("citation_concept_label")
                or metadata.get("concept_label")
                or ""
            ).strip()
        )
        if concept_label:
            covered_labels[concept_id] = concept_label

    return covered_ids, covered_labels


def _looks_low_value_lesson(*, title: str, summary: str | None, blocks: list[dict], topic_title: str) -> bool:
    corpus = " ".join(
        [
            _normalize_text(title).lower(),
            _normalize_text(summary or "").lower(),
            *_extract_block_texts(blocks),
        ]
    )
    if not corpus:
        return True

    marker_hits = sum(1 for marker in LOW_VALUE_PHRASES if marker in corpus)
    if marker_hits >= 2:
        return True

    texts = _extract_block_texts(blocks)
    unique = {t for t in texts if t}
    if texts and len(unique) <= max(1, len(texts) // 4):
        return True

    if _normalize_text(topic_title).lower() == _normalize_text(title).lower() and len(unique) <= 2:
        return True

    return False


def _is_truthy_env(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _is_retryable_llm_error(exc: Exception) -> bool:
    text = str(exc).lower()
    markers = (
        "rate limit",
        "rate_limit_exceeded",
        "insufficient_quota",
        "quota",
        "429",
        "too many requests",
        "service unavailable",
        "temporarily unavailable",
        "timed out",
        "timeout",
        "connection error",
    )
    return any(marker in text for marker in markers)


def _resolve_provider_api_key(provider: str) -> str:
    normalized = (provider or "").strip().lower()
    if normalized == "groq":
        key = os.getenv("GROQ_API_KEY", "").strip()
        if key:
            return key
    key = (os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()
    if key:
        return key
    if normalized == "groq":
        raise LessonGenerationError("No GROQ_API_KEY configured for Groq lesson generation.")
    raise LessonGenerationError("No OpenAI-compatible API key configured for lesson generation.")


def _build_lesson_llm_attempts() -> list[_LLMAttempt]:
    primary_provider = os.getenv("LLM_PROVIDER", "groq").strip().lower()
    primary_model = os.getenv("LESSON_LLM_MODEL", os.getenv("LLM_MODEL", "openai/gpt-oss-20b")).strip()
    if not primary_model:
        raise LessonGenerationError("LESSON_LLM_MODEL/LLM_MODEL is not configured.")

    attempts: list[_LLMAttempt] = [
        _LLMAttempt(
            provider=primary_provider,
            model=primary_model,
            api_key=_resolve_provider_api_key(primary_provider),
            base_url=(
                os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").strip()
                if primary_provider == "groq"
                else (
                    os.getenv("LLM_API_BASE", "").strip()
                    if primary_provider not in {"openai", ""}
                    else None
                )
            ),
        )
    ]

    fallback_enabled = _is_truthy_env(os.getenv("LESSON_OPENAI_FALLBACK_ENABLED"), default=True)
    fallback_key = (os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY") or "").strip()
    fallback_model = (
        os.getenv("LESSON_OPENAI_FALLBACK_MODEL")
        or os.getenv("OPENAI_LLM_MODEL")
        or "gpt-4o-mini"
    ).strip()

    if (
        fallback_enabled
        and primary_provider != "openai"
        and fallback_key
        and fallback_model
    ):
        attempts.append(
            _LLMAttempt(
                provider="openai",
                model=fallback_model,
                api_key=fallback_key,
                base_url=None,
            )
        )

    return attempts


def _resolve_llm_client(attempt: _LLMAttempt) -> tuple[Any, str, str]:
    try:
        from openai import OpenAI
    except ModuleNotFoundError as exc:
        raise LessonGenerationError("openai dependency is missing for lesson generation.") from exc

    try:
        client = OpenAI(api_key=attempt.api_key, base_url=attempt.base_url or None)
    except Exception as exc:
        raise LessonGenerationError(f"Failed to initialize lesson LLM client: {exc}") from exc
    return client, attempt.provider, attempt.model


def _request_lesson_generation(client: Any, *, model: str, prompt: str) -> Any:
    try:
        return client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception:
        return client.chat.completions.create(
            model=model,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )


def _get_mastery_rows(
    db: Session,
    *,
    student_id: uuid.UUID,
    subject: str,
    sss_level: str,
    term: int,
) -> list[StudentConceptMastery]:
    if db is None:
        return []
    stmt = (
        select(StudentConceptMastery)
        .where(
            StudentConceptMastery.student_id == student_id,
            StudentConceptMastery.subject == subject,
            StudentConceptMastery.sss_level == sss_level,
            StudentConceptMastery.term == term,
        )
        .order_by(StudentConceptMastery.mastery_score.asc(), StudentConceptMastery.updated_at.desc())
    )
    return list(db.execute(stmt).scalars().all())


def _mastery_signature(rows: list[StudentConceptMastery]) -> str:
    if not rows:
        return "no_mastery"
    payload = "|".join(
        f"{row.concept_id}:{float(row.mastery_score):.4f}:{row.updated_at.isoformat()}"
        for row in rows
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _retrieve_rag_context(
    *,
    topic_id: uuid.UUID,
    topic_title: str,
    subject: str,
    sss_level: str,
    term: int,
) -> tuple[list[Any], bool]:
    service = RagRetrieveService()
    query = f"{topic_title} explained with worked examples and practice for {sss_level} term {term}"

    topic_payload = InternalRagRetrieveRequest(
        query=query,
        subject=subject,  # type: ignore[arg-type]
        sss_level=sss_level,  # type: ignore[arg-type]
        term=term,
        topic_ids=[topic_id],
        top_k=8,
        approved_only=True,
    )
    response = service.retrieve(topic_payload)
    return response.chunks, False


def _build_generation_prompt(
    *,
    topic_title: str,
    subject: str,
    sss_level: str,
    term: int,
    preference: Any,
    mastery_rows: list[StudentConceptMastery],
    rag_chunks: list[Any],
) -> str:
    weak_concepts = [
        {"concept_id": row.concept_id, "mastery_score": round(float(row.mastery_score), 4)}
        for row in mastery_rows[:5]
    ]
    strong_concepts = [
        {"concept_id": row.concept_id, "mastery_score": round(float(row.mastery_score), 4)}
        for row in mastery_rows[-3:]
    ] if mastery_rows else []

    preference_payload = {
        "explanation_depth": getattr(preference, "explanation_depth", "standard"),
        "examples_first": bool(getattr(preference, "examples_first", False)),
        "pace": getattr(preference, "pace", "normal"),
    }

    context_lines: list[str] = []
    for chunk in rag_chunks[:8]:
        text = _normalize_text(str(chunk.text or ""))[:450]
        if not text:
            continue
        source_id = str(chunk.source_id or "")
        chunk_id = str(chunk.chunk_id or "")
        context_lines.append(f"- ({source_id}#{chunk_id}) {text}")

    total_context_chars = sum(len(line) for line in context_lines)
    if not context_lines:
        raise LessonGenerationError("No usable curriculum context was retrieved for lesson generation.")
    if len(context_lines) < 2 or total_context_chars < 300:
        raise LessonGenerationError(
            "Curriculum context is too sparse for reliable lesson generation for this topic."
        )

    return (
        "You generate curriculum-grounded lesson drafts for one student.\n"
        "Return JSON only. No markdown, no commentary.\n"
        "Do not fabricate facts outside the provided curriculum context.\n"
        "Use student preference and mastery weaknesses to shape explanation depth and pacing.\n\n"
        f"Scope: subject={subject}, level={sss_level}, term={term}, topic={topic_title}\n"
        f"Student preference: {json.dumps(preference_payload, ensure_ascii=True)}\n"
        f"Weak concepts: {json.dumps(weak_concepts, ensure_ascii=True)}\n"
        f"Strong concepts: {json.dumps(strong_concepts, ensure_ascii=True)}\n"
        "Curriculum evidence:\n"
        f"{chr(10).join(context_lines)}\n\n"
        "Return EXACT JSON shape:\n"
        "{\n"
        '  "title": "string",\n'
        '  "summary": "string",\n'
        '  "estimated_duration_minutes": 18,\n'
        '  "content_blocks": [\n'
        '    {"type":"text","value":"string"},\n'
        '    {"type":"example","value":{"prompt":"string","solution":"string","note":"string"}},\n'
        '    {"type":"exercise","value":{"question":"string","expected_answer":"string"}}\n'
        "  ]\n"
        "}\n"
        "Rules:\n"
        "- At least 4 blocks.\n"
        "- Keep blocks concise and teachable.\n"
        "- Ensure at least one worked example and one exercise.\n"
        "- Keep language clear for secondary school learners.\n"
        "- Use concrete details from retrieved evidence; avoid generic restatements.\n"
        "- Do not repeat placeholder wording like 'introduces core ideas'.\n"
    )


def _generate_personalized_lesson(
    *,
    topic_id: uuid.UUID,
    topic_title: str,
    subject: str,
    sss_level: str,
    term: int,
    preference: Any,
    mastery_rows: list[StudentConceptMastery],
) -> dict:
    try:
        rag_chunks, used_scope_fallback = _retrieve_rag_context(
            topic_id=topic_id,
            topic_title=topic_title,
            subject=subject,
            sss_level=sss_level,
            term=term,
        )
    except RagRetrieveServiceError as exc:
        raise LessonGenerationError(f"RAG retrieval failed: {exc}") from exc

    if not rag_chunks:
        raise LessonGenerationError(
            "No approved curriculum chunks found for this topic/scope. Ingest and approve curriculum first."
        )

    prompt = _build_generation_prompt(
        topic_title=topic_title,
        subject=subject,
        sss_level=sss_level,
        term=term,
        preference=preference,
        mastery_rows=mastery_rows,
        rag_chunks=rag_chunks,
    )
    content = ""
    provider = ""
    model = ""
    errors: list[str] = []
    attempts = _build_lesson_llm_attempts()

    for index, attempt in enumerate(attempts):
        client, provider, model = _resolve_llm_client(attempt)
        try:
            response = _request_lesson_generation(client, model=model, prompt=prompt)
            content = str(response.choices[0].message.content or "") if response.choices else ""
            logger.info(
                "lesson.generate.llm_success provider=%s model=%s fallback_used=%s attempt_index=%s",
                provider,
                model,
                index > 0,
                index,
            )
            break
        except Exception as exc:
            errors.append(f"{attempt.provider}:{attempt.model}: {exc}")
            has_more_attempts = index < len(attempts) - 1
            logger.warning(
                "lesson.generate.llm_failed provider=%s model=%s attempt_index=%s retryable=%s error=%s",
                attempt.provider,
                attempt.model,
                index,
                has_more_attempts and _is_retryable_llm_error(exc),
                exc,
            )
            if has_more_attempts and _is_retryable_llm_error(exc):
                continue
            raise LessonGenerationError(f"Lesson LLM generation failed: {exc}") from exc

    if not content and errors:
        raise LessonGenerationError("Lesson LLM generation failed: " + " | ".join(errors[:2]))

    parsed = _extract_json_object(content)
    if not parsed:
        preview = _normalize_text(content)[:220]
        raise LessonGenerationError(
            "Lesson LLM returned invalid JSON. "
            f"model={model}, provider={provider}, preview={preview!r}"
        )

    title = _normalize_text(str(parsed.get("title") or topic_title))[:255]
    summary = _normalize_text(str(parsed.get("summary") or ""))[:1200] or None

    raw_duration = parsed.get("estimated_duration_minutes")
    try:
        duration = int(raw_duration)
    except (TypeError, ValueError):
        duration = 20
    duration = max(8, min(duration, 90))

    blocks = _normalize_generated_blocks(parsed.get("content_blocks"))
    if len(blocks) < 3:
        raise LessonGenerationError("Lesson generation returned insufficient structured content blocks.")
    if _looks_low_value_lesson(title=title, summary=summary, blocks=blocks, topic_title=topic_title):
        raise LessonGenerationError(
            "Lesson generation quality check failed (generic output). Retry after re-ingestion or adjust LLM model."
        )

    source_chunk_ids = [str(chunk.chunk_id) for chunk in rag_chunks[:8] if str(chunk.chunk_id or "").strip()]
    covered_concept_ids, covered_concept_labels = _extract_covered_concepts(rag_chunks)
    metadata = {
        "generator_version": GENERATOR_VERSION,
        "provider": provider,
        "model": model,
        "used_scope_fallback": used_scope_fallback,
        "source_count": len(source_chunk_ids),
        "covered_concept_ids": covered_concept_ids,
        "covered_concept_labels": covered_concept_labels,
    }
    logger.info(
        "lesson.generate.success topic_id=%s provider=%s model=%s source_count=%s covered_concepts=%s scope_fallback=%s",
        topic_id,
        provider,
        model,
        len(source_chunk_ids),
        len(covered_concept_ids),
        used_scope_fallback,
    )
    return {
        "title": title,
        "summary": summary,
        "estimated_duration_minutes": duration,
        "content_blocks": blocks,
        "source_chunk_ids": source_chunk_ids,
        "generation_metadata": metadata,
    }


def fetch_topic_lesson(db: Session, topic_id: uuid.UUID, student_id: uuid.UUID) -> dict:
    started_at = now_ms()
    # 1) Student context (required for curriculum-bounded access)
    student_profile = get_student_profile(db, student_id)
    if not student_profile:
        raise ForbiddenLessonAccess("Student profile not found. Complete onboarding first.")

    # 2) Topic exists + subject info
    topic_subject = get_topic_with_subject(db, topic_id)
    if not topic_subject:
        raise LessonNotFound("Topic not found.")
    topic, subject = topic_subject
    subject_slug = str(subject.slug)

    # 3) Governance: approved only
    if not topic.is_approved:
        raise ForbiddenLessonAccess("Topic is not approved.")

    # 4) Scope enforcement: level + term
    if topic.sss_level != student_profile.sss_level:
        raise ForbiddenLessonAccess("Topic level out of scope for student.")
    if int(topic.term) != int(student_profile.active_term):
        raise ForbiddenLessonAccess("Topic term out of scope for student.")

    # 5) Enrollment enforcement: student must be enrolled in subject
    if not student_enrolled_in_subject(db, student_profile.id, topic.subject_id):
        raise ForbiddenLessonAccess("Student is not enrolled in this subject.")

    legacy_lesson = get_lesson_with_blocks(db, topic.id)
    legacy_blocks = _map_legacy_lesson_blocks(legacy_lesson) if legacy_lesson is not None else []

    # Explicitly require canonical curriculum mapping for lesson delivery.
    if not getattr(topic, "curriculum_version_id", None):
        raise LessonGenerationError(
            "No approved curriculum version mapped for this topic. Ingest and approve canonical curriculum JSON first."
        )

    ensure_personalized_lessons_table(db)
    mastery_rows = _get_mastery_rows(
        db,
        student_id=student_id,
        subject=subject_slug,
        sss_level=student_profile.sss_level,
        term=int(student_profile.active_term),
    )
    mastery_sig = _mastery_signature(mastery_rows)
    curriculum_version_id = topic.curriculum_version_id

    cached = get_personalized_lesson(db, student_id=student_id, topic_id=topic.id)
    graph_context = None
    try:
        from backend.services.lesson_graph_service import lesson_graph_service

        graph_context = lesson_graph_service.get_lesson_graph_context(
            db,
            student_id=student_id,
            subject=subject_slug,
            sss_level=student_profile.sss_level,
            term=int(student_profile.active_term),
            topic_id=topic.id,
        )
    except Exception as exc:  # pragma: no cover - lesson should still load if graph view is unavailable
        logger.warning("lesson.fetch.graph_context_unavailable topic_id=%s student_id=%s detail=%s", topic.id, student_id, exc)
    graph_status = getattr(graph_context, "status", None) if graph_context is not None else None

    if cached is not None:
        cached_meta = dict(cached.generation_metadata or {})
        if (
            cached.curriculum_version_id == curriculum_version_id
            and cached_meta.get("generator_version") == GENERATOR_VERSION
            and cached_meta.get("mastery_signature") == mastery_sig
            and isinstance(cached.content_blocks, list)
            and cached.content_blocks
        ):
            covered_concepts = []
            if graph_context is not None:
                current_ids = {
                    str(item.concept_id)
                    for item in graph_context.current_concepts
                }
                for concept_id in list(cached_meta.get("covered_concept_ids") or []):
                    if concept_id not in current_ids:
                        continue
                    node = next(
                        (item for item in graph_context.current_concepts if str(item.concept_id) == str(concept_id)),
                        None,
                    )
                    covered_concepts.append(
                        {
                            "concept_id": str(concept_id),
                            "label": (
                                cached_meta.get("covered_concept_labels", {}).get(str(concept_id))
                                or (node.label if node else str(concept_id))
                            ),
                            "mastery_score": node.mastery_score if node else None,
                            "mastery_state": node.mastery_state if node else None,
                        }
                    )
            log_timed_event(
                logger,
                "lesson.fetch",
                started_at,
                outcome="cache_hit",
                source="personalized_cache",
                student_id=student_id,
                topic_id=topic.id,
                subject=subject_slug,
                sss_level=student_profile.sss_level,
                term=int(student_profile.active_term),
                graph_status=graph_status,
                provider=cached_meta.get("provider"),
                model=cached_meta.get("model"),
                source_count=cached_meta.get("source_count"),
                covered_concepts=len(list(cached_meta.get("covered_concept_ids") or [])),
            )
            return _lesson_response_from_blocks(
                topic=topic,
                title=cached.title,
                summary=cached.summary,
                estimated_duration_minutes=cached.estimated_duration_minutes,
                content_blocks=list(cached.content_blocks),
                graph_context=graph_context,
                covered_concepts=covered_concepts,
            )

    if legacy_lesson is not None and legacy_blocks:
        logger.info(
            "lesson.fetch.structured_curriculum topic_id=%s student_id=%s curriculum_version_id=%s",
            topic.id,
            student_id,
            curriculum_version_id,
        )
        log_timed_event(
            logger,
            "lesson.fetch",
            started_at,
            outcome="structured",
            source="curriculum",
            student_id=student_id,
            topic_id=topic.id,
            subject=subject_slug,
            sss_level=student_profile.sss_level,
            term=int(student_profile.active_term),
            graph_status=graph_status,
        )
        return _lesson_response_from_blocks(
            topic=topic,
            title=str(getattr(legacy_lesson, "title", topic.title)),
            summary=getattr(legacy_lesson, "summary", None),
            estimated_duration_minutes=getattr(legacy_lesson, "estimated_duration_minutes", None),
            content_blocks=legacy_blocks,
            graph_context=graph_context,
        )

    generated = _generate_personalized_lesson(
        topic_id=topic.id,
        topic_title=topic.title,
        subject=subject_slug,
        sss_level=student_profile.sss_level,
        term=int(student_profile.active_term),
        preference=getattr(student_profile, "preference", None),
        mastery_rows=mastery_rows,
    )
    metadata = dict(generated["generation_metadata"])
    metadata["mastery_signature"] = mastery_sig
    logger.info(
        "lesson.fetch.generated topic_id=%s student_id=%s curriculum_version_id=%s mastery_sig=%s covered_concepts=%s",
        topic.id,
        student_id,
        curriculum_version_id,
        mastery_sig,
        len(list(metadata.get("covered_concept_ids") or [])),
    )
    log_timed_event(
        logger,
        "lesson.fetch",
        started_at,
        outcome="generated",
        source="llm",
        student_id=student_id,
        topic_id=topic.id,
        subject=subject_slug,
        sss_level=student_profile.sss_level,
        term=int(student_profile.active_term),
        graph_status=graph_status,
        provider=metadata.get("provider"),
        model=metadata.get("model"),
        source_count=metadata.get("source_count"),
        covered_concepts=len(list(metadata.get("covered_concept_ids") or [])),
    )

    upsert_personalized_lesson(
        db,
        student_id=student_id,
        topic_id=topic.id,
        curriculum_version_id=curriculum_version_id,
        title=str(generated["title"]),
        summary=generated["summary"],
        estimated_duration_minutes=int(generated["estimated_duration_minutes"]),
        content_blocks=list(generated["content_blocks"]),
        source_chunk_ids=list(generated["source_chunk_ids"]),
        generation_metadata=metadata,
    )
    db.commit()

    covered_concepts = []
    if graph_context is not None:
        current_ids = {
            str(item.concept_id)
            for item in graph_context.current_concepts
        }
        for concept_id in list(metadata.get("covered_concept_ids") or []):
            if concept_id not in current_ids:
                continue
            node = next(
                (item for item in graph_context.current_concepts if str(item.concept_id) == str(concept_id)),
                None,
            )
            covered_concepts.append(
                {
                    "concept_id": str(concept_id),
                    "label": (
                        metadata.get("covered_concept_labels", {}).get(str(concept_id))
                        or (node.label if node else str(concept_id))
                    ),
                    "mastery_score": node.mastery_score if node else None,
                    "mastery_state": node.mastery_state if node else None,
                }
            )

    return _lesson_response_from_blocks(
        topic=topic,
        title=str(generated["title"]),
        summary=generated["summary"],
        estimated_duration_minutes=int(generated["estimated_duration_minutes"]),
        content_blocks=list(generated["content_blocks"]),
        graph_context=graph_context,
        covered_concepts=covered_concepts,
    )
