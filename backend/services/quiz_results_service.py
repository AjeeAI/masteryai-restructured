from __future__ import annotations

import logging
import re
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.core.telemetry import log_timed_event, now_ms
from backend.core.ai_core_client import generate_quiz_insights
from backend.repositories.quiz_repo import QuizRepository
from backend.schemas.learning_path_schema import PathNextIn
from backend.schemas.course_schema import CourseRecommendationStoryOut
from backend.schemas.quiz_schema import (
    QuizGraphRemediationOut,
    QuizResultConceptBreakdownItem,
    QuizResultsResponse,
)
from backend.services.learning_path_service import learning_path_service
from backend.services.prewarm_job_service import PrewarmJobService

logger = logging.getLogger(__name__)


class QuizResultsService:
    def __init__(self, db: Session):
        self.repo = QuizRepository(db)

    @staticmethod
    def _readable_concept_label(concept_id: str, *, fallback_topic_title: str | None = None) -> str:
        value = str(concept_id or "").strip()
        if not value:
            return str(fallback_topic_title or "Untitled Concept").strip()

        try:
            UUID(value)
            fallback = str(fallback_topic_title or "").strip()
            return fallback or "Untitled Concept"
        except ValueError:
            pass

        topic_match = re.fullmatch(r"topic:([0-9a-fA-F-]{36})(?::.*)?", value)
        if topic_match:
            fallback = str(fallback_topic_title or "").strip()
            return fallback or "Topic Concept"

        token = value.rsplit(":", 1)[-1].strip()
        token = re.sub(r"-(\d+)$", "", token)
        token = re.sub(r"[_-]+", " ", token)
        token = re.sub(r"\s+", " ", token).strip()
        return token.title() if token else str(fallback_topic_title or "Untitled Concept").strip()

    @staticmethod
    def _looks_uuid(value: str | None) -> bool:
        text = str(value or "").strip()
        if not text:
            return False
        try:
            UUID(text)
            return True
        except (TypeError, ValueError):
            return False

    def _normalize_concept_label(
        self,
        label: str | None,
        *,
        concept_id: str | None,
        fallback_topic_title: str | None = None,
    ) -> str | None:
        text = str(label or "").strip()
        concept_text = str(concept_id or "").strip()
        if not text or text == concept_text or ":" in text or self._looks_uuid(text):
            if not concept_text:
                return self._readable_concept_label("", fallback_topic_title=fallback_topic_title)
            return self._readable_concept_label(concept_text, fallback_topic_title=fallback_topic_title)
        return text

    async def get_results(self, quiz_id: UUID, student_id: UUID, attempt_id: UUID) -> QuizResultsResponse:
        started_at = now_ms()
        attempt = self.repo.get_attempt_with_answers(attempt_id)
        if not attempt or attempt.quiz_id != quiz_id or attempt.student_id != student_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")

        quiz = self.repo.get_quiz_with_questions(quiz_id)
        if not quiz:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")

        questions = self.repo.get_questions_for_quiz(quiz_id)
        question_map = {q.id: q for q in questions}
        quiz_topic_title = self.repo.get_topic_title(getattr(quiz, "topic_id", None))

        concept_correctness: dict[str, list[bool]] = {}
        for answer in getattr(attempt, "answers", []):
            question = question_map.get(answer.question_id)
            if not question:
                continue

            raw_concept_id = getattr(question, "concept_id", None)
            concept_id = str(raw_concept_id).strip() if raw_concept_id not in (None, "") else ""
            if not concept_id:
                continue
            concept_correctness.setdefault(concept_id, []).append(bool(answer.is_correct))

        concept_breakdown: list[QuizResultConceptBreakdownItem] = []
        weakest_concept: str | None = None
        weakest_accuracy = 1.0

        for concept_id, values in concept_correctness.items():
            accuracy = sum(values) / len(values)
            is_correct = accuracy >= 0.5
            weight_change = 0.15 if is_correct else -0.05
            mapped_topic_title = self.repo.find_topic_title_for_concept(
                concept_id=concept_id,
                subject=str(getattr(quiz, "subject", "")).strip().lower(),
                sss_level=str(getattr(quiz, "sss_level", "")).strip(),
                term=int(getattr(quiz, "term", 0) or 0),
            )
            concept_label = self._readable_concept_label(
                concept_id,
                fallback_topic_title=mapped_topic_title or quiz_topic_title,
            )

            concept_breakdown.append(
                QuizResultConceptBreakdownItem(
                    concept_id=concept_id,
                    concept_label=concept_label,
                    is_correct=is_correct,
                    weight_change=weight_change,
                )
            )

            if accuracy < weakest_accuracy:
                weakest_accuracy = accuracy
                weakest_concept = concept_id

        try:
            insights = await generate_quiz_insights(quiz_id, attempt_id)
        except Exception:
            insights = ["Insights are temporarily unavailable. Review missed concepts and retry."]

        recommended_topic = None
        recommended_topic_title = None
        graph_remediation = None
        recommendation_story = None
        if weakest_concept is not None:
            recommended_topic = await self._get_topic_for_concept(
                weakest_concept,
                quiz=quiz,
                fallback_topic_id=quiz.topic_id,
            )
            recommended_topic_title = self.repo.get_topic_title(recommended_topic)
            graph_remediation = self._build_graph_remediation(
                weakest_concept=weakest_concept,
                quiz=quiz,
                fallback_topic_id=quiz.topic_id,
            )
            recommendation_story = self._build_recommendation_story(
                graph_remediation=graph_remediation,
                quiz_topic_title=quiz_topic_title,
                insights=insights,
            )

        response = QuizResultsResponse(
            score=float(attempt.score or 0.0),
            concept_breakdown=concept_breakdown,
            insights=insights,
            recommended_revision_topic_id=recommended_topic,
            recommended_revision_topic_title=recommended_topic_title,
            graph_remediation=graph_remediation,
            recommendation_story=recommendation_story,
        )
        prewarm_candidates: list[UUID] = []
        if graph_remediation:
            def _parse_uuid(value: str | UUID | None) -> UUID | None:
                if value is None:
                    return None
                if isinstance(value, UUID):
                    return value
                try:
                    return UUID(str(value))
                except (TypeError, ValueError):
                    return None

            for candidate in [recommended_topic, graph_remediation.recommended_next_topic_id]:
                candidate_id = _parse_uuid(candidate)
                if candidate_id is not None:
                    prewarm_candidates.append(candidate_id)

            if graph_remediation.blocking_prerequisite_id:
                mapped = self.repo.find_topic_id_for_concept(
                    concept_id=str(graph_remediation.blocking_prerequisite_id),
                    subject=str(getattr(quiz, "subject", "")).strip().lower(),
                    sss_level=str(getattr(quiz, "sss_level", "")).strip(),
                    term=int(getattr(quiz, "term", 0) or 0),
                )
                if mapped is not None:
                    prewarm_candidates.append(mapped)

        prewarm_enqueued = False
        if prewarm_candidates:
            unique_candidates = []
            seen = set()
            for candidate in prewarm_candidates:
                if candidate in seen:
                    continue
                seen.add(candidate)
                unique_candidates.append(candidate)
            try:
                prewarm_id = PrewarmJobService(self.repo.db).enqueue_lesson_related(
                    student_id=student_id,
                    subject=str(getattr(quiz, "subject", "")).strip().lower(),
                    sss_level=str(getattr(quiz, "sss_level", "")).strip(),
                    term=int(getattr(quiz, "term", 0) or 0),
                    topic_ids=unique_candidates,
                )
                prewarm_enqueued = bool(prewarm_id)
            except Exception:
                prewarm_enqueued = False
        log_timed_event(
            logger,
            "quiz.results",
            started_at,
            outcome="success",
            student_id=student_id,
            quiz_id=quiz_id,
            attempt_id=attempt_id,
            concept_breakdown=len(concept_breakdown),
            insights=len(insights),
            recommended_topic_id=recommended_topic or "none",
            prewarm_candidates=len(prewarm_candidates),
            prewarm_enqueued=prewarm_enqueued,
        )
        return response

    def _build_graph_remediation(
        self,
        *,
        weakest_concept: str,
        quiz,
        fallback_topic_id: UUID | None,
    ) -> QuizGraphRemediationOut | None:
        def _parse_uuid(value: str | None) -> UUID | None:
            if not value:
                return None
            try:
                return UUID(str(value))
            except (TypeError, ValueError):
                return None

        subject = str(getattr(quiz, "subject", "")).strip().lower()
        sss_level = str(getattr(quiz, "sss_level", "")).strip()
        term = int(getattr(quiz, "term", 0) or 0)
        try:
            next_step = learning_path_service.calculate_next_step(
                db=self.repo.db,
                payload=PathNextIn(
                    student_id=quiz.student_id,
                    subject=subject,  # type: ignore[arg-type]
                    sss_level=sss_level,  # type: ignore[arg-type]
                    term=term,
                ),
            )
        except Exception:
            next_step = None

        blocking_prerequisite_id = next_step.prereq_gaps[0] if next_step and next_step.prereq_gaps else None
        blocking_prerequisite_topic_title = (
            self.repo.find_topic_title_for_concept(
                concept_id=blocking_prerequisite_id,
                subject=subject,
                sss_level=sss_level,
                term=term,
            )
            if blocking_prerequisite_id
            else None
        )

        recommended_next_concept_id = next_step.recommended_concept_id if next_step else None
        recommended_next_concept_topic_title = (
            self.repo.find_topic_title_for_concept(
                concept_id=str(recommended_next_concept_id),
                subject=subject,
                sss_level=sss_level,
                term=term,
            )
            if recommended_next_concept_id
            else None
        )
        recommended_next_topic_id = _parse_uuid(next_step.recommended_topic_id) if next_step else None
        recommended_next_topic_title = None
        if next_step and next_step.recommended_topic_title and not self._looks_uuid(next_step.recommended_topic_title):
            recommended_next_topic_title = str(next_step.recommended_topic_title).strip() or None
        if recommended_next_topic_title is None and recommended_next_topic_id:
            recommended_next_topic_title = self.repo.get_topic_title(recommended_next_topic_id)
        if recommended_next_topic_title is None:
            recommended_next_topic_title = self.repo.get_topic_title(fallback_topic_id)

        return QuizGraphRemediationOut(
            weakest_concept_id=weakest_concept,
            weakest_concept_label=self._readable_concept_label(
                weakest_concept,
                fallback_topic_title=self.repo.find_topic_title_for_concept(
                    concept_id=weakest_concept,
                    subject=subject,
                    sss_level=sss_level,
                    term=term,
                ) or self.repo.get_topic_title(fallback_topic_id),
            ),
            blocking_prerequisite_id=blocking_prerequisite_id,
            blocking_prerequisite_label=(
                self._normalize_concept_label(
                    None,
                    concept_id=blocking_prerequisite_id,
                    fallback_topic_title=blocking_prerequisite_topic_title,
                )
                if blocking_prerequisite_id
                else None
            ),
            blocking_prerequisite_topic_title=blocking_prerequisite_topic_title,
            recommended_next_concept_id=recommended_next_concept_id,
            recommended_next_concept_label=(
                self._normalize_concept_label(
                    next_step.recommended_concept_label if next_step else None,
                    concept_id=str(recommended_next_concept_id or ""),
                    fallback_topic_title=recommended_next_concept_topic_title,
                )
                if next_step
                else None
            ),
            recommended_next_topic_id=recommended_next_topic_id or fallback_topic_id,
            recommended_next_topic_title=recommended_next_topic_title,
            recommendation_reason=(next_step.reason if next_step else None),
        )

    @staticmethod
    def _clean_text(value: str | None) -> str | None:
        text = str(value or "").strip()
        return text or None

    def _build_recommendation_story(
        self,
        *,
        graph_remediation: QuizGraphRemediationOut | None,
        quiz_topic_title: str | None,
        insights: list[str],
    ) -> CourseRecommendationStoryOut | None:
        if graph_remediation is None:
            return None

        evidence_summary = self._clean_text(insights[0] if insights else None)
        blocking_label = self._clean_text(graph_remediation.blocking_prerequisite_label)
        weakest_label = self._clean_text(graph_remediation.weakest_concept_label)
        next_concept_label = self._clean_text(graph_remediation.recommended_next_concept_label)
        next_topic_title = self._clean_text(graph_remediation.recommended_next_topic_title)
        recommendation_reason = self._clean_text(graph_remediation.recommendation_reason)
        current_topic_title = self._clean_text(quiz_topic_title)

        if blocking_label:
            supporting_reason = (
                recommendation_reason
                or f"You are still blocked by {blocking_label}, so rebuilding it will improve the weak concept faster."
            )
            headline = f"Rebuild {blocking_label} before pushing ahead"
            action_label = f"Open {next_topic_title}" if next_topic_title else "Bridge the prerequisite"
            return CourseRecommendationStoryOut(
                status="bridge_prerequisite",
                headline=headline,
                supporting_reason=supporting_reason,
                blocking_prerequisite_label=blocking_label,
                next_concept_label=next_concept_label or weakest_label,
                evidence_summary=evidence_summary,
                action_label=action_label,
            )

        if next_topic_title and current_topic_title and next_topic_title != current_topic_title:
            supporting_reason = (
                recommendation_reason
                or f"You recovered enough signal on {weakest_label or 'this concept'} to move forward through {next_topic_title}."
            )
            return CourseRecommendationStoryOut(
                status="advance_to_next",
                headline=f"Advance through {next_topic_title}",
                supporting_reason=supporting_reason,
                blocking_prerequisite_label=None,
                next_concept_label=next_concept_label or weakest_label,
                evidence_summary=evidence_summary,
                action_label=f"Open {next_topic_title}",
            )

        focus_label = weakest_label or next_concept_label or current_topic_title or "this concept"
        supporting_reason = recommendation_reason or f"Stay on {focus_label} and close the weak spots before moving on."
        action_label = f"Retry {current_topic_title}" if current_topic_title else "Retry this topic"
        return CourseRecommendationStoryOut(
            status="hold_current",
            headline=f"Stay with {focus_label}",
            supporting_reason=supporting_reason,
            blocking_prerequisite_label=None,
            next_concept_label=next_concept_label or weakest_label,
            evidence_summary=evidence_summary,
            action_label=action_label,
        )

    async def _get_topic_for_concept(
        self,
        concept_id: str,
        *,
        quiz,
        fallback_topic_id: UUID | None,
    ) -> UUID | None:
        def _parse_uuid(value: str) -> UUID | None:
            try:
                return UUID(value)
            except (TypeError, ValueError):
                return None

        candidates: list[UUID] = []
        direct = _parse_uuid(concept_id)
        if direct is not None:
            candidates.append(direct)

        if concept_id.startswith("topic:"):
            parts = concept_id.split(":")
            if len(parts) >= 2:
                parsed = _parse_uuid(parts[1])
                if parsed is not None:
                    candidates.append(parsed)

        mapped_topic = self.repo.find_topic_id_for_concept(
            concept_id=concept_id,
            subject=str(getattr(quiz, "subject", "")).strip().lower(),
            sss_level=str(getattr(quiz, "sss_level", "")).strip(),
            term=int(getattr(quiz, "term", 0) or 0),
        )
        if mapped_topic is not None:
            candidates.append(mapped_topic)

        if fallback_topic_id is not None:
            candidates.append(fallback_topic_id)

        for topic_id in candidates:
            if self.repo.topic_exists(topic_id):
                return topic_id

        return None
