import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from fastapi import HTTPException

from backend.schemas.quiz_schema import QuizSubmitRequest
from backend.services.quiz_submit_service import QuizSubmitService
from backend.models.quiz import Quiz, QuizQuestion


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def quiz_id():
    return uuid4()


@pytest.fixture
def student_id():
    return uuid4()


@pytest.fixture
def submit_request(student_id):
    return QuizSubmitRequest(
        student_id=student_id,
        answers=[{"question_id": uuid4(), "answer": "A"}],
        time_taken_seconds=120,
    )


@pytest.fixture
def mock_quiz(quiz_id, student_id):
    quiz = MagicMock(spec=Quiz)
    quiz.id = quiz_id
    quiz.student_id = student_id
    quiz.subject = "math"
    quiz.sss_level = "SSS2"
    quiz.term = 1
    quiz.purpose = "practice"
    return quiz


@pytest.fixture
def mock_question(quiz_id):
    q = MagicMock(spec=QuizQuestion)
    q.id = uuid4()
    q.quiz_id = quiz_id
    q.correct_answer = "A"
    q.concept_id = uuid4()
    return q


@pytest.mark.anyio
async def test_submit_quiz_success(
    mock_db, quiz_id, student_id, submit_request, mock_quiz, mock_question
):
    # Align request question_id with mocked question so grading path is exercised.
    submit_request.answers[0].question_id = mock_question.id

    service = QuizSubmitService(mock_db)
    service.repo.get_quiz_with_questions = MagicMock(return_value=mock_quiz)
    service.repo.get_questions_for_quiz = MagicMock(return_value=[mock_question])
    service.repo.create_attempt = MagicMock(return_value=MagicMock(id=uuid4()))
    service.repo.save_answers = MagicMock()
    service.repo.update_attempt_score = MagicMock()

    # Mock activity and graph services
    service.activity_service.log_activity = AsyncMock()
    service.graph_service.send_update = AsyncMock()

    response = await service.submit_quiz(quiz_id, submit_request)

    assert response.score == 100.0  # because answer matches
    assert response.xp_awarded == 100
    service.repo.create_attempt.assert_called_once()
    service.activity_service.log_activity.assert_awaited_once()
    service.graph_service.send_update.assert_awaited_once()
    sent_payload = service.graph_service.send_update.await_args.kwargs["concept_breakdown"]
    assert len(sent_payload) == 1
    assert sent_payload[0].concept_id == str(mock_question.concept_id)


@pytest.mark.anyio
async def test_submit_quiz_skips_unmapped_questions_for_mastery_update(
    mock_db, quiz_id, student_id, submit_request, mock_quiz
):
    question = MagicMock(spec=QuizQuestion)
    question.id = submit_request.answers[0].question_id
    question.quiz_id = quiz_id
    question.correct_answer = "A"
    question.concept_id = None

    service = QuizSubmitService(mock_db)
    service.repo.get_quiz_with_questions = MagicMock(return_value=mock_quiz)
    service.repo.get_questions_for_quiz = MagicMock(return_value=[question])
    service.repo.create_attempt = MagicMock(return_value=MagicMock(id=uuid4()))
    service.repo.save_answers = MagicMock()
    service.repo.update_attempt_score = MagicMock()
    service.activity_service.log_activity = AsyncMock()
    service.graph_service.send_update = AsyncMock()

    response = await service.submit_quiz(quiz_id, submit_request)

    assert response.score == 100.0
    service.graph_service.send_update.assert_not_awaited()


@pytest.mark.anyio
async def test_submit_quiz_not_found(mock_db, quiz_id, submit_request):
    service = QuizSubmitService(mock_db)
    service.repo.get_quiz_with_questions = MagicMock(return_value=None)

    with pytest.raises(HTTPException) as exc:
        await service.submit_quiz(quiz_id, submit_request)
    assert exc.value.status_code == 404
