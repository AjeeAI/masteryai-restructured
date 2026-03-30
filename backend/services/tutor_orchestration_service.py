from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx

from backend.core.config import settings
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
    TutorRecommendationOut,
    TutorStudyPlanIn,
)


class TutorOrchestrationError(RuntimeError):
    """Base exception for tutor orchestration failures."""


class TutorProviderUnavailableError(TutorOrchestrationError):
    """Raised when ai-core is unavailable and fallback is disabled."""


class TutorProviderContractError(TutorOrchestrationError):
    """Raised when ai-core response violates expected contract."""


class TutorOrchestrationService:
    def __init__(self):
        self.base_url = settings.ai_core_base_url.rstrip("/")
        self.timeout_seconds = max(float(settings.ai_core_timeout_seconds), 1.0)
        self.allow_fallback = bool(settings.ai_core_allow_fallback)

    @staticmethod
    def _fallback_chat(payload: TutorChatIn) -> TutorChatOut:
        recommendation = TutorRecommendationOut(
            type="next_topic",
            topic_id=str(payload.topic_id) if payload.topic_id else None,
            reason="Continue practicing this scope while mastery evidence is still building.",
        )
        return TutorChatOut(
            assistant_message=(
                "Tutor provider unavailable right now. "
                f"Stay on {payload.subject.upper()} ({payload.sss_level}, term {payload.term}) and focus on one concrete example before moving on."
            ),
            citations=[],
            actions=["FALLBACK_GUIDANCE_ONLY"],
            recommendations=[recommendation],
            mode="teach",
            key_points=["Use one worked example before trying a harder question."],
            concept_focus=[payload.focus_concept_label] if payload.focus_concept_label else [],
            next_action="Try the lesson checkpoint or ask for one simpler example.",
        )

    @staticmethod
    def _fallback_assessment_start(payload: TutorAssessmentStartIn) -> TutorAssessmentStartOut:
        if not payload.focus_concept_id:
            raise TutorProviderUnavailableError(
                "Tutor assessment fallback requires a concrete graph-selected focus concept."
            )
        return TutorAssessmentStartOut(
            assessment_id=UUID("00000000-0000-0000-0000-000000000000"),
            question=(
                f"Briefly explain one key idea you have learned in {payload.subject.upper()} "
                f"({payload.sss_level} term {payload.term})."
            ),
            concept_id=payload.focus_concept_id,
            concept_label=payload.focus_concept_label or "selected lesson concept",
            ideal_answer="State the rule clearly and give one correct example from the lesson.",
            hint="State the main rule first, then give one example.",
            citations=[],
            actions=["ASSESSMENT_FALLBACK"],
        )

    @staticmethod
    def _fallback_assessment_submit(
        payload: TutorAssessmentSubmitIn,
        *,
        concept_id: str,
        concept_label: str,
    ) -> TutorAssessmentSubmitOut:
        return TutorAssessmentSubmitOut(
            assessment_id=payload.assessment_id,
            is_correct=False,
            score=0.0,
            feedback="Assessment provider unavailable. No mastery update was applied.",
            ideal_answer="",
            concept_id=concept_id,
            concept_label=concept_label,
            mastery_updated=False,
            new_mastery=None,
            actions=["ASSESSMENT_FALLBACK"],
        )

    @staticmethod
    def _fallback_hint(payload: TutorHintIn) -> TutorHintOut:
        return TutorHintOut(
            hint="Break the question into smaller parts and eliminate clearly wrong options first.",
            strategy="guided_hint",
        )

    @staticmethod
    def _fallback_explain(payload: TutorExplainMistakeIn) -> TutorExplainMistakeOut:
        return TutorExplainMistakeOut(
            explanation=(
                "Your answer likely missed the core rule used in this question. "
                f"The expected answer is '{payload.correct_answer}', while you selected '{payload.student_answer}'."
            ),
            improvement_tip="State the governing rule first, then re-check each option against that rule.",
        )

    @staticmethod
    def _fallback_mode_response(*, message: str, action: str, topic_id: str | None) -> TutorChatOut:
        return TutorChatOut(
            assistant_message=message,
            citations=[],
            actions=[action, "FALLBACK_GUIDANCE_ONLY"],
            recommendations=[
                TutorRecommendationOut(
                    type="next_topic",
                    topic_id=topic_id,
                    reason="Stay on the active topic and complete one focused checkpoint before moving on.",
                )
            ],
            key_points=["Use the lesson content and active graph hints to keep your revision focused."],
            next_action="Ask the tutor for a checkpoint question or recap this lesson in three points.",
        )

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.base_url:
            raise TutorProviderUnavailableError("AI_CORE_BASE_URL is not configured.")

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(f"{self.base_url}{path}", json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            detail = (exc.response.text or "").strip()
            raise TutorProviderUnavailableError(
                f"ai-core request failed ({exc.response.status_code}) on {path}: "
                f"{detail[:400] or 'empty response body'}"
            ) from exc
        except httpx.RequestError as exc:
            raise TutorProviderUnavailableError(f"ai-core request failed: {exc}") from exc
        except httpx.HTTPError as exc:
            raise TutorProviderUnavailableError(f"ai-core request failed: {exc}") from exc

        if not isinstance(data, dict):
            raise TutorProviderContractError("ai-core response must be an object.")
        return data

    async def chat(self, payload: TutorChatIn) -> TutorChatOut:
        request_payload = {
            "student_id": str(payload.student_id),
            "session_id": str(payload.session_id),
            "subject": payload.subject,
            "sss_level": payload.sss_level,
            "term": payload.term,
            "topic_id": str(payload.topic_id) if payload.topic_id else None,
            "focus_concept_id": payload.focus_concept_id,
            "focus_concept_label": payload.focus_concept_label,
            "mode": payload.mode,
            "message": payload.message,
        }

        try:
            data = await self._post("/tutor/chat", request_payload)
            return TutorChatOut.model_validate(data)
        except (TutorProviderUnavailableError, TutorProviderContractError):
            if not self.allow_fallback:
                raise
            return self._fallback_chat(payload)

    async def assessment_start(self, payload: TutorAssessmentStartIn) -> TutorAssessmentStartOut:
        request_payload = {
            "student_id": str(payload.student_id),
            "session_id": str(payload.session_id),
            "subject": payload.subject,
            "sss_level": payload.sss_level,
            "term": payload.term,
            "topic_id": str(payload.topic_id),
            "focus_concept_id": payload.focus_concept_id,
            "focus_concept_label": payload.focus_concept_label,
            "difficulty": payload.difficulty,
        }

        try:
            data = await self._post("/tutor/assessment/start", request_payload)
            return TutorAssessmentStartOut.model_validate(
                {
                    **data,
                    "assessment_id": UUID("00000000-0000-0000-0000-000000000000"),
                }
            )
        except (TutorProviderUnavailableError, TutorProviderContractError):
            if not self.allow_fallback:
                raise
            return self._fallback_assessment_start(payload)

    async def assessment_submit(
        self,
        payload: TutorAssessmentSubmitIn,
        *,
        question: str,
        concept_id: str,
        concept_label: str,
        ideal_answer: str,
    ) -> TutorAssessmentSubmitOut:
        request_payload = {
            "student_id": str(payload.student_id),
            "session_id": str(payload.session_id),
            "assessment_id": str(payload.assessment_id),
            "subject": payload.subject,
            "sss_level": payload.sss_level,
            "term": payload.term,
            "topic_id": str(payload.topic_id),
            "answer": payload.answer,
            "question": question,
            "concept_id": concept_id,
            "concept_label": concept_label,
            "ideal_answer": ideal_answer,
        }

        try:
            data = await self._post("/tutor/assessment/submit", request_payload)
            return TutorAssessmentSubmitOut.model_validate(
                {
                    **data,
                    "assessment_id": payload.assessment_id,
                    "mastery_updated": False,
                    "new_mastery": None,
                }
            )
        except (TutorProviderUnavailableError, TutorProviderContractError):
            if not self.allow_fallback:
                raise
            return self._fallback_assessment_submit(
                payload,
                concept_id=concept_id,
                concept_label=concept_label,
            )

    async def hint(self, payload: TutorHintIn) -> TutorHintOut:
        request_payload = {
            "student_id": str(payload.student_id),
            "session_id": str(payload.session_id) if payload.session_id else None,
            "quiz_id": str(payload.quiz_id),
            "question_id": payload.question_id,
            "subject": payload.subject,
            "sss_level": payload.sss_level,
            "term": payload.term,
            "topic_id": str(payload.topic_id) if payload.topic_id else None,
            "message": payload.message,
        }

        try:
            data = await self._post("/tutor/hint", request_payload)
            return TutorHintOut.model_validate(data)
        except (TutorProviderUnavailableError, TutorProviderContractError):
            if not self.allow_fallback:
                raise
            return self._fallback_hint(payload)

    async def recap(self, payload: TutorRecapIn) -> TutorChatOut:
        request_payload = {
            "student_id": str(payload.student_id),
            "session_id": str(payload.session_id),
            "subject": payload.subject,
            "sss_level": payload.sss_level,
            "term": payload.term,
            "topic_id": str(payload.topic_id),
        }
        try:
            data = await self._post("/tutor/recap", request_payload)
            return TutorChatOut.model_validate(data)
        except (TutorProviderUnavailableError, TutorProviderContractError):
            if not self.allow_fallback:
                raise
            return self._fallback_mode_response(
                message="Recap unavailable right now. Re-read the summary, then state the topic in three short points from memory.",
                action="RECAP_FALLBACK",
                topic_id=str(payload.topic_id),
            )

    async def drill(self, payload: TutorDrillIn) -> TutorChatOut:
        request_payload = {
            "student_id": str(payload.student_id),
            "session_id": str(payload.session_id),
            "subject": payload.subject,
            "sss_level": payload.sss_level,
            "term": payload.term,
            "topic_id": str(payload.topic_id),
            "difficulty": payload.difficulty,
        }
        try:
            data = await self._post("/tutor/drill", request_payload)
            return TutorChatOut.model_validate(data)
        except (TutorProviderUnavailableError, TutorProviderContractError):
            if not self.allow_fallback:
                raise
            return self._fallback_mode_response(
                message="Drill mode is unavailable right now. Write one short answer to the lesson's main concept and self-check it against the worked example.",
                action="DRILL_FALLBACK",
                topic_id=str(payload.topic_id),
            )

    async def prereq_bridge(self, payload: TutorPrereqBridgeIn) -> TutorChatOut:
        request_payload = {
            "student_id": str(payload.student_id),
            "session_id": str(payload.session_id),
            "subject": payload.subject,
            "sss_level": payload.sss_level,
            "term": payload.term,
            "topic_id": str(payload.topic_id),
        }
        try:
            data = await self._post("/tutor/prereq-bridge", request_payload)
            return TutorChatOut.model_validate(data)
        except (TutorProviderUnavailableError, TutorProviderContractError):
            if not self.allow_fallback:
                raise
            return self._fallback_mode_response(
                message="Prerequisite bridge is unavailable right now. Step back to the foundational rule that feeds this lesson and explain it in your own words.",
                action="PREREQ_BRIDGE_FALLBACK",
                topic_id=str(payload.topic_id),
            )

    async def study_plan(self, payload: TutorStudyPlanIn) -> TutorChatOut:
        request_payload = {
            "student_id": str(payload.student_id),
            "session_id": str(payload.session_id),
            "subject": payload.subject,
            "sss_level": payload.sss_level,
            "term": payload.term,
            "topic_id": str(payload.topic_id),
            "horizon_days": payload.horizon_days,
        }
        try:
            data = await self._post("/tutor/study-plan", request_payload)
            return TutorChatOut.model_validate(data)
        except (TutorProviderUnavailableError, TutorProviderContractError):
            if not self.allow_fallback:
                raise
            return self._fallback_mode_response(
                message="Study-plan generation is unavailable right now. Do one recap, one checkpoint, and one revision quiz on this topic over the next two days.",
                action="STUDY_PLAN_FALLBACK",
                topic_id=str(payload.topic_id),
            )

    async def explain_mistake(self, payload: TutorExplainMistakeIn) -> TutorExplainMistakeOut:
        request_payload = {
            "student_id": str(payload.student_id),
            "session_id": str(payload.session_id) if payload.session_id else None,
            "subject": payload.subject,
            "sss_level": payload.sss_level,
            "term": payload.term,
            "topic_id": str(payload.topic_id) if payload.topic_id else None,
            "question": payload.question,
            "student_answer": payload.student_answer,
            "correct_answer": payload.correct_answer,
        }

        try:
            data = await self._post("/tutor/explain-mistake", request_payload)
            return TutorExplainMistakeOut.model_validate(data)
        except (TutorProviderUnavailableError, TutorProviderContractError):
            if not self.allow_fallback:
                raise
            return self._fallback_explain(payload)
