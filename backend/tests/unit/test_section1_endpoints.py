from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.main import app
from backend.schemas.activity_schema import ActivityLogOut, LeaderboardEntryOut, StudentStatsOut
from backend.schemas.student_schema import LearningPreferenceResponse


def _override_db():
    yield object()


def test_preferences_endpoints_legacy_and_normalized_alias(monkeypatch):
    user_id = uuid4()

    def _override_user():
        return SimpleNamespace(id=user_id, role="student")

    def _fake_update_preferences(self, uid, updates):
        return LearningPreferenceResponse(
            student_id=uid,
            explanation_depth="standard",
            examples_first=True,
            pace="normal",
            updated_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr("backend.services.student_service.StudentService.update_preferences", _fake_update_preferences)
    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user

    client = TestClient(app)
    payload = {"explanation_depth": "standard", "examples_first": True, "pace": "normal"}

    legacy = client.put(f"/api/v1/students/users/{user_id}/preferences", json=payload)
    normalized = client.put(f"/api/v1/users/{user_id}/preferences", json=payload)

    app.dependency_overrides.clear()

    assert legacy.status_code == 200
    assert normalized.status_code == 200
    assert legacy.json()["student_id"] == str(user_id)
    assert normalized.json()["student_id"] == str(user_id)


def test_activity_log_requires_matching_authenticated_user(monkeypatch):
    auth_user_id = uuid4()
    other_user_id = uuid4()

    def _override_user():
        return SimpleNamespace(id=auth_user_id, role="student")

    def _fake_log_activity(self, payload):
        return ActivityLogOut(status="success", message="Activity logged", points_awarded=10)

    monkeypatch.setattr("backend.services.activity_service.ActivityService.log_activity", _fake_log_activity)
    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user

    client = TestClient(app)
    payload = {
        "student_id": str(other_user_id),
        "subject": "math",
        "term": 1,
        "event_type": "lesson_viewed",
        "ref_id": "topic-1",
        "duration_seconds": 30,
    }
    response = client.post("/api/v1/learning/activity/log", json=payload)

    app.dependency_overrides.clear()

    assert response.status_code == 403


def test_activity_stats_and_leaderboard_endpoints(monkeypatch):
    auth_user_id = uuid4()

    def _override_user():
        return SimpleNamespace(id=auth_user_id, role="student")

    monkeypatch.setattr(
        "backend.services.activity_service.ActivityService.get_student_stats",
        lambda self, student_id: StudentStatsOut(streak=2, mastery_points=60, study_time_seconds=300),
    )
    monkeypatch.setattr(
        "backend.services.activity_service.ActivityService.get_leaderboard",
        lambda self, limit: [LeaderboardEntryOut(student_id=auth_user_id, total_mastery_points=60, rank=1)],
    )

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    client = TestClient(app)

    stats_response = client.get("/api/v1/students/stats")
    leaderboard_response = client.get("/api/v1/students/leaderboard")

    app.dependency_overrides.clear()

    assert stats_response.status_code == 200
    assert stats_response.json()["mastery_points"] == 60
    assert leaderboard_response.status_code == 200
    assert leaderboard_response.json()[0]["rank"] == 1
