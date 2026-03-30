from __future__ import annotations

import logging
import inspect
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.core.telemetry import log_timed_event, now_ms
from backend.repositories.activity_repo import ActivityRepository
from backend.repositories.quiz_repo import QuizRepository
from backend.schemas.activity_schema import ActivityLogCreate
from backend.schemas.quiz_schema import ConceptBreakdownItem, QuizSubmitRequest, QuizSubmitResponse
from backend.services.activity_service import ActivityService
from backend.services.graph_mastery_update_service import GraphMasteryUpdateService

logger = logging.getLogger(__name__)


class QuizSubmitService:
    def __init__(self, db: Session):
        self.repo = QuizRepository(db)
        self.graph_service = GraphMasteryUpdateService(db)
        self.activity_service = ActivityService(ActivityRepository(db))

    @staticmethod
    def _normalize_answer(answer_item) -> dict[str, str] | None:
        if hasattr(answer_item, "question_id") and hasattr(answer_item, "answer"):
            question_id = str(answer_item.question_id)
            answer = str(answer_item.answer).strip()
            return {"question_id": question_id, "answer": answer} if answer else None

        if isinstance(answer_item, dict):
            question_id = str(answer_item.get("question_id") or "").strip()
            answer = str(answer_item.get("answer") or "").strip()
            if question_id and answer:
                return {"question_id": question_id, "answer": answer}

        return None

    async def submit_quiz(self, quiz_id: UUID, request: QuizSubmitRequest) -> QuizSubmitResponse:
        started_at = now_ms()
        quiz = self.repo.get_quiz_with_questions(quiz_id)
        if not quiz:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")

        if str(quiz.student_id) != str(request.student_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Quiz does not belong to the supplied student",
            )

        questions = self.repo.get_questions_for_quiz(quiz_id)
        question_map = {str(q.id): q for q in questions}

        normalized_answers = [
            parsed
            for parsed in (self._normalize_answer(item) for item in request.answers)
            if parsed is not None
        ]

        total_questions = len(questions)
        correct_count = 0
        concept_results: list[tuple[str, bool]] = []

        for answer in normalized_answers:
            qid = answer["question_id"]
            question = question_map.get(qid)
            if not question:
                continue

            expected = (question.correct_answer or "").strip().lower()
            is_correct = answer["answer"].strip().lower() == expected
            if is_correct:
                correct_count += 1

            raw_concept_id = getattr(question, "concept_id", None)
            concept_id = str(raw_concept_id).strip() if raw_concept_id not in (None, "") else ""
            if not concept_id:
                continue
            concept_results.append((concept_id, is_correct))

        score = round((correct_count / total_questions) * 100, 2) if total_questions > 0 else 0.0
        xp = int(score)

        try:
            attempt = self.repo.create_attempt(
                quiz_id,
                request.student_id,
                request.time_taken_seconds,
                raw_answers=normalized_answers,
            )

            answers_with_score = []
            for answer in normalized_answers:
                qid = answer["question_id"]
                question = question_map.get(qid)
                if not question:
                    continue

                expected = (question.correct_answer or "").strip().lower()
                is_correct = answer["answer"].strip().lower() == expected
                answers_with_score.append(
                    {
                        "question_id": question.id,
                        "answer": answer["answer"],
                        "is_correct": is_correct,
                    }
                )

            self.repo.save_answers(attempt.id, answers_with_score)
            self.repo.update_attempt_score(attempt.id, score, xp)

            activity_payload = ActivityLogCreate(
                student_id=request.student_id,
                subject=quiz.subject,
                term=quiz.term,
                event_type="quiz_submitted",
                ref_id=str(quiz_id),
                duration_seconds=request.time_taken_seconds,
            )
            activity_result = self.activity_service.log_activity(activity_payload)
            if inspect.isawaitable(activity_result):
                await activity_result
            self.repo.db.commit()
        except Exception:
            self.repo.db.rollback()
            raise

        source = quiz.purpose if quiz.purpose in {"practice", "diagnostic", "exam_prep"} else "practice"
        concept_breakdown = [
            ConceptBreakdownItem(
                concept_id=concept_id,
                is_correct=is_correct,
                weight_change=0.15 if is_correct else -0.05,
            )
            for concept_id, is_correct in concept_results
        ]

        if concept_breakdown:
            await self.graph_service.send_update(
                student_id=request.student_id,
                quiz_id=quiz_id,
                attempt_id=attempt.id,
                subject=quiz.subject,
                sss_level=quiz.sss_level,
                term=quiz.term,
                source=source,
                concept_breakdown=concept_breakdown,
            )

        from backend.services.lesson_cockpit_service import LessonCockpitService
        from backend.services.lesson_experience_service import LessonExperienceService
        from backend.services.course_experience_service import CourseExperienceService
        from backend.services.dashboard_experience_service import DashboardExperienceService

        LessonExperienceService.invalidate_topic_snapshot_cache(
            student_id=request.student_id,
            subject=quiz.subject,
            sss_level=quiz.sss_level,
            term=int(quiz.term),
            topic_id=quiz.topic_id,
        )
        LessonCockpitService.invalidate_scope_cache(
            student_id=request.student_id,
            subject=quiz.subject,
            sss_level=quiz.sss_level,
            term=int(quiz.term),
        )
        CourseExperienceService.invalidate_scope_cache(
            student_id=request.student_id,
            subject=quiz.subject,
            sss_level=quiz.sss_level,
            term=int(quiz.term),
        )
        DashboardExperienceService.invalidate_student_cache(student_id=request.student_id)

        response = QuizSubmitResponse(attempt_id=attempt.id, score=score, xp_awarded=xp)
        log_timed_event(
            logger,
            "quiz.submit",
            started_at,
            outcome="success",
            student_id=request.student_id,
            quiz_id=quiz_id,
            topic_id=quiz.topic_id,
            subject=quiz.subject,
            score=score,
            concept_updates=len(concept_breakdown),
        )
        return response
