from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.models.quiz import Quiz
from backend.models.quiz_answer import QuizAnswer
from backend.models.quiz_attempt import QuizAttempt
from backend.models.quiz_question import QuizQuestion
from backend.models.topic import Topic


class QuizRepository:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _normalize_options(raw_options: Any) -> list:
        if isinstance(raw_options, list):
            return [str(item) for item in raw_options]
        return []

    # --- Quiz Generation ---
    def create_quiz(
        self,
        *,
        student_id: UUID,
        subject: str,
        sss_level: str,
        term: int,
        topic_id: UUID,
        purpose: str,
        difficulty: str,
        num_questions: int,
    ) -> Quiz:
        quiz = Quiz(
            id=uuid4(),
            student_id=student_id,
            subject=subject,
            sss_level=sss_level,
            term=term,
            topic_id=topic_id,
            purpose=purpose,
            difficulty=difficulty,
            num_questions=num_questions,
        )
        self.db.add(quiz)
        self.db.flush()
        return quiz

    def add_question_to_quiz(self, quiz_id: UUID, question_data: dict[str, Any]) -> QuizQuestion:
        question_text = question_data.get("text") or question_data.get("question_text")
        if not question_text:
            raise ValueError("Question payload must include text")

        order = int(question_data.get("order", 0))
        question_number = max(order + 1, 1)
        question_id = question_data.get("id")
        if not isinstance(question_id, UUID):
            try:
                question_id = UUID(str(question_id)) if question_id else uuid4()
            except (TypeError, ValueError):
                question_id = uuid4()

        raw_concept_id = question_data.get("concept_id")
        concept_id = str(raw_concept_id).strip() if raw_concept_id is not None else ""
        if not concept_id:
            raise ValueError("Question payload must include a mapped concept_id")

        question = QuizQuestion(
            id=question_id,
            quiz_id=quiz_id,
            question_number=question_number,
            question_text=question_text,
            concept_id=concept_id,
            options=self._normalize_options(question_data.get("options")),
            correct_answer=question_data.get("correct_answer"),
            explanation=question_data.get("explanation"),
        )
        self.db.add(question)
        self.db.flush()
        return question

    def get_quiz_with_questions(self, quiz_id: UUID) -> Quiz | None:
        return self.db.query(Quiz).filter(Quiz.id == quiz_id).first()

    # --- Quiz Submission ---
    def create_attempt(
        self,
        quiz_id: UUID,
        student_id: UUID,
        time_taken: int,
        raw_answers: list[dict[str, Any]] | None = None,
    ) -> QuizAttempt:
        attempt = QuizAttempt(
            id=uuid4(),
            quiz_id=quiz_id,
            student_id=student_id,
            time_taken_seconds=time_taken,
            raw_answers=raw_answers or [],
        )
        self.db.add(attempt)
        self.db.flush()
        return attempt

    def save_answers(self, attempt_id: UUID, answers: list[dict[str, Any]]) -> int:
        saved_count = 0
        for ans in answers:
            question_id = ans.get("question_id")
            if question_id is None:
                continue

            answer = QuizAnswer(
                id=uuid4(),
                attempt_id=attempt_id,
                question_id=question_id,
                selected_answer=ans.get("answer"),
                is_correct=ans.get("is_correct"),
            )
            self.db.add(answer)
            saved_count += 1

        self.db.flush()
        return saved_count

    def update_attempt_score(self, attempt_id: UUID, score: float, xp: int) -> None:
        _ = xp
        self.db.query(QuizAttempt).filter(QuizAttempt.id == attempt_id).update(
            {
                "score": score,
                "status": "graded",
            },
            synchronize_session=False,
        )
        self.db.flush()

    def get_attempt(self, attempt_id: UUID) -> QuizAttempt | None:
        return self.db.query(QuizAttempt).filter(QuizAttempt.id == attempt_id).first()

    def get_attempt_with_answers(self, attempt_id: UUID) -> QuizAttempt | None:
        attempt = self.db.query(QuizAttempt).filter(QuizAttempt.id == attempt_id).first()
        if not attempt:
            return None

        answers = self.db.query(QuizAnswer).filter(QuizAnswer.attempt_id == attempt_id).all()
        setattr(attempt, "answers", answers)
        return attempt

    # --- Results ---
    def get_questions_for_quiz(self, quiz_id: UUID) -> list[QuizQuestion]:
        return (
            self.db.query(QuizQuestion)
            .filter(QuizQuestion.quiz_id == quiz_id)
            .order_by(QuizQuestion.question_number)
            .all()
        )

    def topic_exists(self, topic_id: UUID) -> bool:
        return self.db.query(Topic.id).filter(Topic.id == topic_id).first() is not None

    def get_topic_title(self, topic_id: UUID | None) -> str | None:
        if topic_id is None:
            return None
        row = self.db.query(Topic.title).filter(Topic.id == topic_id).first()
        if not row or row[0] is None:
            return None
        return str(row[0]).strip() or None

    def find_topic_id_for_concept(
        self,
        *,
        concept_id: str,
        subject: str,
        sss_level: str,
        term: int,
    ) -> UUID | None:
        row = self.db.execute(
            text(
                """
                SELECT t.id
                FROM curriculum_topic_maps m
                JOIN topics t ON t.id = m.topic_id
                JOIN subjects s ON s.id = t.subject_id
                WHERE m.concept_id = :concept_id
                  AND s.slug = :subject
                  AND t.sss_level = :sss_level
                  AND t.term = :term
                  AND t.is_approved = TRUE
                ORDER BY m.confidence DESC, m.updated_at DESC
                LIMIT 1
                """
            ),
            {
                "concept_id": concept_id,
                "subject": subject,
                "sss_level": sss_level,
                "term": term,
            },
        ).first()
        if not row:
            return None
        value = row[0]
        if isinstance(value, UUID):
            return value
        try:
            return UUID(str(value))
        except (TypeError, ValueError):
            return None

    def find_topic_title_for_concept(
        self,
        *,
        concept_id: str,
        subject: str,
        sss_level: str,
        term: int,
    ) -> str | None:
        row = self.db.execute(
            text(
                """
                SELECT t.title
                FROM curriculum_topic_maps m
                JOIN topics t ON t.id = m.topic_id
                JOIN subjects s ON s.id = t.subject_id
                WHERE m.concept_id = :concept_id
                  AND s.slug = :subject
                  AND t.sss_level = :sss_level
                  AND t.term = :term
                  AND t.is_approved = TRUE
                ORDER BY m.confidence DESC, m.updated_at DESC
                LIMIT 1
                """
            ),
            {
                "concept_id": concept_id,
                "subject": subject,
                "sss_level": sss_level,
                "term": term,
            },
        ).first()
        if not row or row[0] is None:
            return None
        return str(row[0]).strip() or None
