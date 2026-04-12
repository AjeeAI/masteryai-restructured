"""Tutor AI endpoints.

Public endpoints for tutor chat and guided assistance modes:
- chat
- session bootstrap
- hint
- explain mistake
"""

import asyncio
import json
import logging
import time
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.core.telemetry import log_timed_event
from backend.repositories.tutor_session_repo import TutorSessionRepository
from backend.schemas.tutor_schema import (
    TutorAssessmentStartIn,
    TutorAssessmentStartOut,
    TutorAssessmentSubmitIn,
    TutorAssessmentSubmitOut,
    TutorChatIn,
    TutorChatOut,
    TutorDrillIn,
    TutorExplainMistakeIn,
    TutorExplainMistakeOut,
    TutorHintIn,
    TutorHintOut,
    TutorPrereqBridgeIn,
    TutorRecapIn,
    TutorSessionBootstrapIn,
    TutorSessionBootstrapOut,
    TutorStudyPlanIn,
)
from backend.services.lesson_experience_service import LessonExperienceService
from backend.services.lesson_cockpit_service import LessonCockpitService
from backend.services.prewarm_job_service import PrewarmJobService
from backend.services.tutor_action_cache import TutorActionCacheKey, get_cached_action, set_cached_action
from backend.services.tutor_action_prewarm_service import TutorActionPrewarmService
from backend.services.tutor_assessment_service import TutorAssessmentService
from backend.services.tutor_orchestration_service import (
    TutorOrchestrationService,
    TutorProviderUnavailableError,
)

router = APIRouter(prefix="/tutor", tags=["Tutor AI"])
logger = logging.getLogger(__name__)


def _service() -> TutorOrchestrationService:
    return TutorOrchestrationService()


def _session_repo(db: Session) -> TutorSessionRepository:
    return TutorSessionRepository(db)


def _assessment_service(db: Session) -> TutorAssessmentService:
    return TutorAssessmentService(db)


def _lesson_experience_service(db: Session) -> LessonExperienceService:
    return LessonExperienceService(db)


@router.post("/session/bootstrap", response_model=TutorSessionBootstrapOut, status_code=status.HTTP_200_OK)
async def tutor_session_bootstrap( # Turned into async def
    payload: TutorSessionBootstrapIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    started_at = time.perf_counter()
    if payload.student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="student_id must match authenticated user id",
        )
    try:
        # CRITICAL: Added 'await' here because lesson generation is now remote
        response = await _lesson_experience_service(db).bootstrap(payload)
        
        warm_topic_ids: list[UUID] = []
        if response.next_unlock and response.next_unlock.topic_id:
            try:
                warm_topic_ids.append(UUID(str(response.next_unlock.topic_id)))
            except Exception:
                pass
        
        weak_prereq_topic_id = next(
            (item.topic_id for item in response.graph_context.prerequisite_concepts if item.topic_id),
            None,
        )
        if weak_prereq_topic_id:
            try:
                warm_topic_ids.append(UUID(str(weak_prereq_topic_id)))
            except Exception:
                pass
        
        if warm_topic_ids:
            background_tasks.add_task(
                PrewarmJobService.enqueue_lesson_related_job,
                student_id=payload.student_id,
                subject=payload.subject,
                sss_level=payload.sss_level,
                term=int(payload.term),
                topic_ids=warm_topic_ids,
            )
        
        background_tasks.add_task(
            TutorActionPrewarmService.prewarm,
            student_id=payload.student_id,
            session_id=response.session_id,
            subject=payload.subject,
            sss_level=payload.sss_level,
            term=int(payload.term),
            topic_id=payload.topic_id,
        )
        
        log_timed_event(
            logger,
            "tutor.session.bootstrap",
            started_at,
            outcome="success",
            student_id=payload.student_id,
            session_id=response.session_id,
            topic_id=payload.topic_id,
            session_started=response.session_started,
            graph_nodes=len(list(response.graph_nodes or [])),
        )
        return response
    except TutorProviderUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/chat", response_model=TutorChatOut, status_code=status.HTTP_200_OK)
async def tutor_chat(
    payload: TutorChatIn,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if payload.student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="student_id must match authenticated user id",
        )

    repo = _session_repo(db)
    if not repo.session_exists_for_student(session_id=payload.session_id, student_id=payload.student_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found for this student.")

    repo.add_message(session_id=payload.session_id, role="student", content=payload.message)
    started_at = time.perf_counter()

    try:
        response = await _service().chat(payload)
    except TutorProviderUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    assistant_message = (
        response.assistant_message
        if hasattr(response, "assistant_message")
        else str(response.get("assistant_message", ""))
    )
    citations = list(response.citations or []) if hasattr(response, "citations") else list(response.get("citations") or [])
    actions = list(response.actions or []) if hasattr(response, "actions") else list(response.get("actions") or [])
    
    repo.add_message(session_id=payload.session_id, role="assistant", content=assistant_message)
    
    log_timed_event(
        logger,
        "tutor.chat",
        started_at,
        outcome="success",
        student_id=payload.student_id,
        session_id=payload.session_id,
        topic_id=payload.topic_id,
        citations=len(citations),
        actions=len(actions),
    )
    return response


@router.post("/chat/stream", status_code=status.HTTP_200_OK)
async def tutor_chat_stream(
    payload: TutorChatIn,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if payload.student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="student_id must match authenticated user id",
        )

    repo = _session_repo(db)
    if not repo.session_exists_for_student(session_id=payload.session_id, student_id=payload.student_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found for this student.")

    repo.add_message(session_id=payload.session_id, role="student", content=payload.message)
    started_at = time.perf_counter()

    async def event_stream():
        yield "event: status\ndata: " + json.dumps({"phase": "retrieving_context"}) + "\n\n"
        try:
            response = await _service().chat(payload)
        except TutorProviderUnavailableError as exc:
            yield "event: error\ndata: " + json.dumps({"detail": str(exc)}) + "\n\n"
            return

        assistant_message = (
            response.assistant_message
            if hasattr(response, "assistant_message")
            else str(response.get("assistant_message", ""))
        )
        citations = list(response.citations or []) if hasattr(response, "citations") else list(response.get("citations") or [])
        actions = list(response.actions or []) if hasattr(response, "actions") else list(response.get("actions") or [])
        repo.add_message(session_id=payload.session_id, role="assistant", content=assistant_message)
        
        log_timed_event(
            logger,
            "tutor.chat.stream",
            started_at,
            outcome="success",
            student_id=payload.student_id,
            session_id=payload.session_id,
            topic_id=payload.topic_id,
            citations=len(citations),
            actions=len(actions),
        )
        yield "event: status\ndata: " + json.dumps({"phase": "composing_response"}) + "\n\n"
        for offset in range(0, len(assistant_message or ""), 120):
            chunk = (assistant_message or "")[offset : offset + 120]
            if chunk:
                yield "event: delta\ndata: " + json.dumps({"content": chunk}) + "\n\n"
                await asyncio.sleep(0)
        yield "event: status\ndata: " + json.dumps({"phase": "finalizing_response"}) + "\n\n"
        yield "event: message\ndata: " + json.dumps(response.model_dump()) + "\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/assessment/start", response_model=TutorAssessmentStartOut, status_code=status.HTTP_200_OK)
async def tutor_assessment_start(
    payload: TutorAssessmentStartIn,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if payload.student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="student_id must match authenticated user id",
        )

    repo = _session_repo(db)
    if not repo.session_exists_for_student(session_id=payload.session_id, student_id=payload.student_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found for this student.")

    try:
        # Assuming assessment service was also made async
        response = await _assessment_service(db).start_assessment(payload)
        LessonExperienceService.invalidate_session_cache(session_id=payload.session_id)
        LessonCockpitService.invalidate_session_cache(session_id=payload.session_id)
        return response
    except TutorProviderUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))


@router.post("/assessment/submit", response_model=TutorAssessmentSubmitOut, status_code=status.HTTP_200_OK)
async def tutor_assessment_submit(
    payload: TutorAssessmentSubmitIn,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if payload.student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="student_id must match authenticated user id",
        )

    repo = _session_repo(db)
    if not repo.session_exists_for_student(session_id=payload.session_id, student_id=payload.student_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found for this student.")

    try:
        # Assuming assessment service was also made async
        response = await _assessment_service(db).submit_assessment(payload)
        LessonExperienceService.invalidate_session_cache(session_id=payload.session_id)
        LessonCockpitService.invalidate_session_cache(session_id=payload.session_id)
        return response
    except TutorProviderUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))


@router.post("/recap", response_model=TutorChatOut, status_code=status.HTTP_200_OK)
async def tutor_recap(
    payload: TutorRecapIn,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    started_at = time.perf_counter()
    if payload.student_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="student_id must match authenticated user id")
    repo = _session_repo(db)
    if not repo.session_exists_for_student(session_id=payload.session_id, student_id=payload.student_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found for this student.")
    
    cache_key = TutorActionCacheKey(action_id="recap", session_id=payload.session_id, topic_id=payload.topic_id)
    cached = get_cached_action(cache_key)
    if cached is not None:
        return cached

    try:
        response = await _service().recap(payload)
        set_cached_action(cache_key, response)
        return response
    except TutorProviderUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))


@router.post("/drill", response_model=TutorChatOut, status_code=status.HTTP_200_OK)
async def tutor_drill(
    payload: TutorDrillIn,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    started_at = time.perf_counter()
    if payload.student_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="student_id must match authenticated user id")
    repo = _session_repo(db)
    if not repo.session_exists_for_student(session_id=payload.session_id, student_id=payload.student_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found for this student.")
    
    cache_key = TutorActionCacheKey(action_id="drill", session_id=payload.session_id, topic_id=payload.topic_id, difficulty=payload.difficulty)
    cached = get_cached_action(cache_key)
    if cached is not None:
        return cached

    try:
        response = await _service().drill(payload)
        set_cached_action(cache_key, response)
        return response
    except TutorProviderUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))


@router.post("/prereq-bridge", response_model=TutorChatOut, status_code=status.HTTP_200_OK)
async def tutor_prereq_bridge(
    payload: TutorPrereqBridgeIn,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    started_at = time.perf_counter()
    if payload.student_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="student_id must match authenticated user id")
    repo = _session_repo(db)
    if not repo.session_exists_for_student(session_id=payload.session_id, student_id=payload.student_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found for this student.")
    
    cache_key = TutorActionCacheKey(action_id="prereq-bridge", session_id=payload.session_id, topic_id=payload.topic_id)
    cached = get_cached_action(cache_key)
    if cached is not None:
        return cached

    try:
        response = await _service().prereq_bridge(payload)
        set_cached_action(cache_key, response)
        return response
    except TutorProviderUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))


@router.post("/study-plan", response_model=TutorChatOut, status_code=status.HTTP_200_OK)
async def tutor_study_plan(
    payload: TutorStudyPlanIn,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    started_at = time.perf_counter()
    if payload.student_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="student_id must match authenticated user id")
    repo = _session_repo(db)
    if not repo.session_exists_for_student(session_id=payload.session_id, student_id=payload.student_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found for this student.")
    
    try:
        response = await _service().study_plan(payload)
        return response
    except TutorProviderUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))


@router.post("/hint", response_model=TutorHintOut, status_code=status.HTTP_200_OK)
async def tutor_hint(
    payload: TutorHintIn,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    started_at = time.perf_counter()
    if payload.student_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="student_id must match authenticated user id")

    if payload.session_id is not None:
        repo = _session_repo(db)
        if not repo.session_exists_for_student(session_id=payload.session_id, student_id=payload.student_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found for this student.")

    try:
        response = await _service().hint(payload)
        return response
    except TutorProviderUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))


@router.post("/explain-mistake", response_model=TutorExplainMistakeOut, status_code=status.HTTP_200_OK)
async def tutor_explain_mistake(
    payload: TutorExplainMistakeIn,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    started_at = time.perf_counter()
    if payload.student_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="student_id must match authenticated user id")

    if payload.session_id is not None:
        repo = _session_repo(db)
        if not repo.session_exists_for_student(session_id=payload.session_id, student_id=payload.student_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found for this student.")

    try:
        response = await _service().explain_mistake(payload)
        return response
    except TutorProviderUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))