from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.main import app
from backend.schemas.student_schema import LearningPreferenceResponse, StudentProfileResponse


def _override_db():
    yield object()


def test_profile_setup_accepts_preferences_inline(monkeypatch):
    user_id = uuid4()

    def _override_user():
        return SimpleNamespace(id=user_id, role="student")

    now = datetime.now(timezone.utc)

    def _fake_setup(self, request):
        assert request.preferences is not None
        assert request.preferences.explanation_depth.value == "detailed"
        assert request.preferences.examples_first is True
        assert request.preferences.pace.value == "slow"
        return StudentProfileResponse(
            id=uuid4(),
            user_id=user_id,
            sss_level="SSS1",
            current_term=1,
            subjects=["math", "english"],
            preferences=LearningPreferenceResponse(
                student_id=user_id,
                explanation_depth="detailed",
                examples_first=True,
                pace="slow",
                updated_at=now,
            ),
            created_at=now,
            updated_at=now,
        )

    monkeypatch.setattr("backend.services.student_service.StudentService.setup_profile", _fake_setup)
    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user

    client = TestClient(app)
    response = client.post(
        "/api/v1/students/profile/setup",
        json={
            "student_id": str(user_id),
            "sss_level": "SSS1",
            "subjects": ["math", "english"],
            "term": 1,
            "preferences": {
                "explanation_depth": "detailed",
                "examples_first": True,
                "pace": "slow",
            },
        },
        headers={"Authorization": "Bearer fake-token"},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == str(user_id)
    assert data["preferences"]["explanation_depth"] == "detailed"
    assert data["preferences"]["pace"] == "slow"


def test_profile_update_accepts_preferences_inline(monkeypatch):
    user_id = uuid4()
    profile_id = uuid4()

    def _override_user():
        return SimpleNamespace(id=user_id, role="student")

    now = datetime.now(timezone.utc)

    def _fake_update(self, sid, updates):
        assert sid == user_id
        assert updates.preferences is not None
        assert updates.preferences.explanation_depth.value == "standard"
        assert updates.preferences.examples_first is False
        return StudentProfileResponse(
            id=profile_id,
            user_id=user_id,
            sss_level="SSS2",
            current_term=2,
            subjects=["math", "civic"],
            preferences=LearningPreferenceResponse(
                student_id=user_id,
                explanation_depth="standard",
                examples_first=False,
                pace="normal",
                updated_at=now,
            ),
            created_at=now,
            updated_at=now,
        )

    monkeypatch.setattr("backend.services.student_service.StudentService.update_profile", _fake_update)
    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user

    client = TestClient(app)
    response = client.put(
        "/api/v1/students/profile",
        json={
            "sss_level": "SSS2",
            "current_term": 2,
            "subjects": ["math", "civic"],
            "preferences": {
                "explanation_depth": "standard",
                "examples_first": False,
            },
        },
        headers={"Authorization": "Bearer fake-token"},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(profile_id)
    assert data["preferences"]["examples_first"] is False
