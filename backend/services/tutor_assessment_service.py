from __future__ import annotations

import json
import re
import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.core.telemetry import log_timed_event, now_ms
from backend.repositories.activity_repo import ActivityRepository
from backend.repositories.quiz_repo import QuizRepository
from backend.repositories.tutor_session_repo import TutorSessionRepository
from backend.schemas.activity_schema import ActivityLogCreate
from backend.schemas.internal_graph_schema import ConceptUpdateIn, InternalGraphUpdateIn
from backend.schemas.learning_path_schema import PathNextIn
from backend.schemas.tutor_schema import (
    TutorAssessmentStartIn,
    TutorAssessmentStartOut,
    TutorGraphRemediationOut,
    TutorAssessmentSubmitIn,
    TutorAssessmentSubmitOut,
)
from backend.services.activity_service import ActivityService
from backend.services.lesson_graph_service import LessonGraphValidationError, lesson_graph_service
from backend.services.graph_client_service import GraphClientValidationError, graph_client_service
from backend.services.learning_path_service import learning_path_service
from backend.services.tutor_orchestration_service import (
    TutorOrchestrationService,
    TutorProviderUnavailableError,
)

_ASSESSMENT_PREFIX = "TUTOR_ASSESSMENT_STATE::"
logger = logging.getLogger(__name__)


class TutorAssessmentService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = TutorSessionRepository(db)
        self.quiz_repo = QuizRepository(db)
        self.orchestration = TutorOrchestrationService()
        self.activity_service = ActivityService(ActivityRepository(db))

    @staticmethod
    def _encode_state(payload: dict) -> str:
        return _ASSESSMENT_PREFIX + json.dumps(payload, ensure_ascii=True)

    @staticmethod
    def _decode_state(content: str) -> dict | None:
        value = str(content or "")
        if not value.startswith(_ASSESSMENT_PREFIX):
            return None
        try:
            parsed = json.loads(value[len(_ASSESSMENT_PREFIX) :])
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    def _find_pending_state(self, *, session_id: UUID, assessment_id: UUID) -> tuple[UUID, dict] | None:
        history = self.repo.get_session_history(session_id=session_id)
        for row in reversed(history):
            state = self._decode_state(str(row.get("content") or ""))
            if not state:
                continue
            if str(state.get("assessment_id") or "") != str(assessment_id):
                continue
            if str(state.get("status") or "").strip().lower() != "pending":
                continue
            return UUID(str(row["id"])), state
        return None

    def get_pending_assessment(self, *, session_id: UUID) -> dict | None:
        history = self.repo.get_session_history(session_id=session_id)
        for row in reversed(history):
            state = self._decode_state(str(row.get("content") or ""))
            if not state:
                continue
            if str(state.get("status") or "").strip().lower() != "pending":
                continue
            return state
        return None

    @staticmethod
    def _assessment_weight(score: float) -> tuple[bool, float]:
        if score >= 0.8:
            return True, 0.12
        if score >= 0.55:
            return True, 0.05
        return False, 0.04

    @staticmethod
    def _readable_concept_label(concept_id: str, *, fallback_topic_title: str | None = None) -> str:
        value = str(concept_id or "").strip()
        if not value:
            return str(fallback_topic_title or "Untitled Concept").strip()
        try:
            UUID(value)
            fallback = str(fallback_topic_title or "").strip()
            return fallback or "Topic Concept"
        except ValueError:
            pass

        token = value.rsplit(":", 1)[-1].strip()
        token = re.sub(r"-(\d+)$", "", token)
        token = re.sub(r"[_-]+", " ", token)
        token = re.sub(r"\s+", " ", token).strip()
        return token.title() if token else str(fallback_topic_title or "Untitled Concept").strip()

    def _recent_answered_states(self, *, session_id: UUID, limit: int = 6) -> list[dict]:
        history = self.repo.get_session_history(session_id=session_id)
        states: list[dict] = []
        for row in reversed(history):
            state = self._decode_state(str(row.get("content") or ""))
            if not state:
                continue
            if str(state.get("status") or "").strip().lower() != "answered":
                continue
            states.append(state)
            if len(states) >= limit:
                break
        return states

    @staticmethod
    def _concept_streak(states: list[dict], concept_id: str) -> tuple[int, int]:
        correct_streak = 0
        incorrect_streak = 0
        for state in states:
            if str(state.get("concept_id") or "") != str(concept_id):
                continue
            is_correct = bool(state.get("is_correct"))
            if is_correct:
                if incorrect_streak:
                    break
                correct_streak += 1
                continue
            if correct_streak:
                break
            incorrect_streak += 1
        return correct_streak, incorrect_streak

    def _graph_follow_up(
        self,
        *,
        payload: TutorAssessmentSubmitIn,
        focus_concept_id: str,
        fallback_topic_id: UUID | None,
    ) -> tuple[str | None, str | None, str | None, TutorGraphRemediationOut | None]:
        try:
            next_step = learning_path_service.calculate_next_step(
                db=self.db,
                payload=PathNextIn(
                    student_id=payload.student_id,
                    subject=payload.subject,
                    sss_level=payload.sss_level,
                    term=payload.term,
                ),
            )
        except Exception:
            return None, None, None, None

        prerequisite_warning = None
        if next_step.prereq_gaps:
            blocking_label = next_step.recommended_concept_label or "a blocking prerequisite"
            prerequisite_warning = (
                f"You are still blocked by {blocking_label}. Strengthen that prerequisite before pushing further."
            )
        blocking_prerequisite_id = next_step.prereq_gaps[0] if next_step.prereq_gaps else None
        blocking_prerequisite_topic_title = (
            self.quiz_repo.find_topic_title_for_concept(
                concept_id=blocking_prerequisite_id,
                subject=payload.subject,
                sss_level=payload.sss_level,
                term=int(payload.term),
            )
            if blocking_prerequisite_id
            else None
        )
        focus_topic_title = self.quiz_repo.find_topic_title_for_concept(
            concept_id=focus_concept_id,
            subject=payload.subject,
            sss_level=payload.sss_level,
            term=int(payload.term),
        ) or self.quiz_repo.get_topic_title(fallback_topic_id)
        remediation = TutorGraphRemediationOut(
            focus_concept_id=focus_concept_id,
            focus_concept_label=self._readable_concept_label(
                focus_concept_id,
                fallback_topic_title=focus_topic_title,
            ),
            blocking_prerequisite_id=blocking_prerequisite_id,
            blocking_prerequisite_label=(
                self._readable_concept_label(
                    blocking_prerequisite_id,
                    fallback_topic_title=blocking_prerequisite_topic_title,
                )
                if blocking_prerequisite_id
                else None
            ),
            blocking_prerequisite_topic_title=blocking_prerequisite_topic_title,
            recommended_next_concept_id=next_step.recommended_concept_id,
            recommended_next_concept_label=next_step.recommended_concept_label,
            recommended_next_topic_id=next_step.recommended_topic_id,
            recommended_next_topic_title=next_step.recommended_topic_title,
            recommendation_reason=next_step.reason,
        )
        return (
            prerequisite_warning,
            next_step.recommended_topic_id,
            next_step.recommended_topic_title or next_step.recommended_concept_label,
            remediation,
        )

    async def start_assessment(self, payload: TutorAssessmentStartIn) -> TutorAssessmentStartOut:
        started_at = now_ms()
        focus_concept_id = payload.focus_concept_id
        focus_concept_label = payload.focus_concept_label
        if not focus_concept_id:
            try:
                graph_context = lesson_graph_service.get_lesson_graph_context(
                    self.db,
                    student_id=payload.student_id,
                    subject=payload.subject,
                    sss_level=payload.sss_level,
                    term=int(payload.term),
                    topic_id=payload.topic_id,
                )
                current_nodes = list(graph_context.current_concepts or [])
                if current_nodes:
                    weakest = min(current_nodes, key=lambda item: float(item.mastery_score))
                    focus_concept_id = weakest.concept_id
                    focus_concept_label = weakest.label
            except LessonGraphValidationError:
                pass

        effective_payload = payload.model_copy(
            update={
                "focus_concept_id": focus_concept_id,
                "focus_concept_label": focus_concept_label,
            }
        )
        ai_out = await self.orchestration.assessment_start(effective_payload)
        assessment_id = uuid4()
        state = {
            "assessment_id": str(assessment_id),
            "topic_id": str(payload.topic_id),
            "concept_id": ai_out.concept_id,
            "concept_label": ai_out.concept_label,
            "requested_focus_concept_id": payload.focus_concept_id,
            "requested_focus_concept_label": payload.focus_concept_label,
            "selected_focus_concept_id": focus_concept_id,
            "selected_focus_concept_label": focus_concept_label,
            "question": ai_out.question,
            "ideal_answer": ai_out.ideal_answer,
            "hint": ai_out.hint,
            "difficulty": payload.difficulty,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.repo.add_message(
            session_id=payload.session_id,
            role="system",
            content=self._encode_state(state),
        )
        self.repo.add_message(
            session_id=payload.session_id,
            role="assistant",
            content=f"Check question: {ai_out.question}",
        )
        response = ai_out.model_copy(update={"assessment_id": assessment_id})
        log_timed_event(
            logger,
            "tutor.assessment.start",
            started_at,
            outcome="success",
            student_id=payload.student_id,
            session_id=payload.session_id,
            topic_id=payload.topic_id,
            focus_concept_id=focus_concept_id or response.concept_id,
            citations=len(list(response.citations or [])),
        )
        return response

    async def submit_assessment(self, payload: TutorAssessmentSubmitIn) -> TutorAssessmentSubmitOut:
        started_at = now_ms()
        match = self._find_pending_state(session_id=payload.session_id, assessment_id=payload.assessment_id)
        if match is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pending tutor assessment not found for this session.",
            )
        message_id, state = match

        self.repo.add_message(session_id=payload.session_id, role="student", content=payload.answer)
        ai_out = await self.orchestration.assessment_submit(
            payload,
            question=str(state.get("question") or ""),
            concept_id=str(state.get("concept_id") or ""),
            concept_label=str(state.get("concept_label") or ""),
            ideal_answer=str(state.get("ideal_answer") or ""),
        )

        is_positive, weight_change = self._assessment_weight(ai_out.score)
        mastery_updated = False
        new_mastery: float | None = None
        try:
            graph_out = graph_client_service.push_mastery_update(
                self.db,
                payload=InternalGraphUpdateIn(
                    student_id=payload.student_id,
                    quiz_id=None,
                    attempt_id=None,
                    subject=payload.subject,
                    sss_level=payload.sss_level,
                    term=payload.term,
                    timestamp=datetime.now(timezone.utc),
                    source="practice",
                    concept_breakdown=[
                        ConceptUpdateIn(
                            concept_id=ai_out.concept_id,
                            is_correct=is_positive,
                            weight_change=weight_change,
                        )
                    ],
                ),
            )
            mastery_updated = bool(graph_out.success)
            new_mastery = float(graph_out.new_mastery) if graph_out.new_mastery is not None else None
        except GraphClientValidationError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        activity = ActivityLogCreate(
            student_id=payload.student_id,
            subject=payload.subject,
            term=payload.term,
            event_type="mastery_check_done",
            ref_id=str(payload.assessment_id),
            duration_seconds=0,
        )
        self.activity_service.log_activity(activity)

        resolved_state = dict(state)
        resolved_state.update(
            {
                "status": "answered",
                "submitted_at": datetime.now(timezone.utc).isoformat(),
                "student_answer": payload.answer,
                "score": ai_out.score,
                "is_correct": ai_out.is_correct,
                "mastery_updated": mastery_updated,
                "new_mastery": new_mastery,
                "ideal_answer": ai_out.ideal_answer,
            }
        )
        self.repo.update_message_content(message_id=message_id, content=self._encode_state(resolved_state))
        self.repo.add_message(session_id=payload.session_id, role="assistant", content=ai_out.feedback)
        prerequisite_warning, recommended_topic_id, recommended_topic_title, graph_remediation = self._graph_follow_up(
            payload=payload,
            focus_concept_id=ai_out.concept_id,
            fallback_topic_id=payload.topic_id,
        )

        adaptive_action = None
        adaptive_reason = None
        adaptive_difficulty = None
        recent_states = self._recent_answered_states(session_id=payload.session_id, limit=6)
        correct_streak, incorrect_streak = self._concept_streak(recent_states, ai_out.concept_id)
        recent_difficulty = str(state.get("difficulty") or payload.difficulty or "").strip().lower() or None
        if incorrect_streak >= 2 and graph_remediation and graph_remediation.blocking_prerequisite_label:
            adaptive_action = "bridge_prerequisite"
            adaptive_reason = (
                f"Two misses on {ai_out.concept_label}. "
                f"Bridge {graph_remediation.blocking_prerequisite_label} before retrying."
            )
        elif correct_streak >= 2 and recent_difficulty != "hard":
            adaptive_action = "harder_checkpoint"
            adaptive_difficulty = "hard"
            adaptive_reason = f"Strong mastery on {ai_out.concept_label}. Moving to a harder checkpoint."
        elif ai_out.score >= 0.9 and recent_difficulty != "hard":
            adaptive_action = "harder_checkpoint"
            adaptive_difficulty = "hard"
            adaptive_reason = f"Quick mastery detected on {ai_out.concept_label}. Try a harder checkpoint."
        from backend.services.lesson_cockpit_service import LessonCockpitService
        from backend.services.lesson_experience_service import LessonExperienceService
        from backend.services.course_experience_service import CourseExperienceService
        from backend.services.dashboard_experience_service import DashboardExperienceService

        LessonExperienceService.invalidate_topic_snapshot_cache(
            student_id=payload.student_id,
            subject=payload.subject,
            sss_level=payload.sss_level,
            term=int(payload.term),
            topic_id=payload.topic_id,
        )
        LessonCockpitService.invalidate_scope_cache(
            student_id=payload.student_id,
            subject=payload.subject,
            sss_level=payload.sss_level,
            term=int(payload.term),
        )
        CourseExperienceService.invalidate_scope_cache(
            student_id=payload.student_id,
            subject=payload.subject,
            sss_level=payload.sss_level,
            term=int(payload.term),
        )
        DashboardExperienceService.invalidate_student_cache(student_id=payload.student_id)
        response = ai_out.model_copy(
            update={
                "assessment_id": payload.assessment_id,
                "mastery_updated": mastery_updated,
                "new_mastery": new_mastery,
                "actions": list(ai_out.actions) + ["MASTERED_CHECK_RECORDED" if mastery_updated else "MASTERED_CHECK_SKIPPED"],
                "prerequisite_warning": prerequisite_warning,
                "recommended_topic_id": recommended_topic_id,
                "recommended_topic_title": recommended_topic_title,
                "recommended_next_concept_label": (
                    graph_remediation.recommended_next_concept_label if graph_remediation else recommended_topic_title
                ),
                "graph_remediation": graph_remediation,
                "adaptive_action": adaptive_action,
                "adaptive_reason": adaptive_reason,
                "adaptive_difficulty": adaptive_difficulty,
            }
        )
        log_timed_event(
            logger,
            "tutor.assessment.submit",
            started_at,
            outcome="success",
            student_id=payload.student_id,
            session_id=payload.session_id,
            topic_id=payload.topic_id,
            concept_id=ai_out.concept_id,
            score=ai_out.score,
            mastery_updated=mastery_updated,
            recommended_topic_id=recommended_topic_id or "none",
            adaptive_action=adaptive_action or "none",
        )
        return response
