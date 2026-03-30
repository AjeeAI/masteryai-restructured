"""Tutor orchestration utilities.

Includes:
- legacy single-call orchestration (`handle_question`)
- section-5 aligned helpers for HTTP tutor endpoints (`run_tutor_chat`, `run_tutor_hint`, `run_tutor_explain_mistake`)
"""

from __future__ import annotations

import json
import os
import re
from typing import TYPE_CHECKING
from uuid import UUID

import requests

from ai_core.core_engine.api_contracts.schemas import (
    Citation,
    TutorAssessmentStartRequest,
    TutorAssessmentStartResponse,
    TutorAssessmentSubmitRequest,
    TutorAssessmentSubmitResponse,
    TutorChatRequest,
    TutorChatResponse,
    TutorDrillRequest,
    TutorExplainMistakeRequest,
    TutorExplainMistakeResponse,
    TutorHintRequest,
    TutorHintResponse,
    TutorPrereqBridgeRequest,
    TutorRecapRequest,
    TutorRecommendation,
    TutorRequest,
    TutorResponse,
    TutorStudyPlanRequest,
)
from ai_core.core_engine.integrations.internal_api import (
    internal_service_headers,
    internal_service_key_configured,
)
from ai_core.core_engine.llm.client import LLMClient, LLMClientError
from ai_core.core_engine.observability.logging import get_logger
from ai_core.core_engine.observability.telemetry import log_timed_event, now_ms
from ai_core.core_engine.safety.injection import sanitize_user_text
from ai_core.core_engine.safety.moderation import ModerationError, basic_moderate

if TYPE_CHECKING:
    from ai_core.core_engine.config.settings import Settings
    from ai_core.core_engine.curriculum.resolver import CurriculumResolver
    from ai_core.core_engine.knowledge_graph.prerequisites import PrereqService
    from ai_core.core_engine.llm.client import LLMClient
    from ai_core.core_engine.mastery.updater import MasteryUpdater
    from ai_core.core_engine.observability.cost import CostTracker
    from ai_core.core_engine.rag.retriever import RagRetriever

logger = get_logger(__name__)


def _sanitize_and_moderate(text: str, *, max_chars: int = 6000) -> str:
    cleaned = sanitize_user_text((text or "")[:max_chars])
    basic_moderate(cleaned)
    return cleaned


def _normalize_rag_query(raw: str) -> str | None:
    normalized = " ".join((raw or "").split())
    if len(normalized) < 3:
        return None
    return normalized[:4000]


def _normalize_topic_ids(topic_id: str | None) -> list[str]:
    if not topic_id:
        return []
    try:
        UUID(str(topic_id))
    except (TypeError, ValueError):
        logger.warning("tutor._internal_rag_retrieve skipping invalid topic_id: %s", topic_id)
        return []
    return [str(topic_id)]


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


def _request_json(
    method: str,
    url: str,
    *,
    params: dict | None = None,
    payload: dict | None = None,
    timeout: float,
) -> dict:
    if not internal_service_key_configured():
        raise RuntimeError("INTERNAL_SERVICE_KEY is not configured for ai-core internal backend calls.")
    response = requests.request(
        method,
        url,
        params=params,
        json=payload,
        timeout=timeout,
        headers=internal_service_headers(),
    )
    if not response.ok:
        detail = (response.text or "").strip()
        raise RuntimeError(
            f"internal request failed ({response.status_code}): {detail[:500] or 'no response body'}"
        )
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError("internal request returned a non-object payload")
    return data


def _internal_postgres_base_url() -> str:
    return os.getenv("BACKEND_INTERNAL_POSTGRES_URL", "http://127.0.0.1:8000/api/v1/internal/postgres").strip().rstrip("/")


def _internal_graph_context_url() -> str:
    return os.getenv(
        "BACKEND_INTERNAL_GRAPH_CONTEXT_URL",
        "http://127.0.0.1:8000/api/v1/internal/graph/context",
    ).strip()


def _internal_context_timeout() -> float:
    return float(os.getenv("INTERNAL_CONTEXT_TIMEOUT_SECONDS", "12"))


def _internal_profile_context(request: TutorChatRequest) -> dict:
    return _request_json(
        "GET",
        f"{_internal_postgres_base_url()}/profile",
        params={"student_id": request.student_id},
        timeout=_internal_context_timeout(),
    )


def _internal_history_context(request: TutorChatRequest) -> dict:
    return _request_json(
        "GET",
        f"{_internal_postgres_base_url()}/history",
        params={"student_id": request.student_id, "session_id": request.session_id},
        timeout=_internal_context_timeout(),
    )


def _internal_lesson_context(request: TutorChatRequest) -> dict | None:
    if not request.topic_id:
        return None
    return _request_json(
        "GET",
        f"{_internal_postgres_base_url()}/lesson-context",
        params={"student_id": request.student_id, "topic_id": request.topic_id},
        timeout=_internal_context_timeout(),
    )


def _internal_graph_context(request: TutorChatRequest) -> dict:
    params = {
        "student_id": request.student_id,
        "subject": request.subject,
        "sss_level": request.sss_level,
        "term": int(request.term),
    }
    if request.topic_id:
        params["topic_id"] = request.topic_id
    return _request_json(
        "GET",
        _internal_graph_context_url(),
        params=params,
        timeout=_internal_context_timeout(),
    )


def _internal_rag_retrieve(request: TutorChatRequest) -> list[Citation]:
    base_url = os.getenv("BACKEND_INTERNAL_RAG_URL", "http://127.0.0.1:8000/api/v1/internal/rag/retrieve").strip()
    timeout = float(os.getenv("INTERNAL_RAG_TIMEOUT_SECONDS", "12"))
    top_k = int(os.getenv("INTERNAL_RAG_TOP_K", "6"))
    query = _normalize_rag_query(request.message)
    if query is None:
        return []

    payload = {
        "query": query,
        "subject": request.subject,
        "sss_level": request.sss_level,
        "term": int(request.term),
        "topic_ids": _normalize_topic_ids(request.topic_id),
        "top_k": max(1, min(top_k, 20)),
        "approved_only": True,
    }
    allow_scope_fallback = os.getenv("TUTOR_CHAT_ALLOW_SCOPE_FALLBACK", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    def _request_chunks(request_payload: dict) -> list[dict]:
        if not internal_service_key_configured():
            raise RuntimeError("INTERNAL_SERVICE_KEY is not configured for ai-core internal backend calls.")
        response = requests.post(
            base_url,
            json=request_payload,
            timeout=timeout,
            headers=internal_service_headers(),
        )
        if not response.ok:
            detail = (response.text or "").strip()
            raise RuntimeError(
                f"internal RAG request failed ({response.status_code}): {detail[:500] or 'no response body'}"
            )
        data = response.json()
        return list(data.get("chunks", []))

    chunks = _request_chunks(payload)
    if allow_scope_fallback and not chunks and payload["topic_ids"]:
        fallback_payload = dict(payload)
        fallback_payload["topic_ids"] = []
        logger.info(
            "tutor._internal_rag_retrieve empty topic-scoped result; retrying scope-only retrieval",
            extra={
                "subject": request.subject,
                "sss_level": request.sss_level,
                "term": int(request.term),
                "topic_id": request.topic_id,
            },
        )
        chunks = _request_chunks(fallback_payload)

    citations: list[Citation] = []
    for chunk in chunks:
        text = str(chunk.get("text") or "")
        snippet = " ".join(text.split())[:220]
        citations.append(
            Citation(
                source_id=str(chunk.get("source_id") or ""),
                chunk_id=str(chunk.get("chunk_id") or ""),
                snippet=snippet,
                metadata=dict(chunk.get("metadata") or {}),
            )
        )
    return citations


def _internal_rag_retrieve_for_prompt(
    *,
    student_id: str,
    session_id: str,
    subject: str,
    sss_level: str,
    term: int,
    topic_id: str | None,
    message: str,
) -> list[Citation]:
    request = TutorChatRequest(
        student_id=student_id,
        session_id=session_id,
        subject=subject,
        sss_level=sss_level,
        term=term,
        topic_id=topic_id,
        message=message,
    )
    return _internal_rag_retrieve(request)


def _llm_generate(prompt: str) -> str:
    client = LLMClient(
        provider=os.getenv("LLM_PROVIDER", "groq"),
        model=os.getenv("LLM_MODEL", "openai/gpt-oss-20b"),
        api_key=os.getenv("LLM_API_KEY"),
    )
    return client.generate(prompt)


def _readable_concept_label(concept_id: str) -> str:
    value = str(concept_id or "").strip()
    if not value:
        return "unknown concept"
    try:
        UUID(value)
        return value
    except ValueError:
        pass
    token = value.rsplit(":", 1)[-1].strip().lower()
    token = re.sub(r"-(\d+)$", "", token)
    token = re.sub(r"[^a-z0-9]+", " ", token).strip()
    return token or value


def _clamp_score(value: object) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, score))


def _lesson_context_available(lesson_context: dict | None) -> bool:
    if not lesson_context:
        return False
    if str(lesson_context.get("summary") or "").strip():
        return True
    blocks = lesson_context.get("content_blocks")
    return isinstance(blocks, list) and bool(blocks)


def _lesson_context_source(lesson_context: dict | None) -> str | None:
    if not lesson_context:
        return None
    source = str(lesson_context.get("context_source") or "").strip().lower()
    return source or None


def _lesson_covered_concept_ids(lesson_context: dict | None) -> list[str]:
    if not lesson_context:
        return []
    return [str(value) for value in list(lesson_context.get("covered_concept_ids") or []) if str(value).strip()]


def _lesson_covered_concept_lines(lesson_context: dict | None, *, max_items: int = 6) -> list[str]:
    concept_ids = _lesson_covered_concept_ids(lesson_context)
    concept_labels = {
        str(key): str(value)
        for key, value in dict((lesson_context or {}).get("covered_concept_labels") or {}).items()
        if str(key).strip()
    }
    rendered: list[str] = []
    for concept_id in concept_ids[:max_items]:
        rendered.append(f"- {concept_labels.get(concept_id) or _readable_concept_label(concept_id)}")
    return rendered


def _lesson_concept_label_map(lesson_context: dict | None) -> dict[str, str]:
    if not lesson_context:
        return {}
    return {
        str(key): str(value)
        for key, value in dict(lesson_context.get("covered_concept_labels") or {}).items()
        if str(key).strip()
    }


def _lesson_context_block_lines(lesson_context: dict | None, *, max_blocks: int = 5) -> list[str]:
    if not lesson_context:
        return []

    rendered: list[str] = []
    for block in list(lesson_context.get("content_blocks") or [])[:max_blocks]:
        if not isinstance(block, dict):
            continue
        block_type = str(block.get("type") or "text").strip().lower()
        value = block.get("value")
        if isinstance(value, str):
            text = " ".join(value.split()).strip()
        elif isinstance(value, dict):
            parts = [
                " ".join(str(value.get(key) or "").split()).strip()
                for key in ("prompt", "note", "solution", "question", "expected_answer")
            ]
            text = " | ".join(part for part in parts if part)
        else:
            text = ""
        if text:
            rendered.append(f"- {block_type}: {text[:320]}")
    return rendered


def _history_context_lines(history_context: dict | None, *, max_messages: int = 6) -> list[str]:
    if not history_context:
        return []
    rows = list(history_context.get("messages") or [])[-max_messages:]
    rendered: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        role = str(row.get("role") or "message").strip().lower()
        content = " ".join(str(row.get("content") or "").split()).strip()
        if content:
            rendered.append(f"- {role}: {content[:220]}")
    return rendered


def _graph_context_lines(graph_context: dict | None, lesson_context: dict | None) -> list[str]:
    if not graph_context:
        return []

    covered_concept_ids = set(_lesson_covered_concept_ids(lesson_context))
    mastery_rows = list(graph_context.get("mastery") or [])
    covered_mastery_rows = [
        row
        for row in mastery_rows
        if isinstance(row, dict) and str(row.get("concept_id") or "") in covered_concept_ids
    ]
    mastery_focus_rows = covered_mastery_rows or mastery_rows
    weak_rows = sorted(
        [
            row for row in mastery_focus_rows
            if isinstance(row, dict) and isinstance(row.get("score"), (int, float))
        ],
        key=lambda row: float(row.get("score", 0.0)),
    )[:5]
    weak_summary = ", ".join(
        f"{_readable_concept_label(str(row.get('concept_id') or ''))} ({float(row.get('score', 0.0)):.2f})"
        for row in weak_rows
    )

    prereq_rows = [
        row for row in list(graph_context.get("prereqs") or [])
        if isinstance(row, dict)
        and (
            not covered_concept_ids
            or str(row.get("concept_id") or "") in covered_concept_ids
            or str(row.get("prerequisite_concept_id") or "") in covered_concept_ids
        )
    ][:5]
    prereq_summary = ", ".join(
        (
            f"{_readable_concept_label(str(row.get('prerequisite_concept_id') or ''))}"
            f" -> {_readable_concept_label(str(row.get('concept_id') or ''))}"
        )
        for row in prereq_rows
        if isinstance(row, dict)
    )

    lines = [
        f"- overall_mastery: {float(graph_context.get('overall_mastery') or 0.0):.2f}",
        f"- unlocked_nodes: {len(list(graph_context.get('unlocked_nodes') or []))}",
    ]
    if covered_concept_ids:
        lines.append(f"- lesson_covered_concepts: {len(covered_concept_ids)}")
    if weak_summary:
        lines.append(
            f"- weak_concepts_in_lesson: {weak_summary}" if covered_concept_ids else f"- weak_concepts: {weak_summary}"
        )
    if prereq_summary:
        lines.append(f"- prerequisite_edges: {prereq_summary}")
    return lines


def _profile_context_lines(profile_context: dict | None) -> list[str]:
    if not profile_context:
        return []
    preferences = profile_context.get("preferences") or {}
    lines = [
        f"- enrolled_subjects: {', '.join(str(item) for item in list(profile_context.get('subjects') or []))}",
        f"- preferred_explanation_depth: {preferences.get('explanation_depth', 'unknown')}",
        f"- examples_first: {bool(preferences.get('examples_first', False))}",
        f"- pace: {preferences.get('pace', 'unknown')}",
    ]
    return lines


def _citation_concept_lines(citations: list[Citation], *, max_items: int = 6) -> list[str]:
    rendered: list[str] = []
    seen: set[str] = set()
    for citation in citations:
        concept_id = str(citation.metadata.get("concept_id") or "").strip()
        if not concept_id or concept_id in seen:
            continue
        seen.add(concept_id)
        label = str(
            citation.metadata.get("citation_concept_label")
            or citation.metadata.get("concept_label")
            or _readable_concept_label(concept_id)
        ).strip()
        rendered.append(f"- {label}")
        if len(rendered) >= max_items:
            break
    return rendered


def _assessment_target_concept(
    *,
    lesson_context: dict | None,
    graph_context: dict | None,
    citations: list[Citation],
    requested_focus_concept_id: str | None = None,
    requested_focus_concept_label: str | None = None,
) -> tuple[str, str] | None:
    concept_labels = _lesson_concept_label_map(lesson_context)
    covered_ids = _lesson_covered_concept_ids(lesson_context)
    graph_nodes = []
    for key in ("current_concepts", "prerequisite_concepts", "downstream_concepts"):
        graph_nodes.extend(list((graph_context or {}).get(key) or []))
    graph_label_map = {
        str(row.get("concept_id") or "").strip(): str(row.get("label") or "").strip()
        for row in graph_nodes
        if isinstance(row, dict) and str(row.get("concept_id") or "").strip()
    }
    mastery_map = {
        str(row.get("concept_id") or ""): _clamp_score(row.get("score"))
        for row in list((graph_context or {}).get("mastery") or [])
        if isinstance(row, dict) and str(row.get("concept_id") or "").strip()
    }
    requested_focus_id = str(requested_focus_concept_id or "").strip()
    requested_focus_label = " ".join(str(requested_focus_concept_label or "").split()).strip()

    if requested_focus_id:
        if (
            requested_focus_id in concept_labels
            or requested_focus_id in graph_label_map
            or any(str(citation.metadata.get("concept_id") or "").strip() == requested_focus_id for citation in citations)
        ):
            return (
                requested_focus_id,
                concept_labels.get(requested_focus_id)
                or graph_label_map.get(requested_focus_id)
                or requested_focus_label
                or _readable_concept_label(requested_focus_id),
            )

    if requested_focus_label:
        normalized_requested = requested_focus_label.casefold()
        for concept_id, label in {**graph_label_map, **concept_labels}.items():
            if str(label).strip().casefold() == normalized_requested:
                return concept_id, str(label).strip()
        for citation in citations:
            citation_label = str(
                citation.metadata.get("citation_concept_label")
                or citation.metadata.get("concept_label")
                or ""
            ).strip()
            citation_concept_id = str(citation.metadata.get("concept_id") or "").strip()
            if citation_concept_id and citation_label.casefold() == normalized_requested:
                return citation_concept_id, citation_label

    ranked_covered = [
        (concept_id, mastery_map.get(concept_id, 0.0))
        for concept_id in covered_ids
    ]
    if ranked_covered:
        ranked_covered.sort(key=lambda item: item[1])
        concept_id = ranked_covered[0][0]
        return concept_id, concept_labels.get(concept_id) or _readable_concept_label(concept_id)

    for citation in citations:
        concept_id = str(citation.metadata.get("concept_id") or "").strip()
        if concept_id:
            label = str(
                citation.metadata.get("citation_concept_label")
                or citation.metadata.get("concept_label")
                or _readable_concept_label(concept_id)
            ).strip()
            return concept_id, label
    return None


def _citations_block(citations: list[Citation]) -> str:
    if citations:
        return "\n".join(f"- ({item.source_id}#{item.chunk_id}) {item.snippet}" for item in citations)
    return "- No verified curriculum context retrieved."


def _assessment_start_prompt(
    request: TutorAssessmentStartRequest,
    *,
    concept_id: str,
    concept_label: str,
    lesson_context: dict | None,
    graph_context: dict | None,
    citations: list[Citation],
) -> str:
    lesson_title = str((lesson_context or {}).get("title") or "").strip() or "No persisted lesson title"
    lesson_summary = str((lesson_context or {}).get("summary") or "").strip() or "No persisted lesson summary."
    lesson_block = "\n".join(_lesson_context_block_lines(lesson_context)) or "- No persisted lesson body available."
    graph_block = "\n".join(_graph_context_lines(graph_context, lesson_context)) or "- No graph/mastery context available."
    citations_block = _citations_block(citations)
    return (
        "You generate one short-answer formative assessment question for a Nigerian SSS lesson.\n"
        "Return JSON only.\n"
        "Do not generate multiple-choice questions.\n"
        "Do not use generic wording.\n"
        "Ask exactly one question focused on the target concept.\n\n"
        f"Scope: subject={request.subject}, level={request.sss_level}, term={request.term}, difficulty={request.difficulty}\n"
        f"Current lesson title: {lesson_title}\n"
        f"Current lesson summary: {lesson_summary}\n"
        f"Target concept id: {concept_id}\n"
        f"Target concept label: {concept_label}\n\n"
        f"Lesson body:\n{lesson_block}\n\n"
        f"Mastery / graph context:\n{graph_block}\n\n"
        f"Retrieved context:\n{citations_block}\n\n"
        "Return EXACT JSON shape:\n"
        "{\n"
        '  "question": "string",\n'
        '  "ideal_answer": "string",\n'
        '  "hint": "string"\n'
        "}\n"
        "Rules:\n"
        "- The question must be answerable from the lesson context.\n"
        "- The ideal_answer must be concise, correct, and lesson-grounded.\n"
        "- The hint must guide without giving the full answer away.\n"
        "- Do not mention internal IDs in visible text.\n"
    )


def _assessment_submit_prompt(
    request: TutorAssessmentSubmitRequest,
    *,
    lesson_context: dict | None,
    graph_context: dict | None,
    citations: list[Citation],
) -> str:
    lesson_title = str((lesson_context or {}).get("title") or "").strip() or "No persisted lesson title"
    lesson_summary = str((lesson_context or {}).get("summary") or "").strip() or "No persisted lesson summary."
    lesson_block = "\n".join(_lesson_context_block_lines(lesson_context)) or "- No persisted lesson body available."
    graph_block = "\n".join(_graph_context_lines(graph_context, lesson_context)) or "- No graph/mastery context available."
    citations_block = _citations_block(citations)
    return (
        "You evaluate a student's short-answer response for a Nigerian SSS lesson.\n"
        "Return JSON only.\n"
        "Be strict, lesson-grounded, and concise.\n\n"
        f"Scope: subject={request.subject}, level={request.sss_level}, term={request.term}\n"
        f"Current lesson title: {lesson_title}\n"
        f"Current lesson summary: {lesson_summary}\n"
        f"Target concept id: {request.concept_id}\n"
        f"Target concept label: {request.concept_label}\n"
        f"Assessment question: {request.question}\n"
        f"Ideal answer: {request.ideal_answer}\n"
        f"Student answer: {request.answer}\n\n"
        f"Lesson body:\n{lesson_block}\n\n"
        f"Mastery / graph context:\n{graph_block}\n\n"
        f"Retrieved context:\n{citations_block}\n\n"
        "Return EXACT JSON shape:\n"
        "{\n"
        '  "score": 0.0,\n'
        '  "feedback": "string",\n'
        '  "ideal_answer": "string"\n'
        "}\n"
        "Rules:\n"
        "- score must be between 0 and 1.\n"
        "- feedback must explain what was correct, missing, or wrong.\n"
        "- ideal_answer may refine the provided ideal answer, but must stay lesson-grounded.\n"
    )


def _validate_assessment_start_payload(
    parsed: dict | None,
    *,
    concept_id: str,
    concept_label: str,
    citations: list[Citation],
) -> TutorAssessmentStartResponse:
    if not parsed:
        raise RuntimeError("assessment generation returned invalid JSON")
    question = " ".join(str(parsed.get("question") or "").split()).strip()
    ideal_answer = " ".join(str(parsed.get("ideal_answer") or "").split()).strip()
    hint = " ".join(str(parsed.get("hint") or "").split()).strip()
    if not question or not ideal_answer:
        raise RuntimeError("assessment generation returned incomplete content")
    lowered_question = question.lower()
    if "which option" in lowered_question or "a common misconception" in lowered_question:
        raise RuntimeError("assessment generation returned placeholder question content")
    if re.search(r"\b(math|english|civic):sss[123]:t[123]:", lowered_question):
        raise RuntimeError("assessment generation leaked internal concept ids")
    return TutorAssessmentStartResponse(
        question=question,
        concept_id=concept_id,
        concept_label=concept_label,
        ideal_answer=ideal_answer,
        hint=hint or None,
        citations=citations,
        actions=["USED_RAG_CONTEXT" if citations else "ASSESSMENT_WITHOUT_RAG"],
    )


def _validate_assessment_submit_payload(
    parsed: dict | None,
    *,
    request: TutorAssessmentSubmitRequest,
    citations: list[Citation],
) -> TutorAssessmentSubmitResponse:
    if not parsed:
        raise RuntimeError("assessment evaluation returned invalid JSON")
    score = _clamp_score(parsed.get("score"))
    feedback = " ".join(str(parsed.get("feedback") or "").split()).strip()
    ideal_answer = " ".join(str(parsed.get("ideal_answer") or request.ideal_answer).split()).strip()
    if not feedback:
        raise RuntimeError("assessment evaluation returned empty feedback")
    return TutorAssessmentSubmitResponse(
        assessment_id=request.assessment_id,
        is_correct=score >= 0.8,
        score=score,
        feedback=feedback,
        ideal_answer=ideal_answer or request.ideal_answer,
        concept_id=request.concept_id,
        concept_label=request.concept_label,
        citations=citations,
        actions=["ASSESSMENT_EVALUATED", "USED_RAG_CONTEXT" if citations else "ASSESSMENT_WITHOUT_RAG"],
    )


def _is_question_request(message: str) -> bool:
    normalized = " ".join((message or "").lower().split())
    markers = (
        "ask me a question",
        "ask me question",
        "quiz me",
        "test me",
        "give me a question",
        "give me one question",
        "check my understanding",
    )
    return any(marker in normalized for marker in markers)


def _chat_prompt(
    request: TutorChatRequest,
    *,
    citations: list[Citation],
    profile_context: dict | None,
    history_context: dict | None,
    lesson_context: dict | None,
    graph_context: dict | None,
) -> str:
    if citations:
        citations_block = "\n".join(
            f"- ({item.source_id}#{item.chunk_id}) {item.snippet}" for item in citations
        )
    else:
        citations_block = "- No verified curriculum context retrieved."

    lesson_lines = _lesson_context_block_lines(lesson_context)
    lesson_block = "\n".join(lesson_lines) if lesson_lines else "- No persisted lesson body available."
    history_block = "\n".join(_history_context_lines(history_context)) or "- No prior tutor history."
    graph_block = "\n".join(_graph_context_lines(graph_context, lesson_context)) or "- No graph/mastery context available."
    profile_block = "\n".join(_profile_context_lines(profile_context)) or "- No profile preferences available."
    covered_concepts_block = "\n".join(_lesson_covered_concept_lines(lesson_context)) or "- No explicit lesson concept coverage metadata."
    lesson_title = str((lesson_context or {}).get("title") or "").strip() or "No persisted lesson title"
    lesson_summary = str((lesson_context or {}).get("summary") or "").strip() or "No persisted lesson summary."
    question_mode = _is_question_request(request.message)

    return (
        "You are Mastery AI, a lesson-aware curriculum-bound tutor for Nigerian SSS learners.\n"
        f"Scope: subject={request.subject}, level={request.sss_level}, term={request.term}.\n"
        "Hard constraints:\n"
        "- Do not answer outside this exact scope (subject, level, and term).\n"
        "- Treat the persisted current lesson as the primary context when it is available.\n"
        "- Use retrieved curriculum chunks as supporting evidence and cite source/chunk IDs when possible.\n"
        "- Personalize scaffolding using the mastery/graph context and profile preferences when available.\n"
        "- Do not fabricate facts, sources, or curriculum claims.\n"
        "- If context is insufficient, say what is missing and ask one focused follow-up question.\n"
        "- Keep explanation concise, stepwise, and student-friendly.\n"
        "- Stay inside the currently selected lesson topic unless the student explicitly asks to broaden the scope.\n"
        "- Never pretend a student has mastered something unless there is explicit evidence.\n"
        "- For unsafe requests, refuse and redirect to safe learning support.\n\n"
        f"Current lesson title: {lesson_title}\n"
        f"Current lesson summary: {lesson_summary}\n"
        f"Lesson covered concepts:\n{covered_concepts_block}\n\n"
        f"Current lesson body:\n{lesson_block}\n\n"
        f"Student profile and preferences:\n{profile_block}\n\n"
        f"Recent tutor history:\n{history_block}\n\n"
        f"Mastery / graph context:\n{graph_block}\n\n"
        f"Question-request mode: {'yes' if question_mode else 'no'}\n"
        "If question-request mode is yes, ask exactly one lesson-scoped check question first. "
        "Prefer the weakest concept inside the current lesson when identifiable. "
        "Do not give the answer in the same turn.\n\n"
        f"Student question: {request.message}\n\n"
        f"Retrieved context:\n{citations_block}\n"
    )


def _infer_tutor_mode_from_message(message: str) -> str:
    text = (message or "").strip().lower()
    if (
        re.search(r"\bwaec\b", text)
        or re.search(r"\bexam(?:s|ination)?\b", text)
        or "past question" in text
    ):
        return "exam-practice"
    if any(phrase in text for phrase in ("recap", "summary", "summarize", "revise")):
        return "recap"
    if any(phrase in text for phrase in ("drill", "practice", "harder one")):
        return "drill"
    if any(phrase in text for phrase in ("why am i learning", "prerequisite", "previous topic", "bridge")):
        return "diagnose"
    if any(phrase in text for phrase in ("ask me a question", "quiz me", "test me")):
        return "socratic"
    return "teach"


def _weak_concept_labels(graph_context: dict | None, lesson_context: dict | None, *, limit: int = 3) -> list[str]:
    covered_ids = set(_lesson_covered_concept_ids(lesson_context))
    rows = [
        row
        for row in list((graph_context or {}).get("mastery") or [])
        if isinstance(row, dict)
        and (not covered_ids or str(row.get("concept_id") or "") in covered_ids)
    ]
    ranked = sorted(rows, key=lambda row: _clamp_score(row.get("score")))[:limit]
    labels = _lesson_concept_label_map(lesson_context)
    return [
        labels.get(str(row.get("concept_id") or "")) or _readable_concept_label(str(row.get("concept_id") or ""))
        for row in ranked
        if str(row.get("concept_id") or "").strip()
    ]


def _recommendations_from_graph(
    *,
    request: TutorChatRequest,
    graph_context: dict | None,
) -> list[TutorRecommendation]:
    recommendations: list[TutorRecommendation] = []
    next_unlock = dict((graph_context or {}).get("next_unlock") or {})
    next_topic_id = str(next_unlock.get("topic_id") or request.topic_id or "").strip() or None
    next_topic_title = str(next_unlock.get("topic_title") or "").strip() or None
    reason = str(next_unlock.get("reason") or "").strip() or (
        "Stay on the current lesson and close the weakest gaps before moving to a new topic."
    )
    recommendations.append(
        TutorRecommendation(
            type="next_topic",
            topic_id=next_topic_id,
            topic_title=next_topic_title,
            reason=reason,
        )
    )
    return recommendations


def _message_anchor_label(
    request: TutorChatRequest,
    lesson_context: dict | None,
    graph_context: dict | None,
) -> str | None:
    focus_label = " ".join(str(request.focus_concept_label or "").split()).strip()
    if focus_label:
        return focus_label
    weak_labels = _weak_concept_labels(graph_context, lesson_context, limit=1)
    if weak_labels:
        return weak_labels[0]
    covered_labels = _lesson_covered_concept_lines(lesson_context, max_items=1)
    if covered_labels:
        return covered_labels[0].removeprefix("- ").strip()
    lesson_title = str((lesson_context or {}).get("title") or "").strip()
    if lesson_title and lesson_title != "No persisted lesson title":
        return lesson_title
    return None


def _lesson_block_texts(lesson_context: dict | None, *, max_blocks: int = 5) -> list[str]:
    if not lesson_context:
        return []

    rendered: list[str] = []
    for block in list(lesson_context.get("content_blocks") or [])[:max_blocks]:
        if not isinstance(block, dict):
            continue
        value = block.get("value")
        if isinstance(value, str):
            text = " ".join(value.split()).strip()
        elif isinstance(value, dict):
            parts = [
                " ".join(str(value.get(key) or "").split()).strip()
                for key in ("prompt", "note", "solution", "question", "expected_answer")
            ]
            text = " ".join(part for part in parts if part).strip()
        else:
            text = ""
        if text:
            rendered.append(text)
    return rendered


def _lesson_recap_key_points(lesson_context: dict | None, *, limit: int = 3) -> list[str]:
    candidates: list[str] = []
    summary = str((lesson_context or {}).get("summary") or "").strip()
    if summary:
        candidates.extend(re.split(r"[;\n]+", summary))

    for block_text in _lesson_block_texts(lesson_context):
        candidates.extend(re.split(r"(?<=[.!?])\s+", block_text))

    cleaned: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        text = " ".join(str(item or "").split()).strip(" -•\t\r\n")
        text = re.sub(r"^[0-9]+[.)]\s*", "", text)
        if not text:
            continue
        if text.isupper() and len(text.split()) <= 8:
            continue
        if len(text) < 12:
            continue
        if len(text) > 180:
            text = text[:177].rstrip(" ,;:") + "..."
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned


def _recap_memory_hook(anchor_label: str | None) -> str:
    if anchor_label:
        return f"Memory hook: think {anchor_label} as core idea -> key feature -> one real example."
    return "Memory hook: keep the core idea, key feature, and one real example together."


def _lesson_visible_title(lesson_context: dict | None) -> str | None:
    lesson_title = " ".join(str((lesson_context or {}).get("title") or "").split()).strip()
    if not lesson_title:
        return None
    if lesson_title.lower().startswith("lesson:"):
        lesson_title = lesson_title.split(":", 1)[1].strip()
    return lesson_title or None


def _fast_recap_response(
    *,
    request: TutorChatRequest,
    lesson_context: dict | None,
    graph_context: dict | None,
    actions: list[str],
) -> TutorChatResponse:
    anchor_label = _lesson_visible_title(lesson_context) or _message_anchor_label(request, lesson_context, graph_context) or "This lesson"
    key_points = _lesson_recap_key_points(lesson_context, limit=3)
    weak_labels = _weak_concept_labels(graph_context, lesson_context, limit=2)
    concept_focus = list(dict.fromkeys([anchor_label] + weak_labels))[:4]
    prerequisite_warning = None
    if weak_labels:
        prerequisite_warning = f"Watch {weak_labels[0]} closely because it still needs reinforcement."

    recap_parts = [f"{anchor_label} is the main focus of this lesson."]
    if key_points:
        recap_parts.append("Quick recap: " + "; ".join(point.rstrip(".") for point in key_points) + ".")
    recap_parts.append(_recap_memory_hook(anchor_label))
    assistant_message = " ".join(part for part in recap_parts if part).strip()

    return TutorChatResponse(
        assistant_message=assistant_message,
        citations=[],
        actions=actions + ["MODE:RECAP", "FAST_RECAP_PATH", "SKIPPED_HISTORY_RECAP", "SKIPPED_RAG_RECAP", "SKIPPED_LLM_RECAP"],
        recommendations=_recommendations_from_graph(request=request, graph_context=graph_context),
        mode="recap",
        key_points=key_points,
        concept_focus=concept_focus,
        prerequisite_warning=prerequisite_warning,
        next_action="Run the 1-minute checkpoint or take the lesson quiz next.",
        recommended_assessment="Ask one checkpoint question on this lesson.",
        recommended_topic_title=(
            str(dict((graph_context or {}).get("next_unlock") or {}).get("topic_title") or "").strip() or None
        ),
    )


def _tighten_tutor_message(
    message: str,
    *,
    request: TutorChatRequest,
    lesson_context: dict | None,
    graph_context: dict | None,
) -> str:
    anchored = " ".join(str(message or "").split()).strip()
    if not anchored:
        return anchored
    anchor = _message_anchor_label(request, lesson_context, graph_context)
    if anchor and anchor.casefold() not in anchored.casefold():
        anchored = f"{anchor}: {anchored}"
    return anchored


def _structured_tutor_prompt(
    *,
    mode: str,
    user_goal: str,
    request: TutorChatRequest,
    citations: list[Citation],
    profile_context: dict | None,
    history_context: dict | None,
    lesson_context: dict | None,
    graph_context: dict | None,
) -> str:
    lesson_title = str((lesson_context or {}).get("title") or "").strip() or "No persisted lesson title"
    lesson_summary = str((lesson_context or {}).get("summary") or "").strip() or "No persisted lesson summary."
    covered_concepts_block = "\n".join(_lesson_covered_concept_lines(lesson_context)) or "- No explicit lesson concept coverage metadata."
    lesson_block = "\n".join(_lesson_context_block_lines(lesson_context)) or "- No persisted lesson body available."
    profile_block = "\n".join(_profile_context_lines(profile_context)) or "- No profile preferences available."
    history_block = "\n".join(_history_context_lines(history_context)) or "- No prior tutor history."
    graph_block = "\n".join(_graph_context_lines(graph_context, lesson_context)) or "- No graph/mastery context available."
    citations_block = _citations_block(citations)
    focused_node_block = (
        f"- focus_concept_label: {request.focus_concept_label}\n- focus_concept_id: {request.focus_concept_id}"
        if request.focus_concept_label or request.focus_concept_id
        else "- No explicit graph-selected concept focus."
    )
    next_unlock = dict((graph_context or {}).get("next_unlock") or {})
    next_unlock_title = str(next_unlock.get("topic_title") or "").strip() or "No downstream unlock identified."
    next_unlock_reason = str(next_unlock.get("reason") or "").strip() or "No explicit next-unlock reason available."
    anchor_label = _message_anchor_label(request, lesson_context, graph_context) or lesson_title
    mode_guidance = {
        "teach": "Explain clearly, stepwise, with one concrete lesson-grounded example and one likely mistake to avoid.",
        "socratic": "Ask one guiding question first, then give a short nudge instead of a full lecture.",
        "diagnose": "Explain why this topic matters now, point out the weakest prerequisite link, and name the next best action.",
        "drill": "Generate one short drill prompt, then coach the learner with a compact lesson-grounded answer.",
        "recap": "Compress the topic into three sharp points, one memory hook, and one exam-useful reminder.",
        "exam-practice": "Coach the learner in WAEC style: exam-focused, precise, time-aware, and grounded in this lesson.",
    }.get(mode, "Explain clearly and stay grounded.")
    return (
        "You are Mastery AI, a graph-aware tutor for Nigerian SSS learners.\n"
        "Return JSON only.\n"
        "Use lesson context as primary grounding, graph/mastery context as adaptive guidance, and retrieved chunks as evidence.\n"
        "Do not fabricate facts, sources, or topic progression.\n"
        "Never claim mastery updates happened.\n"
        "Do not mention internal IDs in visible text.\n\n"
        f"Mode: {mode}\n"
        f"Mode guidance: {mode_guidance}\n"
        f"Student goal: {user_goal}\n"
        f"Scope: subject={request.subject}, level={request.sss_level}, term={request.term}\n"
        f"Current lesson title: {lesson_title}\n"
        f"Current lesson summary: {lesson_summary}\n\n"
        f"Preferred visible anchor label: {anchor_label}\n"
        f"Graph-selected focus:\n{focused_node_block}\n\n"
        f"Lesson covered concepts:\n{covered_concepts_block}\n\n"
        f"Next unlock:\n- topic_title: {next_unlock_title}\n- reason: {next_unlock_reason}\n\n"
          f"Lesson body:\n{lesson_block}\n\n"
        f"Student profile:\n{profile_block}\n\n"
        f"Recent tutor history:\n{history_block}\n\n"
        f"Graph / mastery context:\n{graph_block}\n\n"
        f"Retrieved citations:\n{citations_block}\n\n"
        "Return EXACT JSON shape:\n"
        "{\n"
        '  "assistant_message": "string",\n'
        '  "key_points": ["string"],\n'
        '  "concept_focus": ["string"],\n'
        '  "prerequisite_warning": "string or empty",\n'
        '  "next_action": "string",\n'
        '  "recommended_assessment": "string or empty"\n'
        "}\n"
        "Rules:\n"
        "- assistant_message must be engaging, concise, and lesson-specific, not generic.\n"
        "- The first sentence must name the visible anchor label or current lesson in plain language.\n"
        "- Use at least one concrete example, rule, or detail from the lesson body or retrieved citations.\n"
        "- If graph-selected focus exists, center the explanation on that concept first.\n"
        "- If a weak prerequisite or next unlock is available, mention one of them naturally when useful.\n"
        "- Avoid filler openers like 'This topic is important', 'Let us break it down', or 'right now' unless necessary.\n"
        "- key_points should contain 2 to 4 short bullets.\n"
        "- concept_focus should name the most relevant concepts in readable language.\n"
        "- prerequisite_warning should be empty if not needed.\n"
        "- next_action must tell the student exactly what to do next.\n"
        "- recommended_assessment should suggest one check if useful, else empty.\n"
    )


def _validate_structured_tutor_payload(
    parsed: dict | None,
    *,
    mode: str,
    request: TutorChatRequest,
    citations: list[Citation],
    actions: list[str],
    graph_context: dict | None,
    lesson_context: dict | None,
) -> TutorChatResponse:
    if not parsed:
        raise RuntimeError("tutor generation returned invalid JSON")
    assistant_message = _tighten_tutor_message(
        str(parsed.get("assistant_message") or ""),
        request=request,
        lesson_context=lesson_context,
        graph_context=graph_context,
    )
    if not assistant_message:
        raise RuntimeError("tutor generation returned empty assistant message")
    key_points = [
        " ".join(str(item).split()).strip()
        for item in list(parsed.get("key_points") or [])
        if " ".join(str(item).split()).strip()
    ][:4]
    concept_focus = [
        " ".join(str(item).split()).strip()
        for item in list(parsed.get("concept_focus") or [])
        if " ".join(str(item).split()).strip()
    ][:4]
    if request.focus_concept_label:
        concept_focus = list(dict.fromkeys([request.focus_concept_label] + concept_focus))[:4]
    elif not concept_focus:
        concept_focus = _weak_concept_labels(graph_context, lesson_context) or _lesson_covered_concept_lines(lesson_context, max_items=3)
    prerequisite_warning = " ".join(str(parsed.get("prerequisite_warning") or "").split()).strip() or None
    next_action = " ".join(str(parsed.get("next_action") or "").split()).strip() or None
    recommended_assessment = " ".join(str(parsed.get("recommended_assessment") or "").split()).strip() or None
    return TutorChatResponse(
        assistant_message=assistant_message,
        citations=citations,
        actions=actions,
        recommendations=_recommendations_from_graph(request=request, graph_context=graph_context),
        mode=mode,  # type: ignore[arg-type]
        key_points=key_points,
        concept_focus=concept_focus,
        prerequisite_warning=prerequisite_warning,
        next_action=next_action,
        recommended_assessment=recommended_assessment,
        recommended_topic_title=(
            str(dict((graph_context or {}).get("next_unlock") or {}).get("topic_title") or "").strip() or None
        ),
    )


def _plain_text_tutor_payload(
    raw: str,
    *,
    mode: str,
    request: TutorChatRequest,
    citations: list[Citation],
    actions: list[str],
    graph_context: dict | None,
    lesson_context: dict | None,
) -> TutorChatResponse:
    assistant_message = _tighten_tutor_message(
        str(raw or ""),
        request=request,
        lesson_context=lesson_context,
        graph_context=graph_context,
    )
    if not assistant_message:
        raise RuntimeError("tutor generation returned empty text")
    return TutorChatResponse(
        assistant_message=assistant_message,
        citations=citations,
        actions=actions,
        recommendations=_recommendations_from_graph(request=request, graph_context=graph_context),
        mode=mode,  # type: ignore[arg-type]
        key_points=_weak_concept_labels(graph_context, lesson_context)[:3],
        concept_focus=(
            [request.focus_concept_label]
            if request.focus_concept_label
            else _weak_concept_labels(graph_context, lesson_context) or _lesson_covered_concept_lines(lesson_context, max_items=3)
        ),
        prerequisite_warning=None,
        next_action="Use the graph rail or ask for one focused checkpoint next.",
        recommended_assessment="Ask for one quick checkpoint to confirm understanding.",
        recommended_topic_title=(
            str(dict((graph_context or {}).get("next_unlock") or {}).get("topic_title") or "").strip() or None
        ),
    )


def _collect_tutor_context(request: TutorChatRequest) -> tuple[list[Citation], dict | None, dict | None, dict | None, dict | None, list[str]]:
    citations: list[Citation] = []
    profile_context: dict | None = None
    history_context: dict | None = None
    lesson_context: dict | None = None
    graph_context: dict | None = None
    actions: list[str] = ["ENFORCED_SCOPE_POLICY", "NO_MASTERY_WRITE_NO_EVIDENCE"]

    actions.append("CALLED_TOOL:internal_postgres.profile")
    try:
        profile_context = _internal_profile_context(request)
    except Exception as exc:
        logger.warning("tutor.context profile fetch failed: %s", exc)
        actions.append("PROFILE_CONTEXT_FAILED")
    else:
        actions.append("USED_PROFILE_CONTEXT")

    actions.append("CALLED_TOOL:internal_postgres.history")
    try:
        history_context = _internal_history_context(request)
    except Exception as exc:
        logger.warning("tutor.context history fetch failed: %s", exc)
        actions.append("SESSION_HISTORY_FAILED")
    else:
        actions.append("USED_SESSION_HISTORY")

    if request.topic_id:
        actions.append("CALLED_TOOL:internal_postgres.lesson_context")
        try:
            lesson_context = _internal_lesson_context(request)
        except Exception as exc:
            logger.warning("tutor.context lesson-context fetch failed: %s", exc)
            actions.append("LESSON_CONTEXT_FAILED")
        else:
            if _lesson_context_available(lesson_context):
                actions.append("USED_LESSON_CONTEXT")
                source = _lesson_context_source(lesson_context)
                if source == "structured":
                    actions.append("USED_STRUCTURED_LESSON_CONTEXT")
                elif source == "personalized":
                    actions.append("USED_PERSONALIZED_LESSON_CONTEXT")
            else:
                actions.append("LESSON_CONTEXT_EMPTY")

    actions.append("CALLED_TOOL:internal_graph.context")
    try:
        graph_context = _internal_graph_context(request)
    except Exception as exc:
        logger.warning("tutor.context graph-context fetch failed: %s", exc)
        actions.append("GRAPH_CONTEXT_FAILED")
    else:
        actions.append("USED_GRAPH_CONTEXT")

    actions.append("CALLED_TOOL:internal_rag.retrieve")
    try:
        citations = _internal_rag_retrieve(request)
    except Exception as exc:
        logger.warning("tutor.context retrieval failed: %s", exc)
        actions.append("RAG_RETRIEVAL_FAILED")
    else:
        actions.append("USED_RAG_CONTEXT" if citations else "NO_RAG_CONTEXT")

    return citations, profile_context, history_context, lesson_context, graph_context, actions


def _run_structured_tutor_mode(
    *,
    request: TutorChatRequest,
    mode: str,
    user_goal: str,
) -> TutorChatResponse:
    started_at = now_ms()
    citations, profile_context, history_context, lesson_context, graph_context, actions = _collect_tutor_context(request)
    if request.focus_concept_label or request.focus_concept_id:
        actions.append("USED_GRAPH_SELECTED_FOCUS")

    if not citations and not _lesson_context_available(lesson_context):
        topic_part = f", topic_id={request.topic_id}" if request.topic_id else ""
        log_timed_event(
            logger,
            "tutor.mode",
            started_at,
            log_level=30,
            outcome="no_context",
            mode=mode,
            subject=request.subject,
            term=request.term,
            topic_id=request.topic_id or "none",
        )
        return TutorChatResponse(
            assistant_message=(
                "Tutor unavailable: no lesson-aware context found for "
                f"subject={request.subject}, level={request.sss_level}, term={request.term}{topic_part}. "
                "Generate the lesson successfully and ensure approved curriculum chunks exist for this scope/topic."
            ),
            citations=[],
            actions=actions + ["NO_CONTEXT_ABORTED"],
            recommendations=[],
            mode=mode,  # type: ignore[arg-type]
        )

    prompt = _structured_tutor_prompt(
        mode=mode,
        user_goal=user_goal,
        request=request,
        citations=citations,
        profile_context=profile_context,
        history_context=history_context,
        lesson_context=lesson_context,
        graph_context=graph_context,
    )
    try:
        raw = _llm_generate(prompt)
    except (LLMClientError, Exception) as exc:
        detail = str(exc) or "unknown model error"
        logger.warning("tutor.mode llm generation failed mode=%s detail=%s", mode, detail)
        log_timed_event(
            logger,
            "tutor.mode",
            started_at,
            log_level=30,
            outcome="llm_error",
            mode=mode,
            subject=request.subject,
            term=request.term,
            topic_id=request.topic_id or "none",
            detail=detail,
        )
        return TutorChatResponse(
            assistant_message=f"Tutor unavailable: model generation failed: {detail}",
            citations=citations,
            actions=actions + ["LLM_UNAVAILABLE"],
            recommendations=[],
            mode=mode,  # type: ignore[arg-type]
        )

    parsed = _extract_json_object(raw)
    if parsed is None:
        response = _plain_text_tutor_payload(
            raw,
            mode=mode,
            request=request,
            citations=citations,
            actions=actions + [f"MODE:{mode.upper()}", "LLM_PLAIN_TEXT_FALLBACK"],
            graph_context=graph_context,
            lesson_context=lesson_context,
        )
    else:
        response = _validate_structured_tutor_payload(
            parsed,
            mode=mode,
            request=request,
            citations=citations,
            actions=actions + [f"MODE:{mode.upper()}"],
            graph_context=graph_context,
            lesson_context=lesson_context,
        )
    log_timed_event(
        logger,
        "tutor.mode",
        started_at,
        outcome="success",
        mode=mode,
        subject=request.subject,
        sss_level=request.sss_level,
        term=request.term,
        topic_id=request.topic_id or "none",
        lesson_context=_lesson_context_available(lesson_context),
        context_source=_lesson_context_source(lesson_context) or "none",
        covered_concepts=len(_lesson_covered_concept_ids(lesson_context)),
        citations=len(citations),
        graph_context=bool(graph_context),
        history_messages=len(list((history_context or {}).get("messages") or [])),
    )
    return response


def handle_question(
    request: TutorRequest,
    *,
    settings: "Settings",
    curriculum: "CurriculumResolver",
    retriever: "RagRetriever",
    prereqs: "PrereqService",
    llm: "LLMClient",
    mastery: "MasteryUpdater",
    cost_tracker: "CostTracker",
) -> TutorResponse:
    """MVP orchestration:
    resolve scope -> retrieve chunks -> prereq hints -> LLM response -> mastery update -> logs/cost
    """

    from ai_core.core_engine.llm.prompts import build_tutor_prompt
    from ai_core.core_engine.rag.citations import format_citations
    # 1) Safety and hygiene
    user_text = request.message[: settings.max_input_chars]
    user_text = sanitize_user_text(user_text)
    if settings.enable_basic_moderation:
        basic_moderate(user_text)

    # 2) Curriculum scoping
    scope = curriculum.resolve_scope(
        subject_id=request.subject_id,
        sss_level=request.sss_level,
        term=int(request.term),
        topic_id=request.topic_id,
    )

    # 3) RAG retrieval with strict filters
    chunks = retriever.retrieve(
        query=user_text,
        subject_id=scope.subject_id,
        sss_level=scope.sss_level,
        term=scope.term,
        allowed_topic_ids=scope.allowed_topic_ids,
        approved_only=True,
        top_k=6,
    )
    citations = format_citations(chunks)

    # 4) Optional prerequisite chain
    remediation_prereqs = []
    if request.topic_id:
        remediation_prereqs = prereqs.get_prerequisites_for_topic(topic_id=request.topic_id)

    # 5) LLM prompt + generation
    prompt = build_tutor_prompt(
        user_message=user_text,
        mode=request.mode,
        sss_level=request.sss_level,
        term=int(request.term),
        citations=citations,
        remediation_prereqs=remediation_prereqs,
    )
    with cost_tracker.track(request_id=request.session_id or "single"):
        assistant_text = llm.generate(prompt)

    # 6) Minimal mastery update (only on practice for MVP)
    actions = []
    if request.mode == "practice" and request.topic_id:
        mastery.update_from_interaction(
            user_id=request.user_id,
            subject_id=request.subject_id,
            topic_id=request.topic_id,
            interaction_type="practice",
            signal={"message": user_text},
        )
        actions.append("UPDATED_MASTERY_BASIC")

    # 7) Logs
    logger.info(
        "tutor.handle_question",
        extra={
            "user_id": request.user_id,
            "subject_id": request.subject_id,
            "sss_level": request.sss_level,
            "term": int(request.term),
            "topic_id": request.topic_id,
            "mode": request.mode,
            "rag_chunks": len(chunks),
        },
    )

    return TutorResponse(
        assistant_message=assistant_text,
        citations=[Citation(**c) for c in citations],
        remediation_prereqs=remediation_prereqs,
        actions=actions,
        cost=cost_tracker.snapshot(),
    )


def run_tutor_chat(request: TutorChatRequest) -> TutorChatResponse:
    """Run agentic tutor chat flow using retrieval tool + LLM generation."""
    try:
        safe_message = _sanitize_and_moderate(request.message)
    except ModerationError:
        return TutorChatResponse(
            assistant_message=(
                "I can't help with that request. "
                "Please ask a curriculum-based study question for your selected scope."
            ),
            citations=[],
            actions=["REFUSED_SAFETY_POLICY"],
            recommendations=[],
        )

    request = request.model_copy(update={"message": safe_message})
    mode = request.mode or _infer_tutor_mode_from_message(request.message)
    return _run_structured_tutor_mode(request=request, mode=mode, user_goal=request.message)


def run_tutor_recap(request: TutorRecapRequest) -> TutorChatResponse:
    chat_request = TutorChatRequest(
        student_id=request.student_id,
        session_id=request.session_id,
        subject=request.subject,
        sss_level=request.sss_level,
        term=request.term,
        topic_id=request.topic_id,
        message="Recap this lesson in three sharp points and one memory hook.",
    )
    actions: list[str] = ["ENFORCED_SCOPE_POLICY", "NO_MASTERY_WRITE_NO_EVIDENCE", "FAST_RECAP_ONLY"]
    lesson_context: dict | None = None
    graph_context: dict | None = None

    try:
        lesson_context = _internal_lesson_context(chat_request)
    except Exception as exc:
        logger.warning("tutor.recap lesson-context fetch failed: %s", exc)
        actions.append("LESSON_CONTEXT_FAILED")
    else:
        if _lesson_context_available(lesson_context):
            actions.append("USED_LESSON_CONTEXT")
            source = _lesson_context_source(lesson_context)
            if source == "structured":
                actions.append("USED_STRUCTURED_LESSON_CONTEXT")
            elif source == "personalized":
                actions.append("USED_PERSONALIZED_LESSON_CONTEXT")
        else:
            actions.append("LESSON_CONTEXT_EMPTY")

    try:
        graph_context = _internal_graph_context(chat_request)
    except Exception as exc:
        logger.warning("tutor.recap graph-context fetch failed: %s", exc)
        actions.append("GRAPH_CONTEXT_FAILED")
    else:
        actions.append("USED_GRAPH_CONTEXT")

    if _lesson_context_available(lesson_context):
        return _fast_recap_response(
            request=chat_request,
            lesson_context=lesson_context,
            graph_context=graph_context,
            actions=actions,
        )

    return _run_structured_tutor_mode(
        request=chat_request,
        mode="recap",
        user_goal="Give a concise revision recap of the active lesson.",
    )


def run_tutor_drill(request: TutorDrillRequest) -> TutorChatResponse:
    chat_request = TutorChatRequest(
        student_id=request.student_id,
        session_id=request.session_id,
        subject=request.subject,
        sss_level=request.sss_level,
        term=request.term,
        topic_id=request.topic_id,
        message=f"Generate one {request.difficulty} drill for this lesson and coach me through it.",
    )
    return _run_structured_tutor_mode(
        request=chat_request,
        mode="drill",
        user_goal=f"Create one {request.difficulty} drill around the active lesson and coach the learner.",
    )


def run_tutor_prereq_bridge(request: TutorPrereqBridgeRequest) -> TutorChatResponse:
    chat_request = TutorChatRequest(
        student_id=request.student_id,
        session_id=request.session_id,
        subject=request.subject,
        sss_level=request.sss_level,
        term=request.term,
        topic_id=request.topic_id,
        message="Explain the prerequisite bridge into this lesson and why it matters now.",
    )
    return _run_structured_tutor_mode(
        request=chat_request,
        mode="diagnose",
        user_goal="Explain the weakest prerequisite bridge feeding the active lesson and what it unlocks next.",
    )


def run_tutor_study_plan(request: TutorStudyPlanRequest) -> TutorChatResponse:
    chat_request = TutorChatRequest(
        student_id=request.student_id,
        session_id=request.session_id,
        subject=request.subject,
        sss_level=request.sss_level,
        term=request.term,
        topic_id=request.topic_id,
        message=f"Create a focused {request.horizon_days}-day study plan for this lesson.",
    )
    return _run_structured_tutor_mode(
        request=chat_request,
        mode="teach",
        user_goal=f"Create a focused {request.horizon_days}-day study plan using the current lesson, graph weaknesses, and retrieval evidence.",
    )


def run_tutor_assessment_start(request: TutorAssessmentStartRequest) -> TutorAssessmentStartResponse:
    started_at = now_ms()
    try:
        profile_context = _internal_profile_context(
            TutorChatRequest(
                student_id=request.student_id,
                session_id=request.session_id,
                subject=request.subject,
                sss_level=request.sss_level,
                term=request.term,
                topic_id=request.topic_id,
                message="start assessment",
            )
        )
    except Exception:
        profile_context = None

    try:
        lesson_context = _internal_lesson_context(
            TutorChatRequest(
                student_id=request.student_id,
                session_id=request.session_id,
                subject=request.subject,
                sss_level=request.sss_level,
                term=request.term,
                topic_id=request.topic_id,
                message="start assessment",
            )
        )
    except Exception as exc:
        logger.warning("tutor.run_tutor_assessment_start lesson-context fetch failed: %s", exc)
        lesson_context = None

    try:
        graph_context = _internal_graph_context(
            TutorChatRequest(
                student_id=request.student_id,
                session_id=request.session_id,
                subject=request.subject,
                sss_level=request.sss_level,
                term=request.term,
                topic_id=request.topic_id,
                message="start assessment",
            )
        )
    except Exception as exc:
        logger.warning("tutor.run_tutor_assessment_start graph-context fetch failed: %s", exc)
        graph_context = None

    try:
        citations = _internal_rag_retrieve_for_prompt(
            student_id=request.student_id,
            session_id=request.session_id,
            subject=request.subject,
            sss_level=request.sss_level,
            term=int(request.term),
            topic_id=request.topic_id,
            message=(
                f"{request.subject} {request.sss_level} term {request.term} "
                f"{request.focus_concept_label or request.topic_id} assessment question"
            ),
        )
    except Exception as exc:
        logger.warning("tutor.run_tutor_assessment_start retrieval failed: %s", exc)
        citations = []

    if not citations and not _lesson_context_available(lesson_context):
        log_timed_event(
            logger,
            "tutor.assessment.start",
            started_at,
            log_level=30,
            outcome="no_context",
            subject=request.subject,
            term=request.term,
            topic_id=request.topic_id or "none",
        )
        raise RuntimeError(
            "No lesson-aware assessment context found. Generate the lesson and ensure approved curriculum chunks exist."
        )

    target = _assessment_target_concept(
        lesson_context=lesson_context,
        graph_context=graph_context,
        citations=citations,
        requested_focus_concept_id=request.focus_concept_id,
        requested_focus_concept_label=request.focus_concept_label,
    )
    if target is None:
        log_timed_event(
            logger,
            "tutor.assessment.start",
            started_at,
            log_level=30,
            outcome="no_target_concept",
            subject=request.subject,
            term=request.term,
            topic_id=request.topic_id or "none",
        )
        raise RuntimeError("No valid target concept found for tutor assessment.")
    concept_id, concept_label = target

    prompt = _assessment_start_prompt(
        request,
        concept_id=concept_id,
        concept_label=concept_label,
        lesson_context=lesson_context,
        graph_context=graph_context,
        citations=citations,
    )
    try:
        raw = _llm_generate(prompt)
    except (LLMClientError, Exception) as exc:
        log_timed_event(
            logger,
            "tutor.assessment.start",
            started_at,
            log_level=30,
            outcome="llm_error",
            subject=request.subject,
            term=request.term,
            topic_id=request.topic_id or "none",
            concept_id=concept_id,
            detail=str(exc),
        )
        raise RuntimeError(f"assessment question generation failed: {exc}") from exc

    parsed = _extract_json_object(raw)
    out = _validate_assessment_start_payload(
        parsed,
        concept_id=concept_id,
        concept_label=concept_label,
        citations=citations,
    )
    actions = list(out.actions)
    if profile_context:
        actions.append("USED_PROFILE_CONTEXT")
    if graph_context:
        actions.append("USED_GRAPH_CONTEXT")
    actions.append("ASSESSMENT_TARGET_CONCEPT")
    if request.focus_concept_id or request.focus_concept_label:
        actions.append("USED_GRAPH_SELECTED_FOCUS")
    response = out.model_copy(update={"actions": actions})
    log_timed_event(
        logger,
        "tutor.assessment.start",
        started_at,
        outcome="success",
        subject=request.subject,
        term=request.term,
        topic_id=request.topic_id or "none",
        concept_id=response.concept_id,
        citations=len(response.citations),
        lesson_context=_lesson_context_available(lesson_context),
        graph_context=bool(graph_context),
        focus_selected=bool(request.focus_concept_id or request.focus_concept_label),
    )
    return response


def run_tutor_assessment_submit(request: TutorAssessmentSubmitRequest) -> TutorAssessmentSubmitResponse:
    started_at = now_ms()
    try:
        lesson_context = _internal_lesson_context(
            TutorChatRequest(
                student_id=request.student_id,
                session_id=request.session_id,
                subject=request.subject,
                sss_level=request.sss_level,
                term=request.term,
                topic_id=request.topic_id,
                message=request.question,
            )
        )
    except Exception as exc:
        logger.warning("tutor.run_tutor_assessment_submit lesson-context fetch failed: %s", exc)
        lesson_context = None

    try:
        graph_context = _internal_graph_context(
            TutorChatRequest(
                student_id=request.student_id,
                session_id=request.session_id,
                subject=request.subject,
                sss_level=request.sss_level,
                term=request.term,
                topic_id=request.topic_id,
                message=request.question,
            )
        )
    except Exception as exc:
        logger.warning("tutor.run_tutor_assessment_submit graph-context fetch failed: %s", exc)
        graph_context = None

    try:
        citations = _internal_rag_retrieve_for_prompt(
            student_id=request.student_id,
            session_id=request.session_id,
            subject=request.subject,
            sss_level=request.sss_level,
            term=int(request.term),
            topic_id=request.topic_id,
            message=f"{request.question} {request.concept_label} {request.answer}",
        )
    except Exception as exc:
        logger.warning("tutor.run_tutor_assessment_submit retrieval failed: %s", exc)
        citations = []

    if not citations and not _lesson_context_available(lesson_context):
        log_timed_event(
            logger,
            "tutor.assessment.submit",
            started_at,
            log_level=30,
            outcome="no_context",
            subject=request.subject,
            term=request.term,
            topic_id=request.topic_id or "none",
            concept_id=request.concept_id,
        )
        raise RuntimeError(
            "No lesson-aware assessment context found. Generate the lesson and ensure approved curriculum chunks exist."
        )

    prompt = _assessment_submit_prompt(
        request,
        lesson_context=lesson_context,
        graph_context=graph_context,
        citations=citations,
    )
    try:
        raw = _llm_generate(prompt)
    except (LLMClientError, Exception) as exc:
        log_timed_event(
            logger,
            "tutor.assessment.submit",
            started_at,
            log_level=30,
            outcome="llm_error",
            subject=request.subject,
            term=request.term,
            topic_id=request.topic_id or "none",
            concept_id=request.concept_id,
            detail=str(exc),
        )
        raise RuntimeError(f"assessment answer evaluation failed: {exc}") from exc

    parsed = _extract_json_object(raw)
    response = _validate_assessment_submit_payload(parsed, request=request, citations=citations)
    log_timed_event(
        logger,
        "tutor.assessment.submit",
        started_at,
        outcome="success",
        subject=request.subject,
        term=request.term,
        topic_id=request.topic_id or "none",
        concept_id=request.concept_id,
        score=response.score,
        citations=len(response.citations),
        lesson_context=_lesson_context_available(lesson_context),
        graph_context=bool(graph_context),
    )
    return response


def run_tutor_hint(request: TutorHintRequest) -> TutorHintResponse:
    """Return a concise scaffolded hint for an in-progress quiz question."""
    try:
        safe_note = _sanitize_and_moderate(request.message or "")
    except ModerationError:
        return TutorHintResponse(
            hint="I cannot assist with that request. Ask a safe, curriculum-focused question.",
            strategy="policy_refusal",
        )

    prompt = (
        "You are an exam coach. Give a short guided hint only, no full answer.\n"
        f"Scope: {request.subject}, {request.sss_level}, term {request.term}.\n"
        f"Question ID: {request.question_id}\n"
        f"Student note: {safe_note}\n"
    )
    try:
        hint_text = _llm_generate(prompt)
    except (LLMClientError, Exception):
        hint_text = "Focus on the core rule, eliminate one wrong option, then compare the remaining choices."
    return TutorHintResponse(hint=hint_text, strategy="guided_hint")


def run_tutor_explain_mistake(request: TutorExplainMistakeRequest) -> TutorExplainMistakeResponse:
    """Explain why an answer is wrong and provide a targeted correction tip."""
    try:
        safe_question = _sanitize_and_moderate(request.question)
        safe_student_answer = _sanitize_and_moderate(request.student_answer, max_chars=500)
        safe_correct_answer = _sanitize_and_moderate(request.correct_answer, max_chars=500)
    except ModerationError:
        return TutorExplainMistakeResponse(
            explanation="I cannot process that content. Please submit a safe curriculum question.",
            improvement_tip="Rephrase your question using neutral academic language.",
        )

    prompt = (
        "Explain the student's mistake briefly and give one improvement tip.\n"
        f"Scope: {request.subject}, {request.sss_level}, term {request.term}.\n"
        f"Question: {safe_question}\n"
        f"Student answer: {safe_student_answer}\n"
        f"Correct answer: {safe_correct_answer}\n"
    )
    try:
        explanation = _llm_generate(prompt)
    except (LLMClientError, Exception):
        explanation = (
            "Your answer did not follow the governing rule in this question. "
            f"You selected '{request.student_answer}' while the correct answer is '{request.correct_answer}'."
        )
    return TutorExplainMistakeResponse(
        explanation=explanation,
        improvement_tip="Write the relevant rule first, then verify each option against that rule.",
    )
