from __future__ import annotations

import logging
import httpx
from typing import Any
from backend.core.config import settings
from backend.schemas.tutor_schema import (
    TutorChatIn, TutorChatOut,
    TutorHintIn, TutorHintOut,
    TutorExplainMistakeIn, TutorExplainMistakeOut,
    TutorRecapIn, TutorDrillIn,
    TutorPrereqBridgeIn, TutorStudyPlanIn
)

logger = logging.getLogger(__name__)

class TutorProviderUnavailableError(Exception):
    """Exception raised when the remote AI Core service is unreachable."""
    pass

class TutorOrchestrationService:
    def __init__(self):
        # Point this to your AI Core Render URL
        self.base_url = settings.ai_core_base_url.rstrip("/")
        self.timeout = 60.0  # AI can take time to think

    async def _post(self, endpoint: str, payload: dict) -> dict:
        """Internal helper to communicate with the remote AI Core service."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            headers = {"X-Internal-Service-Key": settings.internal_service_key}
            
            response = await client.post(
                f"{self.base_url}{endpoint}",
                json=payload,
                headers=headers
            )
            
            # --- LOGGING: THE DEBUGGING X-RAY ---
            # This allows you to see the raw string before Pydantic validation kicks in.
            logger.info(f"TUTOR_ORCHESTRATOR_RAW_RESPONSE ({endpoint}): {response.text}")
            # ------------------------------------
            
            if response.status_code != 200:
                logger.error(f"AI CORE FAILURE ({response.status_code}): {response.text}")
                raise TutorProviderUnavailableError(f"Remote AI Engine error: {response.text}")
                
            return response.json()

    async def chat(self, payload: TutorChatIn) -> TutorChatOut:
        ai_payload = {
            "student_id": str(payload.student_id),
            "session_id": str(payload.session_id),
            "subject": payload.subject,
            "sss_level": payload.sss_level,
            "term": int(payload.term),
            "topic_id": str(payload.topic_id) if payload.topic_id else None,
            "message": payload.message,
            "mode": payload.mode,
            "focus_concept_id": payload.focus_concept_id,
            "focus_concept_label": payload.focus_concept_label
        }
        data = await self._post("/tutor/chat", ai_payload)
        return TutorChatOut.model_validate(data)

    async def hint(self, payload: TutorHintIn) -> TutorHintOut:
        ai_payload = {
            "student_id": str(payload.student_id),
            "quiz_id": str(payload.quiz_id),
            "question_id": payload.question_id,
            "subject": payload.subject,
            "sss_level": payload.sss_level,
            "term": int(payload.term),
            "message": payload.message
        }
        data = await self._post("/tutor/hint", ai_payload)
        return TutorHintOut.model_validate(data)

    async def explain_mistake(self, payload: TutorExplainMistakeIn) -> TutorExplainMistakeOut:
        ai_payload = {
            "student_id": str(payload.student_id),
            "subject": payload.subject,
            "sss_level": payload.sss_level,
            "term": int(payload.term),
            "question": payload.question,
            "student_answer": payload.student_answer,
            "correct_answer": payload.correct_answer
        }
        data = await self._post("/tutor/explain-mistake", ai_payload)
        return TutorExplainMistakeOut.model_validate(data)

    async def recap(self, payload: TutorRecapIn) -> TutorChatOut:
        data = await self._post("/tutor/recap", payload.model_dump())
        return TutorChatOut.model_validate(data)

    async def drill(self, payload: TutorDrillIn) -> TutorChatOut:
        data = await self._post("/tutor/drill", payload.model_dump())
        return TutorChatOut.model_validate(data)

    async def prereq_bridge(self, payload: TutorPrereqBridgeIn) -> TutorChatOut:
        data = await self._post("/tutor/prereq-bridge", payload.model_dump())
        return TutorChatOut.model_validate(data)

    async def study_plan(self, payload: TutorStudyPlanIn) -> TutorChatOut:
        data = await self._post("/tutor/study-plan", payload.model_dump())
        return TutorChatOut.model_validate(data)