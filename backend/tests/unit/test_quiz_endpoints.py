import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from types import SimpleNamespace

from backend.main import app
from backend.core.auth import get_current_user
from backend.services.quiz_generate_service import QuizGenerateService
from backend.services.quiz_submit_service import QuizSubmitService
from backend.services.quiz_results_service import QuizResultsService

client = TestClient(app)
STUDENT_ID = uuid4()


@pytest.fixture
def mock_db():
    # Override dependency if needed, but we'll mock services
    pass


@pytest.fixture(autouse=True)
def override_auth():
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=STUDENT_ID)
    yield
    app.dependency_overrides.pop(get_current_user, None)


def test_generate_quiz_endpoint():
    quiz_id = uuid4()
    mock_response = {
        "quiz_id": str(quiz_id),
        "questions": [
            {
                "id": str(uuid4()),
                "text": "Sample question",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
                "concept_id": str(uuid4()),
                "difficulty": "medium",
            }
        ],
    }

    with patch.object(
        QuizGenerateService, "generate_quiz", new=AsyncMock(return_value=mock_response)
    ):
        response = client.post(
            "/api/v1/learning/quizzes/generate",
            json={
                "student_id": str(STUDENT_ID),
                "subject": "math",
                "sss_level": "SSS2",
                "term": 1,
                "topic_id": str(uuid4()),
                "purpose": "practice",
                "difficulty": "medium",
                "num_questions": 5,
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert "quiz_id" in data
    assert len(data["questions"]) == 1


def test_submit_quiz_endpoint():
    quiz_id = uuid4()
    mock_response = {"attempt_id": str(uuid4()), "score": 80.0, "xp_awarded": 80}

    with patch.object(
        QuizSubmitService, "submit_quiz", new=AsyncMock(return_value=mock_response)
    ):
        response = client.post(
            f"/api/v1/learning/quizzes/{quiz_id}/submit",
            json={
                "student_id": str(STUDENT_ID),
                "answers": [{"question_id": str(uuid4()), "answer": "A"}],
                "time_taken_seconds": 120,
            },
        )
    assert response.status_code == 200
    assert response.json()["score"] == 80.0


def test_get_results_endpoint():
    quiz_id = uuid4()
    student_id = STUDENT_ID
    attempt_id = uuid4()
    mock_response = {
        "score": 80.0,
        "concept_breakdown": [],
        "insights": ["Good job"],
        "recommended_revision_topic_id": None,
    }

    with patch.object(
        QuizResultsService, "get_results", new=AsyncMock(return_value=mock_response)
    ):
        response = client.get(
            f"/api/v1/learning/quizzes/{quiz_id}/results",
            params={"student_id": str(student_id), "attempt_id": str(attempt_id)},
        )
    assert response.status_code == 200
    assert response.json()["insights"][0] == "Good job"
