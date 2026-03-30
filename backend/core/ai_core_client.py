from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import httpx

from backend.core.config import settings
from backend.core.telemetry import log_timed_event, now_ms

logger = logging.getLogger(__name__)


class AICoreClientError(RuntimeError):
    """Base ai-core integration error."""


class AICoreUnavailableError(AICoreClientError):
    """ai-core base URL is missing or unreachable."""


class AICoreProviderError(AICoreClientError):
    """ai-core request failed with network/http errors."""


class AICoreContractError(AICoreClientError):
    """ai-core returned payload that violates expected contract."""


def _coerce_question(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise AICoreContractError("Question payload must be an object")

    raw_id = raw.get("id")
    try:
        question_id = UUID(str(raw_id))
    except (TypeError, ValueError) as exc:
        raise AICoreContractError("Question id must be a valid UUID") from exc

    text = str(raw.get("text") or raw.get("question_text") or "").strip()
    if not text:
        raise AICoreContractError("Question text is required")

    raw_options = raw.get("options")
    if raw_options is None:
        options: list[str] = []
    elif isinstance(raw_options, list):
        options = [str(item) for item in raw_options]
    else:
        raise AICoreContractError("Question options must be a list")

    raw_concept = raw.get("concept_id")
    concept_id = str(raw_concept).strip() if raw_concept is not None else ""
    if not concept_id:
        raise AICoreContractError("Question concept_id is required")

    difficulty = str(raw.get("difficulty") or "").strip().lower()
    if difficulty not in {"easy", "medium", "hard"}:
        raise AICoreContractError("Question difficulty must be one of easy|medium|hard")

    correct_answer = raw.get("correct_answer")
    if correct_answer is not None:
        correct_answer = str(correct_answer).strip()

    return {
        "id": question_id,
        "text": text,
        "options": options,
        "correct_answer": correct_answer,
        "concept_id": concept_id,
        "difficulty": difficulty,
    }


async def generate_quiz_questions(
    *,
    student_id: UUID | None,
    subject: str,
    sss_level: str,
    term: int,
    topic_id,
    purpose: str,
    difficulty: str,
    num_questions: int,
) -> list[dict[str, Any]]:
    """Fetch quiz questions from ai-core with strict response validation."""
    started_at = now_ms()
    base_url = settings.ai_core_base_url.rstrip("/")
    if not base_url:
        raise AICoreUnavailableError("AI_CORE_BASE_URL is not configured")

    payload = {
        "student_id": str(student_id) if student_id else None,
        "subject": subject,
        "sss_level": sss_level,
        "term": term,
        "topic_id": str(topic_id),
        "purpose": purpose,
        "difficulty": difficulty,
        "num_questions": num_questions,
    }

    try:
        async with httpx.AsyncClient(timeout=settings.ai_core_timeout_seconds) as client:
            response = await client.post(f"{base_url}/quiz/generate", json=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        log_timed_event(
            logger,
            "ai_core.quiz.generate",
            started_at,
            log_level=logging.WARNING,
            outcome="http_error",
            student_id=student_id or "none",
            topic_id=topic_id,
            subject=subject,
            detail=str(exc),
        )
        raise AICoreProviderError(f"ai-core /quiz/generate failed: {exc}") from exc

    questions = data.get("questions") if isinstance(data, dict) else None
    if not isinstance(questions, list) or not questions:
        raise AICoreContractError("ai-core /quiz/generate returned empty or invalid questions payload")

    normalized_questions = [_coerce_question(item) for item in questions]
    if num_questions > 0:
        normalized_questions = normalized_questions[:num_questions]
    if not normalized_questions:
        raise AICoreContractError("ai-core /quiz/generate produced no valid questions after validation")
    log_timed_event(
        logger,
        "ai_core.quiz.generate",
        started_at,
        outcome="success",
        student_id=student_id or "none",
        topic_id=topic_id,
        subject=subject,
        questions=len(normalized_questions),
    )
    return normalized_questions


async def generate_quiz_insights(quiz_id, attempt_id) -> list[str]:
    """Fetch insight text from ai-core, returning no insights when unavailable."""
    started_at = now_ms()
    base_url = settings.ai_core_base_url.rstrip("/")
    if not base_url:
        logger.warning("ai-core insights unavailable: AI_CORE_BASE_URL is not configured")
        return []

    try:
        async with httpx.AsyncClient(timeout=settings.ai_core_timeout_seconds) as client:
            response = await client.get(f"{base_url}/quiz/{quiz_id}/attempt/{attempt_id}/insights")
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        logger.warning("ai-core insights call failed, returning no insights: %s", exc)
        return []

    insights = data.get("insights") if isinstance(data, dict) else None
    if isinstance(insights, list) and insights:
        log_timed_event(
            logger,
            "ai_core.quiz.insights",
            started_at,
            outcome="success",
            quiz_id=quiz_id,
            attempt_id=attempt_id,
            insights=len(insights),
        )
        return [str(item) for item in insights]

    log_timed_event(
        logger,
        "ai_core.quiz.insights",
        started_at,
        outcome="empty",
        quiz_id=quiz_id,
        attempt_id=attempt_id,
    )
    return []
