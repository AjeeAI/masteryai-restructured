import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from fastapi import HTTPException

from backend.services.quiz_results_service import QuizResultsService
from backend.models.quiz import QuizAttempt, Quiz
from backend.models.quiz_question import QuizQuestion


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
def attempt_id():
    return uuid4()


@pytest.fixture
def mock_attempt(attempt_id, quiz_id, student_id):
    attempt = MagicMock(spec=QuizAttempt)
    attempt.id = attempt_id
    attempt.quiz_id = quiz_id
    attempt.student_id = student_id
    attempt.score = 80.0
    attempt.answers = []
    return attempt


@pytest.fixture
def mock_quiz(quiz_id):
    quiz = MagicMock(spec=Quiz)
    quiz.id = quiz_id
    quiz.subject = "civic"
    quiz.sss_level = "SSS1"
    quiz.term = 2
    quiz.topic_id = uuid4()
    return quiz


@pytest.mark.anyio
async def test_get_results_success(
    mock_db, quiz_id, student_id, attempt_id, mock_attempt, mock_quiz
):
    service = QuizResultsService(mock_db)
    service.repo.get_attempt_with_answers = MagicMock(return_value=mock_attempt)
    service.repo.get_quiz_with_questions = MagicMock(return_value=mock_quiz)
    service.repo.get_questions_for_quiz = MagicMock(return_value=[])
    service.repo.get_topic_title = MagicMock(return_value="Electoral Process and Participation")
    service.repo.find_topic_title_for_concept = MagicMock(return_value=None)

    with patch(
        "backend.services.quiz_results_service.generate_quiz_insights",
        new=AsyncMock(return_value=["Insight 1"]),
    ):
        response = await service.get_results(quiz_id, student_id, attempt_id)

    assert response.score == 80.0
    assert response.insights == ["Insight 1"]
    assert response.recommended_revision_topic_title is None


@pytest.mark.anyio
async def test_get_results_returns_readable_labels_and_topic_title(
    mock_db, quiz_id, student_id, attempt_id, mock_attempt, mock_quiz
):
    service = QuizResultsService(mock_db)
    concept_id = "civic:sss1:t2:constitutional-governance"
    question_id = uuid4()
    mapped_topic_id = uuid4()

    mock_answer = MagicMock()
    mock_answer.question_id = question_id
    mock_answer.is_correct = False
    mock_attempt.answers = [mock_answer]

    mock_question = MagicMock(spec=QuizQuestion)
    mock_question.id = question_id
    mock_question.concept_id = concept_id

    service.repo.get_attempt_with_answers = MagicMock(return_value=mock_attempt)
    service.repo.get_quiz_with_questions = MagicMock(return_value=mock_quiz)
    service.repo.get_questions_for_quiz = MagicMock(return_value=[mock_question])
    service.repo.get_topic_title = MagicMock(side_effect=lambda topic_id: "Electoral Process and Participation" if topic_id else None)
    service.repo.find_topic_title_for_concept = MagicMock(return_value="Electoral Process and Participation")
    service.repo.find_topic_id_for_concept = MagicMock(return_value=mapped_topic_id)
    service.repo.topic_exists = MagicMock(return_value=True)

    with patch(
        "backend.services.quiz_results_service.generate_quiz_insights",
        new=AsyncMock(return_value=["Review constitutional governance."]),
    ):
        response = await service.get_results(quiz_id, student_id, attempt_id)

    assert response.concept_breakdown[0].concept_id == concept_id
    assert response.concept_breakdown[0].concept_label == "Constitutional Governance"
    assert response.recommended_revision_topic_id == mapped_topic_id
    assert response.recommended_revision_topic_title == "Electoral Process and Participation"
    assert response.recommendation_story is not None
    assert response.recommendation_story.status == "hold_current"
    assert response.recommendation_story.headline == "Stay with Constitutional Governance"
    assert response.recommendation_story.evidence_summary == "Review constitutional governance."


@pytest.mark.anyio
async def test_get_results_skips_unmapped_question_concepts(
    mock_db, quiz_id, student_id, attempt_id, mock_attempt, mock_quiz
):
    service = QuizResultsService(mock_db)
    question_id = uuid4()

    mock_answer = MagicMock()
    mock_answer.question_id = question_id
    mock_answer.is_correct = False
    mock_attempt.answers = [mock_answer]

    mock_question = MagicMock(spec=QuizQuestion)
    mock_question.id = question_id
    mock_question.concept_id = None

    service.repo.get_attempt_with_answers = MagicMock(return_value=mock_attempt)
    service.repo.get_quiz_with_questions = MagicMock(return_value=mock_quiz)
    service.repo.get_questions_for_quiz = MagicMock(return_value=[mock_question])
    service.repo.get_topic_title = MagicMock(return_value="Electoral Process and Participation")
    service.repo.find_topic_title_for_concept = MagicMock(return_value=None)

    with patch(
        "backend.services.quiz_results_service.generate_quiz_insights",
        new=AsyncMock(return_value=["Use the next lesson step to rebuild weak evidence."]),
    ):
        response = await service.get_results(quiz_id, student_id, attempt_id)

    assert response.concept_breakdown == []
    assert response.recommended_revision_topic_id is None
    assert response.graph_remediation is None


@pytest.mark.anyio
async def test_get_results_attempt_not_found(
    mock_db, quiz_id, student_id, attempt_id
):
    service = QuizResultsService(mock_db)
    service.repo.get_attempt_with_answers = MagicMock(return_value=None)

    with pytest.raises(HTTPException) as exc:
        await service.get_results(quiz_id, student_id, attempt_id)
    assert exc.value.status_code == 404
