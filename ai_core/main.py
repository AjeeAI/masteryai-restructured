"""Lightweight ai-core HTTP app for container/service health."""

from __future__ import annotations

import os
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from ai_core.core_engine.orchestration.quiz_engine import (
    generate_quiz_questions,
    generate_quiz_insights,
    QuizGenerationError,
)
from ai_core.core_engine.integrations.internal_api import internal_service_key_configured
from ai_core.core_engine.observability.telemetry import telemetry_snapshot
from ai_core.core_engine.orchestration.tutor_engine import (
    run_tutor_drill,
    run_tutor_assessment_start,
    run_tutor_assessment_submit,
    run_tutor_chat,
    run_tutor_explain_mistake,
    run_tutor_hint,
    run_tutor_prereq_bridge,
    run_tutor_recap,
    run_tutor_study_plan,
)
from ai_core.core_engine.api_contracts.schemas import (
    TutorDrillRequest,
    TutorAssessmentStartRequest,
    TutorAssessmentStartResponse,
    TutorAssessmentSubmitRequest,
    TutorAssessmentSubmitResponse,
    TutorChatRequest,
    TutorChatResponse,
    TutorExplainMistakeRequest,
    TutorExplainMistakeResponse,
    TutorHintRequest,
    TutorHintResponse,
    TutorPrereqBridgeRequest,
    TutorRecapRequest,
    TutorStudyPlanRequest,
)
from ai_core.core_engine.api_contracts.quiz_schemas import (
    QuizGenerateRequest,
    QuizGenerateResponse,
    QuizInsightsResponse,
    QuestionSchema,
)

app = FastAPI(title="Mastery AI Core", version="0.1.0")

_ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH)


def _parse_cors_origins(raw_value: str) -> list[str]:
    value = (raw_value or "").strip()
    if not value:
        return ["*"]
    if value == "*":
        return ["*"]
    if value.startswith("["):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            pass
    return [item.strip() for item in value.split(",") if item.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_cors_origins(os.getenv("CORS_ORIGINS", "*")),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"service": "ai-core", "status": "online"}


@app.get("/health")
def health():
    llm_key_present = bool(os.getenv("GROQ_API_KEY") or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY"))
    postgres_dsn_present = bool(os.getenv("POSTGRES_DSN") or os.getenv("DATABASE_URL"))
    checks = {
        "llm_api_key": "configured" if llm_key_present else "not_configured",
        "postgres_dsn": "configured" if postgres_dsn_present else "not_configured",
        "backend_internal_postgres_url": "configured"
        if os.getenv("BACKEND_INTERNAL_POSTGRES_URL")
        else "not_configured",
        "backend_internal_rag_url": "configured"
        if os.getenv("BACKEND_INTERNAL_RAG_URL")
        else "not_configured",
        "backend_internal_graph_context_url": "configured"
        if os.getenv("BACKEND_INTERNAL_GRAPH_CONTEXT_URL")
        else "not_configured",
        "internal_service_key": "configured" if internal_service_key_configured() else "not_configured",
        "neo4j_uri": "configured" if os.getenv("NEO4J_URI") else "not_configured",
        "redis_url": "configured" if os.getenv("REDIS_URL") else "not_configured",
        "qdrant_url": "configured" if os.getenv("QDRANT_URL") else "not_configured",
        "vector_index_name": "configured"
        if (os.getenv("QDRANT_COLLECTION") or os.getenv("VECTOR_INDEX_NAME"))
        else "not_configured",
    }
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "runtime": {
            "status": "ok",
            "telemetry": telemetry_snapshot(),
        },
    }


@app.post("/quiz/generate", response_model=QuizGenerateResponse)
async def quiz_generate(payload: QuizGenerateRequest):
    try:
        questions_raw = await generate_quiz_questions(
            student_id=payload.student_id,
            subject=payload.subject,
            sss_level=payload.sss_level,
            term=payload.term,
            topic_id=payload.topic_id,
            purpose=payload.purpose,
            difficulty=payload.difficulty,
            num_questions=payload.num_questions,
        )
    except QuizGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    # Convert dicts -> Pydantic models
    questions = [QuestionSchema(**q) for q in questions_raw]
    return QuizGenerateResponse(questions=questions)


@app.get("/quiz/{quiz_id}/attempt/{attempt_id}/insights", response_model=QuizInsightsResponse)
async def quiz_insights(quiz_id: UUID, attempt_id: UUID):
    insights = await generate_quiz_insights(quiz_id=quiz_id, attempt_id=attempt_id)
    return QuizInsightsResponse(insights=insights)


@app.post("/tutor/chat", response_model=TutorChatResponse)
def tutor_chat(payload: TutorChatRequest):
    return run_tutor_chat(payload)


@app.post("/tutor/recap", response_model=TutorChatResponse)
def tutor_recap(payload: TutorRecapRequest):
    return run_tutor_recap(payload)


@app.post("/tutor/drill", response_model=TutorChatResponse)
def tutor_drill(payload: TutorDrillRequest):
    return run_tutor_drill(payload)


@app.post("/tutor/prereq-bridge", response_model=TutorChatResponse)
def tutor_prereq_bridge(payload: TutorPrereqBridgeRequest):
    return run_tutor_prereq_bridge(payload)


@app.post("/tutor/study-plan", response_model=TutorChatResponse)
def tutor_study_plan(payload: TutorStudyPlanRequest):
    return run_tutor_study_plan(payload)


@app.post("/tutor/assessment/start", response_model=TutorAssessmentStartResponse)
def tutor_assessment_start(payload: TutorAssessmentStartRequest):
    return run_tutor_assessment_start(payload)


@app.post("/tutor/assessment/submit", response_model=TutorAssessmentSubmitResponse)
def tutor_assessment_submit(payload: TutorAssessmentSubmitRequest):
    return run_tutor_assessment_submit(payload)


@app.post("/tutor/hint", response_model=TutorHintResponse)
def tutor_hint(payload: TutorHintRequest):
    return run_tutor_hint(payload)


@app.post("/tutor/explain-mistake", response_model=TutorExplainMistakeResponse)
def tutor_explain_mistake(payload: TutorExplainMistakeRequest):
    return run_tutor_explain_mistake(payload)
