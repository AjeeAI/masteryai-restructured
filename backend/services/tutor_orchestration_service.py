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
        # Point this to your new AI Core Render URL (e.g., https://ai-core.onrender.com)
        self.base_url = settings.ai_core_base_url.rstrip("/")
        self.timeout = 60.0  # AI can take time to think
        self.allow_fallback = bool(settings.ai_core_allow_fallback)

    async def _post(self, endpoint: str, payload: dict) -> dict:
        """Internal helper to communicate with the remote AI Core service."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                headers = {"X-Internal-Service-Key": settings.internal_service_key}
                response = await client.post(
                    f"{self.base_url}{endpoint}",
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"AI Core request failed at {endpoint}: {str(e)}")
                raise TutorProviderUnavailableError(f"Remote AI Engine error: {e}")

    async def chat(self, payload: TutorChatIn) -> TutorChatOut:
        # Map Backend Schema to AI Core Request Schema
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
        try:
            data = await self._post("/tutor/chat", ai_payload)
            return TutorChatOut.model_validate(data)
        except Exception as e:
            logger.warning(f"Tutor chat fallback triggered: {e}")
            return self._fallback_chat(payload)

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
        try:
            data = await self._post("/tutor/hint", ai_payload)
            return TutorHintOut.model_validate(data)
        except Exception:
            return self._fallback_hint(payload)

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
        try:
            data = await self._post("/tutor/explain-mistake", ai_payload)
            return TutorExplainMistakeOut.model_validate(data)
        except Exception:
            return self._fallback_explain(payload)

    # --- Section 5 & 7 Remote Endpoints ---

    async def recap(self, payload: TutorRecapIn) -> TutorChatOut:
        try:
            data = await self._post("/tutor/recap", payload.model_dump())
            return TutorChatOut.model_validate(data)
        except Exception:
            return self._fallback_chat(payload)

    async def drill(self, payload: TutorDrillIn) -> TutorChatOut:
        try:
            data = await self._post("/tutor/drill", payload.model_dump())
            return TutorChatOut.model_validate(data)
        except Exception:
            return self._fallback_chat(payload)

    async def prereq_bridge(self, payload: TutorPrereqBridgeIn) -> TutorChatOut:
        try:
            data = await self._post("/tutor/prereq-bridge", payload.model_dump())
            return TutorChatOut.model_validate(data)
        except Exception:
            return self._fallback_chat(payload)

    async def study_plan(self, payload: TutorStudyPlanIn) -> TutorChatOut:
        try:
            data = await self._post("/tutor/study-plan", payload.model_dump())
            return TutorChatOut.model_validate(data)
        except Exception:
            return self._fallback_chat(payload)

    # --- FALLBACK METHODS ---

    def _fallback_chat(self, payload: TutorChatIn) -> TutorChatOut:
        return TutorChatOut(
            assistant_message=(
                "I'm having a bit of trouble connecting to my brain right now. "
                f"Let's stay focused on {payload.subject.upper()} while I reconnect."
            ),
            citations=[],
            actions=["FALLBACK_MODE"],
            recommendations=[],
            mode="teach",
            key_points=["Review your current lesson materials."],
            next_action="Try refreshing the page or sending another message in a moment."
        )

    def _fallback_hint(self, payload: TutorHintIn) -> TutorHintOut:
        return TutorHintOut(hint="Try breaking the problem down into smaller steps.", strategy="fallback")

    def _fallback_explain(self, payload: TutorExplainMistakeIn) -> TutorExplainMistakeOut:
        return TutorExplainMistakeOut(
            explanation="I'm having trouble analyzing this mistake right now. Re-read the core rule for this topic.",
            improvement_tip="Check the lesson examples again."
        )