"""AI Core quiz generation orchestration.

Rules:
- Generate grounded quizzes from persisted lesson context and curriculum RAG evidence.
- Do not return placeholder/template quiz content.
- Fail explicitly when grounded context is unavailable or generated output is invalid.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from typing import Any

import requests

from ai_core.core_engine.integrations.internal_api import (
    internal_service_headers,
    internal_service_key_configured,
)
from ai_core.core_engine.llm.client import LLMClient, LLMClientError
from ai_core.core_engine.observability.logging import get_logger
from ai_core.core_engine.observability.telemetry import log_timed_event, now_ms

logger = get_logger(__name__)

_PLACEHOLDER_MARKERS = (
    "which option best demonstrates understanding of",
    "a common misconception students make",
    "an unrelated fact from another topic",
    "a partially correct but incomplete statement",
    "a clear example of",
)


class QuizGenerationError(RuntimeError):
    """Raised when quiz generation cannot produce grounded, valid questions."""


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
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _request_json(
    method: str,
    url: str,
    *,
    params: dict | None = None,
    payload: dict | None = None,
    timeout: float,
) -> dict:
    if not internal_service_key_configured():
        raise QuizGenerationError("INTERNAL_SERVICE_KEY is not configured for ai-core internal backend calls.")
    try:
        response = requests.request(
            method,
            url,
            params=params,
            json=payload,
            timeout=timeout,
            headers=internal_service_headers(),
        )
    except requests.RequestException as exc:
        raise QuizGenerationError(f"internal request failed for {url}: {exc}") from exc
    if not response.ok:
        detail = (response.text or "").strip()
        raise QuizGenerationError(
            f"internal request failed ({response.status_code}): {detail[:500] or 'no response body'}"
        )
    data = response.json()
    if not isinstance(data, dict):
        raise QuizGenerationError("internal request returned a non-object payload")
    return data


def _internal_postgres_base_url() -> str:
    return os.getenv("BACKEND_INTERNAL_POSTGRES_URL", "http://127.0.0.1:8000/api/v1/internal/postgres").strip().rstrip("/")


def _internal_rag_url() -> str:
    return os.getenv("BACKEND_INTERNAL_RAG_URL", "http://127.0.0.1:8000/api/v1/internal/rag/retrieve").strip()


def _internal_timeout() -> float:
    return float(os.getenv("INTERNAL_CONTEXT_TIMEOUT_SECONDS", "12"))


def _internal_lesson_context(*, student_id: uuid.UUID | None, topic_id: uuid.UUID) -> dict | None:
    if student_id is None:
        return None
    return _request_json(
        "GET",
        f"{_internal_postgres_base_url()}/lesson-context",
        params={"student_id": str(student_id), "topic_id": str(topic_id)},
        timeout=_internal_timeout(),
    )


def _load_postgres_repo(dsn: str):
    from ai_core.core_engine.integrations.postgres_repo import PostgresRepo

    return PostgresRepo(dsn=dsn)


def _topic_title_from_postgres(*, topic_id: uuid.UUID) -> str | None:
    dsn = (os.getenv("POSTGRES_DSN") or os.getenv("DATABASE_URL") or "").strip()
    if not dsn:
        return None
    try:
        repo = _load_postgres_repo(dsn)
        return repo.get_topic_title(topic_id=str(topic_id))
    except Exception as exc:
        logger.warning("quiz.topic_title lookup failed topic_id=%s error=%s", topic_id, exc)
        return None


def _internal_rag_context(
    *,
    subject: str,
    sss_level: str,
    term: int,
    topic_id: uuid.UUID,
    topic_title: str,
) -> list[dict]:
    query = _normalize_text(f"{topic_title} {subject} {sss_level} term {term} lesson practice questions")
    data = _request_json(
        "POST",
        _internal_rag_url(),
        payload={
            "query": query[:4000],
            "subject": subject,
            "sss_level": sss_level,
            "term": int(term),
            "topic_ids": [str(topic_id)],
            "top_k": max(4, min(int(os.getenv("QUIZ_RAG_TOP_K", "8")), 12)),
            "approved_only": True,
        },
        timeout=float(os.getenv("INTERNAL_RAG_TIMEOUT_SECONDS", "12")),
    )
    chunks = data.get("chunks")
    if not isinstance(chunks, list):
        raise QuizGenerationError("internal RAG returned invalid chunks payload")
    return [dict(chunk) for chunk in chunks if isinstance(chunk, dict)]


def _readable_concept_label(concept_id: str) -> str:
    value = str(concept_id or "").strip()
    if not value:
        return "unknown concept"
    try:
        uuid.UUID(value)
        return value
    except ValueError:
        pass
    token = value.rsplit(":", 1)[-1].strip().lower()
    token = re.sub(r"-(\d+)$", "", token)
    token = re.sub(r"[^a-z0-9]+", " ", token).strip()
    return token or value


def _topic_title(*, lesson_context: dict | None, rag_chunks: list[dict], topic_id: uuid.UUID) -> str:
    lesson_title = _normalize_text(str((lesson_context or {}).get("title") or ""))
    if lesson_title:
        return re.sub(r"^lesson:\s*", "", lesson_title, flags=re.IGNORECASE).strip() or lesson_title

    for chunk in rag_chunks:
        metadata = dict(chunk.get("metadata") or {})
        candidate = _normalize_text(
            str(metadata.get("citation_topic_title") or metadata.get("topic_title") or "")
        )
        if candidate:
            return candidate

    from_db = _topic_title_from_postgres(topic_id=topic_id)
    if from_db:
        return from_db
    return f"topic {topic_id}"


def _lesson_body_lines(lesson_context: dict | None, *, max_blocks: int = 6) -> list[str]:
    if not lesson_context:
        return []
    rendered: list[str] = []
    for block in list(lesson_context.get("content_blocks") or [])[:max_blocks]:
        if not isinstance(block, dict):
            continue
        block_type = _normalize_text(str(block.get("type") or "text")).lower()
        value = block.get("value")
        if isinstance(value, str):
            text = _normalize_text(value)
        elif isinstance(value, dict):
            pieces = [
                _normalize_text(str(value.get(key) or ""))
                for key in ("prompt", "note", "solution", "question", "expected_answer")
            ]
            text = " | ".join(piece for piece in pieces if piece)
        else:
            text = ""
        if text:
            rendered.append(f"- {block_type}: {text[:320]}")
    return rendered


def _lesson_context_has_substance(lesson_context: dict | None) -> bool:
    if not lesson_context:
        return False
    if _normalize_text(str(lesson_context.get("summary") or "")):
        return True
    return bool(_lesson_body_lines(lesson_context))


def _collect_concepts(*, lesson_context: dict | None, rag_chunks: list[dict]) -> list[dict[str, str]]:
    concepts: list[dict[str, str]] = []
    seen: set[str] = set()

    lesson_ids = [str(value) for value in list((lesson_context or {}).get("covered_concept_ids") or []) if str(value).strip()]
    lesson_labels = {
        str(key): _normalize_text(str(value))
        for key, value in dict((lesson_context or {}).get("covered_concept_labels") or {}).items()
        if str(key).strip()
    }
    for concept_id in lesson_ids:
        if concept_id in seen:
            continue
        seen.add(concept_id)
        concepts.append(
            {
                "concept_id": concept_id,
                "label": lesson_labels.get(concept_id) or _readable_concept_label(concept_id),
            }
        )

    for chunk in rag_chunks:
        metadata = dict(chunk.get("metadata") or {})
        concept_id = _normalize_text(str(metadata.get("concept_id") or ""))
        if not concept_id or concept_id in seen:
            continue
        seen.add(concept_id)
        label = _normalize_text(
            str(metadata.get("citation_concept_label") or metadata.get("concept_label") or "")
        ) or _readable_concept_label(concept_id)
        concepts.append({"concept_id": concept_id, "label": label})

    return concepts[:12]


def _context_lines(rag_chunks: list[dict], *, max_chunks: int = 8) -> list[str]:
    lines: list[str] = []
    for chunk in rag_chunks[:max_chunks]:
        text = _normalize_text(str(chunk.get("text") or ""))[:420]
        metadata = dict(chunk.get("metadata") or {})
        source_id = _normalize_text(str(chunk.get("source_id") or ""))
        chunk_id = _normalize_text(str(chunk.get("chunk_id") or ""))
        concept_label = _normalize_text(
            str(metadata.get("citation_concept_label") or metadata.get("concept_label") or "")
        )
        prefix = f"({source_id}#{chunk_id})"
        if concept_label:
            prefix += f" [{concept_label}]"
        if text:
            lines.append(f"- {prefix} {text}")
    return lines


def _build_quiz_prompt(
    *,
    subject: str,
    sss_level: str,
    term: int,
    topic_title: str,
    purpose: str,
    difficulty: str,
    num_questions: int,
    concept_pool: list[dict[str, str]],
    lesson_context: dict | None,
    rag_chunks: list[dict],
) -> str:
    lesson_summary = _normalize_text(str((lesson_context or {}).get("summary") or ""))
    lesson_body = "\n".join(_lesson_body_lines(lesson_context)) or "- No persisted lesson body."
    evidence_block = "\n".join(_context_lines(rag_chunks))
    if not evidence_block and not _lesson_context_has_substance(lesson_context):
        raise QuizGenerationError("Curriculum context is too sparse for grounded quiz generation.")
    if not evidence_block:
        evidence_block = "- No extra retrieval evidence. Use the structured lesson body as the primary source."

    concepts_json = json.dumps(concept_pool, ensure_ascii=True)
    return (
        "You generate curriculum-grounded multiple-choice quizzes for one Nigerian secondary school lesson.\n"
        "Return JSON only. No markdown, no commentary.\n"
        "Do not use placeholders or meta options such as 'common misconception', 'unrelated fact', "
        "'partially correct statement', or 'clear example of <concept>'.\n"
        "Every question must test actual lesson content from the provided context.\n"
        "Use only the provided concept_ids.\n\n"
        f"Scope: subject={subject}, level={sss_level}, term={term}, topic={topic_title}\n"
        f"Purpose: {purpose}\n"
        f"Difficulty: {difficulty}\n"
        f"Question count: {num_questions}\n"
        f"Lesson summary: {lesson_summary or 'N/A'}\n"
        f"Allowed concepts: {concepts_json}\n\n"
        f"Lesson body:\n{lesson_body}\n\n"
        f"Curriculum evidence:\n{evidence_block}\n\n"
        "Return EXACT JSON shape:\n"
        "{\n"
        '  "questions": [\n'
        "    {\n"
        '      "text": "string",\n'
        '      "options": ["string", "string", "string", "string"],\n'
        '      "correct_answer": "A",\n'
        '      "concept_id": "string",\n'
        '      "difficulty": "easy|medium|hard",\n'
        '      "explanation": "string"\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "Rules:\n"
        "- Generate exactly the requested number of questions.\n"
        "- Questions must be concrete, lesson-scoped, and answerable from the provided evidence.\n"
        "- Use exactly 4 options per question.\n"
        "- Use plausible distractors tied to the lesson, not generic distractors.\n"
        "- correct_answer must be one of A, B, C, D.\n"
        "- concept_id must come from the provided allowed concepts.\n"
        "- difficulty must match the requested difficulty.\n"
        "- explanation must briefly justify the correct answer using the lesson context.\n"
    )


def _llm_generate(prompt: str) -> str:
    client = LLMClient(
        provider=os.getenv("LLM_PROVIDER", "groq"),
        model=os.getenv("LLM_MODEL", "openai/gpt-oss-20b"),
        api_key=os.getenv("LLM_API_KEY"),
    )
    return client.generate(prompt)


def _validate_question(
    raw: Any,
    *,
    allowed_concept_ids: set[str],
    difficulty: str,
    idx: int,
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise QuizGenerationError(f"Question {idx + 1} is not an object.")

    text = _normalize_text(str(raw.get("text") or raw.get("question_text") or ""))
    if not text:
        raise QuizGenerationError(f"Question {idx + 1} is missing text.")
    lowered_text = text.lower()
    if any(marker in lowered_text for marker in _PLACEHOLDER_MARKERS):
        raise QuizGenerationError(f"Question {idx + 1} contains placeholder quiz text.")
    if re.search(r"\b(math|english|civic):sss[123]:t[123]:", lowered_text):
        raise QuizGenerationError(f"Question {idx + 1} leaked an internal concept id into visible text.")

    options = raw.get("options")
    if not isinstance(options, list) or len(options) != 4:
        raise QuizGenerationError(f"Question {idx + 1} must have exactly 4 options.")
    normalized_options = [_normalize_text(str(option)) for option in options]
    if any(not option for option in normalized_options):
        raise QuizGenerationError(f"Question {idx + 1} has an empty option.")
    if len(set(option.lower() for option in normalized_options)) != 4:
        raise QuizGenerationError(f"Question {idx + 1} has duplicate options.")
    for option in normalized_options:
        lowered = option.lower()
        if any(marker in lowered for marker in _PLACEHOLDER_MARKERS):
            raise QuizGenerationError(f"Question {idx + 1} contains placeholder option text.")
        if re.search(r"\b(math|english|civic):sss[123]:t[123]:", lowered):
            raise QuizGenerationError(f"Question {idx + 1} leaked an internal concept id into an option.")

    correct_answer = _normalize_text(str(raw.get("correct_answer") or "")).upper()
    if correct_answer not in {"A", "B", "C", "D"}:
        raise QuizGenerationError(f"Question {idx + 1} has invalid correct_answer.")

    concept_id = _normalize_text(str(raw.get("concept_id") or ""))
    if not concept_id or concept_id not in allowed_concept_ids:
        raise QuizGenerationError(f"Question {idx + 1} uses an invalid concept_id.")

    explanation = _normalize_text(str(raw.get("explanation") or ""))
    if not explanation:
        raise QuizGenerationError(f"Question {idx + 1} is missing explanation.")

    return {
        "id": uuid.uuid4(),
        "text": text,
        "options": normalized_options,
        "correct_answer": correct_answer,
        "concept_id": concept_id[:255],
        "difficulty": difficulty,
        "explanation": explanation,
    }


def _validate_generated_questions(
    parsed: dict,
    *,
    allowed_concept_ids: set[str],
    difficulty: str,
    num_questions: int,
) -> list[dict[str, Any]]:
    questions = parsed.get("questions")
    if not isinstance(questions, list) or len(questions) != num_questions:
        raise QuizGenerationError("Quiz generation returned an invalid question count.")

    normalized: list[dict[str, Any]] = []
    seen_texts: set[str] = set()
    for idx, item in enumerate(questions):
        question = _validate_question(
            item,
            allowed_concept_ids=allowed_concept_ids,
            difficulty=difficulty,
            idx=idx,
        )
        fingerprint = question["text"].lower()
        if fingerprint in seen_texts:
            raise QuizGenerationError(f"Question {idx + 1} duplicates another question.")
        seen_texts.add(fingerprint)
        normalized.append(question)
    return normalized


def _rebalance_answer_positions(
    questions: list[dict[str, Any]],
    *,
    topic_id: uuid.UUID,
) -> list[dict[str, Any]]:
    if not questions:
        return []

    letters = "ABCD"
    offset = topic_id.int % 4
    rebalanced: list[dict[str, Any]] = []

    for idx, question in enumerate(questions):
        current_index = letters.index(str(question["correct_answer"]).upper())
        desired_index = (offset + idx) % 4
        options = list(question["options"])
        correct_option = options.pop(current_index)
        options.insert(desired_index, correct_option)
        rebalanced.append(
            {
                **question,
                "options": options,
                "correct_answer": letters[desired_index],
            }
        )
    return rebalanced


async def generate_quiz_questions(
    student_id: uuid.UUID | None,
    subject: str,
    sss_level: str,
    term: int,
    topic_id: uuid.UUID,
    purpose: str,
    difficulty: str,
    num_questions: int,
) -> list[dict[str, Any]]:
    started_at = now_ms()
    try:
        lesson_context = _internal_lesson_context(student_id=student_id, topic_id=topic_id)
    except Exception as exc:
        logger.warning("quiz.lesson_context unavailable topic_id=%s error=%s", topic_id, exc)
        lesson_context = None

    try:
        rag_chunks = _internal_rag_context(
            subject=subject,
            sss_level=sss_level,
            term=term,
            topic_id=topic_id,
            topic_title=_topic_title(lesson_context=lesson_context, rag_chunks=[], topic_id=topic_id),
        )
    except Exception as exc:
        logger.warning("quiz.rag_context unavailable topic_id=%s error=%s", topic_id, exc)
        rag_chunks = []
    if not rag_chunks and not _lesson_context_has_substance(lesson_context):
        log_timed_event(
            logger,
            "quiz.generate",
            started_at,
            log_level=30,
            outcome="no_context",
            topic_id=topic_id,
            subject=subject,
            lesson_context=False,
            rag_chunks=0,
        )
        raise QuizGenerationError("No approved curriculum context found for grounded quiz generation.")

    topic_title = _topic_title(lesson_context=lesson_context, rag_chunks=rag_chunks, topic_id=topic_id)
    concept_pool = _collect_concepts(lesson_context=lesson_context, rag_chunks=rag_chunks)
    if not concept_pool:
        log_timed_event(
            logger,
            "quiz.generate",
            started_at,
            log_level=30,
            outcome="no_concepts",
            topic_id=topic_id,
            subject=subject,
            lesson_context=bool(lesson_context),
            rag_chunks=len(rag_chunks),
        )
        raise QuizGenerationError("No valid concept coverage found for this lesson/topic.")

    prompt = _build_quiz_prompt(
        subject=subject,
        sss_level=sss_level,
        term=term,
        topic_title=topic_title,
        purpose=purpose,
        difficulty=difficulty,
        num_questions=num_questions,
        concept_pool=concept_pool,
        lesson_context=lesson_context,
        rag_chunks=rag_chunks,
    )

    try:
        raw = _llm_generate(prompt)
    except (LLMClientError, Exception) as exc:
        log_timed_event(
            logger,
            "quiz.generate",
            started_at,
            log_level=30,
            outcome="llm_error",
            topic_id=topic_id,
            subject=subject,
            rag_chunks=len(rag_chunks),
            concepts=len(concept_pool),
            detail=str(exc),
        )
        raise QuizGenerationError(f"Quiz LLM generation failed: {exc}") from exc

    parsed = _extract_json_object(raw)
    if not parsed:
        preview = _normalize_text(raw)[:220]
        log_timed_event(
            logger,
            "quiz.generate",
            started_at,
            log_level=30,
            outcome="invalid_json",
            topic_id=topic_id,
            subject=subject,
            preview=preview,
        )
        raise QuizGenerationError(f"Quiz LLM returned invalid JSON. preview={preview!r}")

    questions = _validate_generated_questions(
        parsed,
        allowed_concept_ids={item["concept_id"] for item in concept_pool},
        difficulty=difficulty,
        num_questions=num_questions,
    )
    questions = _rebalance_answer_positions(questions, topic_id=topic_id)
    log_timed_event(
        logger,
        "quiz.generate",
        started_at,
        outcome="success",
        topic_id=topic_id,
        subject=subject,
        sss_level=sss_level,
        term=term,
        questions=len(questions),
        concepts=len(concept_pool),
        rag_chunks=len(rag_chunks),
        lesson_context=bool(lesson_context),
        lesson_context_source=str((lesson_context or {}).get("context_source") or "none"),
    )
    return questions


async def generate_quiz_insights(quiz_id: uuid.UUID, attempt_id: uuid.UUID) -> list[str]:
    return [
        "Review the concepts you missed and retry one focused question at a time.",
        "Compare each wrong option with the correct explanation before your next attempt.",
        "Return to the lesson section connected to your weakest concept before reattempting the quiz.",
    ]
