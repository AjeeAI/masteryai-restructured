"""Lightweight ai-core HTTP app for container/service health."""

from __future__ import annotations

import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, HTTPException, status, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# --- SCHEMA / CONTRACT IMPORTS ---
from core_engine.api_contracts.lesson_schemas import LessonGenerateRequest, LessonGenerateResponse
from core_engine.api_contracts.diagnostic_schemas import (
    DiagnosticGenerateRequest,
    DiagnosticGenerateResponse,
)
from core_engine.api_contracts.quiz_schemas import (
    QuizGenerateRequest,
    QuizGenerateResponse,
    QuizInsightsResponse,
    QuestionSchema,
)
from core_engine.api_contracts.schemas import (
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

# --- ORCHESTRATION & ENGINE IMPORTS ---
from core_engine.orchestration.lesson_engine import generate_lesson_content
from core_engine.orchestration.diagnostic_engine import generate_pedagogical_questions
from core_engine.orchestration.quiz_engine import (
    generate_quiz_questions,
    generate_quiz_insights,
    QuizGenerationError,
)
from core_engine.orchestration.tutor_engine import (
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

# --- INTEGRATIONS & OBSERVABILITY ---
from core_engine.integrations.internal_api import internal_service_key_configured
from core_engine.observability.telemetry import telemetry_snapshot

# --- APP SETUP ---
app = FastAPI(title="Mastery AI Core", version="0.1.0")
logger = logging.getLogger(__name__)

_ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH)

# --- SECURITY HANDLER ---
async def verify_internal_key(x_internal_service_key: str = Header(None)):
    """
    Security Bouncer: Ensures only the Backend (which knows the secret key) 
    can call these endpoints.
    """
    internal_key = os.getenv("INTERNAL_SERVICE_KEY")
    if not x_internal_service_key or x_internal_service_key != internal_key:
        logger.warning(f"Unauthorized access attempt to AI Core from: {x_internal_service_key}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Invalid or missing Internal Service Key"
        )

# --- CORS SETUP ---
def _parse_cors_origins(raw_value: str) -> list[str]:
    value = (raw_value or "").strip()
    if not value or value == "*":
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

# --- SYSTEM ROUTES ---

@app.get("/")
def root():
    return {"service": "ai-core", "status": "online"}

@app.get("/health")
def health():
    # Removed Groq. Now checking for Gemini primarily.
    llm_key_present = bool(os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY"))
    postgres_dsn_present = bool(os.getenv("POSTGRES_DSN") or os.getenv("DATABASE_URL"))
    checks = {
        "llm_api_key": "configured" if llm_key_present else "not_configured",
        "postgres_dsn": "configured" if postgres_dsn_present else "not_configured",
        "internal_service_key": "configured" if internal_service_key_configured() else "not_configured",
        "neo4j_uri": "configured" if os.getenv("NEO4J_URI") else "not_configured",
    }
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "runtime": {"telemetry": telemetry_snapshot()},
    }

# --- DIAGNOSTIC & LESSON GENERATION ---

@app.post("/diagnostic/generate", response_model=DiagnosticGenerateResponse, dependencies=[Depends(verify_internal_key)])
async def diagnostic_generate(payload: DiagnosticGenerateRequest):
    try:
        questions = await generate_pedagogical_questions(
            subject=payload.subject,
            level=payload.sss_level,
            concepts=payload.concepts
        )
        return DiagnosticGenerateResponse(questions=questions)
    except Exception as exc:
        logger.error(f"Diagnostic generation failed: {exc}")
        raise HTTPException(status_code=500, detail="Failed to generate pedagogical questions")

@app.post("/lesson/generate", response_model=LessonGenerateResponse, dependencies=[Depends(verify_internal_key)])
async def ai_lesson_generate(payload: LessonGenerateRequest):
    try:
        content = await generate_lesson_content(payload.model_dump())
        return content
    except Exception as exc:
        logger.error(f"Lesson generation failed: {exc}")
        raise HTTPException(status_code=500, detail="Failed to generate lesson content")

# --- QUIZ ROUTES ---

@app.post("/quiz/generate", response_model=QuizGenerateResponse, dependencies=[Depends(verify_internal_key)])
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
        questions = [QuestionSchema(**q) for q in questions_raw]
        return QuizGenerateResponse(questions=questions)
    except QuizGenerationError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

@app.get("/quiz/{quiz_id}/attempt/{attempt_id}/insights", response_model=QuizInsightsResponse, dependencies=[Depends(verify_internal_key)])
async def quiz_insights(quiz_id: UUID, attempt_id: UUID):
    insights = await generate_quiz_insights(quiz_id=quiz_id, attempt_id=attempt_id)
    return QuizInsightsResponse(insights=insights)

# --- TUTOR ROUTES (Now Secured & Async) ---
# CRITICAL: We changed these to `async def` and added `await` to prevent blocking the Render thread.

@app.post("/tutor/chat", response_model=TutorChatResponse, dependencies=[Depends(verify_internal_key)])
async def tutor_chat(payload: TutorChatRequest):
    return await run_tutor_chat(payload)

@app.post("/tutor/recap", response_model=TutorChatResponse, dependencies=[Depends(verify_internal_key)])
async def tutor_recap(payload: TutorRecapRequest):
    return await run_tutor_recap(payload)

@app.post("/tutor/drill", response_model=TutorChatResponse, dependencies=[Depends(verify_internal_key)])
async def tutor_drill(payload: TutorDrillRequest):
    return await run_tutor_drill(payload)

@app.post("/tutor/hint", response_model=TutorHintResponse, dependencies=[Depends(verify_internal_key)])
async def tutor_hint(payload: TutorHintRequest):
    return await run_tutor_hint(payload)

@app.post("/tutor/explain-mistake", response_model=TutorExplainMistakeResponse, dependencies=[Depends(verify_internal_key)])
async def tutor_explain_mistake(payload: TutorExplainMistakeRequest):
    return await run_tutor_explain_mistake(payload)

@app.post("/tutor/prereq-bridge", response_model=TutorChatResponse, dependencies=[Depends(verify_internal_key)])
async def tutor_prereq_bridge(payload: TutorPrereqBridgeRequest):
    return await run_tutor_prereq_bridge(payload)

@app.post("/tutor/study-plan", response_model=TutorChatResponse, dependencies=[Depends(verify_internal_key)])
async def tutor_study_plan(payload: TutorStudyPlanRequest):
    return await run_tutor_study_plan(payload)

@app.post("/tutor/assessment/start", response_model=TutorAssessmentStartResponse, dependencies=[Depends(verify_internal_key)])
async def tutor_assessment_start(payload: TutorAssessmentStartRequest):
    return await run_tutor_assessment_start(payload)

@app.post("/tutor/assessment/submit", response_model=TutorAssessmentSubmitResponse, dependencies=[Depends(verify_internal_key)])
async def tutor_assessment_submit(payload: TutorAssessmentSubmitRequest):
    return await run_tutor_assessment_submit(payload)