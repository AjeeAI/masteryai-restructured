from __future__ import annotations

import logging
from uuid import UUID
from typing import Any

# Import the actual AI logic directly from your ai_core folder
from ai_core.tutor_engine import (
    run_tutor_chat, 
    run_tutor_hint, 
    run_tutor_explain_mistake,
    run_tutor_recap,
    run_tutor_drill,
    run_tutor_prereq_bridge,
    run_tutor_study_plan
)

# Import the AI Core internal schemas (Contracts)
from ai_core.core_engine.api_contracts.schemas import (
    TutorChatRequest, 
    TutorHintRequest, 
    TutorExplainMistakeRequest,
    TutorRecapRequest,
    TutorDrillRequest,
    TutorPrereqBridgeRequest,
    TutorStudyPlanRequest
)

from backend.core.config import settings
from backend.schemas.tutor_schema import (
    TutorChatIn, TutorChatOut,
    TutorHintIn, TutorHintOut,
    TutorExplainMistakeIn, TutorExplainMistakeOut,
    TutorRecapIn, TutorDrillIn,
    TutorPrereqBridgeIn, TutorStudyPlanIn,
    TutorRecommendationOut
)

logger = logging.getLogger(__name__)

class TutorOrchestrationService:
    def __init__(self):
        # We keep this for backward compatibility, but we are bypassing the network
        self.allow_fallback = bool(settings.ai_core_allow_fallback)

    async def chat(self, payload: TutorChatIn) -> TutorChatOut:
        """Directly calls the AI Tutor engine without a network loop."""
        ai_request = TutorChatRequest(
            student_id=str(payload.student_id),
            session_id=str(payload.session_id),
            subject=payload.subject,
            sss_level=payload.sss_level,
            term=int(payload.term),
            topic_id=str(payload.topic_id) if payload.topic_id else None,
            message=payload.message,
            mode=payload.mode,
            focus_concept_id=payload.focus_concept_id,
            focus_concept_label=payload.focus_concept_label
        )

        try:
            # CALL DIRECTLY: No httpx, no 127.0.0.1, no deadlock.
            response_data = run_tutor_chat(ai_request)
            return TutorChatOut.model_validate(response_data.model_dump())
        except Exception as e:
            logger.error(f"Tutor Orchestration Chat Failed: {str(e)}")
            if not self.allow_fallback:
                raise
            return self._fallback_chat(payload)

    async def hint(self, payload: TutorHintIn) -> TutorHintOut:
        ai_request = TutorHintRequest(
            student_id=str(payload.student_id),
            quiz_id=str(payload.quiz_id),
            question_id=payload.question_id,
            subject=payload.subject,
            sss_level=payload.sss_level,
            term=int(payload.term),
            message=payload.message
        )
        try:
            response_data = run_tutor_hint(ai_request)
            return TutorHintOut.model_validate(response_data.model_dump())
        except Exception:
            return self._fallback_hint(payload)

    async def explain_mistake(self, payload: TutorExplainMistakeIn) -> TutorExplainMistakeOut:
        ai_request = TutorExplainMistakeRequest(
            student_id=str(payload.student_id),
            subject=payload.subject,
            sss_level=payload.sss_level,
            term=int(payload.term),
            question=payload.question,
            student_answer=payload.student_answer,
            correct_answer=payload.correct_answer
        )
        try:
            response_data = run_tutor_explain_mistake(ai_request)
            return TutorExplainMistakeOut.model_validate(response_data.model_dump())
        except Exception:
            return self._fallback_explain(payload)

    # --- FALLBACK METHODS (Keep these for UI safety) ---

    @staticmethod
    def _fallback_chat(payload: TutorChatIn) -> TutorChatOut:
        return TutorChatOut(
            assistant_message=(
                "I'm having a bit of trouble connecting to my brain right now. "
                f"Let's stay focused on {payload.subject.upper()} and try one more example."
            ),
            citations=[],
            actions=["FALLBACK_MODE"],
            recommendations=[],
            mode="teach",
            key_points=["Review the last section."],
            next_action="Try refreshing the lesson."
        )

    @staticmethod
    def _fallback_hint(payload: TutorHintIn) -> TutorHintOut:
        return TutorHintOut(hint="Try breaking the problem down.", strategy="fallback")

    @staticmethod
    def _fallback_explain(payload: TutorExplainMistakeIn) -> TutorExplainMistakeOut:
        return TutorExplainMistakeOut(explanation="Look for the main rule used in the lesson.", improvement_tip="Re-read the example.")