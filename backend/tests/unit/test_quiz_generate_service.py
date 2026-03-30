import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from fastapi import HTTPException

from backend.schemas.quiz_schema import QuizGenerateRequest
from backend.services.quiz_generate_service import QuizGenerateService


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def generate_request():
    return QuizGenerateRequest(
        student_id=uuid4(),
        subject="math",
        sss_level="SSS2",
        term=1,
        topic_id=uuid4(),
        purpose="practice",
        difficulty="medium",
        num_questions=5,
    )


@pytest.mark.anyio
async def test_generate_quiz_success(mock_db, generate_request):
    # Mock AI core response
    mock_questions = [
        {
            "id": uuid4(),
            "text": "Sample question",
            "options": ["A", "B", "C", "D"],
            "correct_answer": "A",
            "concept_id": uuid4(),
            "difficulty": "medium",
        }
        for _ in range(5)
    ]

    with patch(
        "backend.services.quiz_generate_service.generate_quiz_questions",
        new=AsyncMock(return_value=mock_questions),
    ) as mock_ai:
        # Mock repository
        service = QuizGenerateService(mock_db)
        service.repo.create_quiz = MagicMock(return_value=MagicMock(id=uuid4()))
        created_rows = [
            MagicMock(id=uuid4(), concept_id=f"topic:{generate_request.topic_id}:c{idx}")
            for idx in range(5)
        ]
        service.repo.add_question_to_quiz = MagicMock(side_effect=created_rows)
        service.repo.find_topic_title_for_concept = MagicMock(return_value=None)

        response = await service.generate_quiz(generate_request)

        assert response.quiz_id is not None
        assert len(response.questions) == 5
        assert response.questions[0].id == created_rows[0].id
        assert response.questions[0].concept_id == created_rows[0].concept_id
        mock_ai.assert_called_once()
        service.repo.create_quiz.assert_called_once()
        assert service.repo.add_question_to_quiz.call_count == 5


@pytest.mark.anyio
async def test_generate_quiz_ai_failure(mock_db, generate_request):
    with patch(
        "backend.services.quiz_generate_service.generate_quiz_questions",
        new=AsyncMock(side_effect=Exception("AI error")),
    ):
        service = QuizGenerateService(mock_db)
        with pytest.raises(HTTPException) as exc:
            await service.generate_quiz(generate_request)
        assert exc.value.status_code == 503
        assert "AI generation failed" in exc.value.detail
