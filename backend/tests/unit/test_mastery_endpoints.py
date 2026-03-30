from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.main import app


def _override_db():
    yield object()


def test_mastery_endpoint_success(monkeypatch):
    student_id = uuid4()

    def _override_user():
        return SimpleNamespace(id=student_id, role="student")

    class _FakeService:
        def get_dashboard(self, **kwargs):
            return {
                "subject": kwargs["subject"],
                "view": kwargs["view"],
                "mastery": [{"concept_id": "c1", "score": 0.7}],
                "streak": {"current": 4, "best": 7},
                "badges": ["Consistency-5"],
            }

    monkeypatch.setattr("backend.endpoints.mastery._service", lambda db: _FakeService())
    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    client = TestClient(app)

    response = client.get(
        "/api/v1/learning/mastery",
        params={
            "student_id": str(student_id),
            "subject": "math",
            "term": 1,
            "view": "concept",
            "persist_snapshot": "false",
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["subject"] == "math"
    assert response.json()["view"] == "concept"


def test_mastery_endpoint_rejects_mismatched_student_id(monkeypatch):
    auth_user_id = uuid4()
    payload_student_id = uuid4()

    def _override_user():
        return SimpleNamespace(id=auth_user_id, role="student")

    class _FakeService:
        def get_dashboard(self, **kwargs):
            return {
                "subject": kwargs["subject"],
                "view": kwargs["view"],
                "mastery": [],
                "streak": {"current": 0, "best": 0},
                "badges": [],
            }

    monkeypatch.setattr("backend.endpoints.mastery._service", lambda db: _FakeService())
    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    client = TestClient(app)

    response = client.get(
        "/api/v1/learning/mastery",
        params={
            "student_id": str(payload_student_id),
            "subject": "english",
            "term": 1,
            "view": "concept",
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 403
