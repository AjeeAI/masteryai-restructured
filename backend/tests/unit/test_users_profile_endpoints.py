from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.main import app
from backend.schemas.user_schema import UserProfileOut


def _override_db():
    yield object()


def test_users_me_get_and_put(monkeypatch):
    user_id = uuid4()

    def _override_user():
        return SimpleNamespace(id=user_id, role="student")

    def _fake_get_me(self, _user_id):
        return UserProfileOut(
            user_id=str(_user_id),
            email="olasquare@example.com",
            role="student",
            first_name="Olasquare",
            last_name="Adeola",
            display_name="Olasquare Adeola",
            avatar_url=None,
            phone=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    def _fake_update_me(self, _user_id, payload):
        return UserProfileOut(
            user_id=str(_user_id),
            email="olasquare@example.com",
            role="student",
            first_name=payload.first_name or "Olasquare",
            last_name=payload.last_name or "Adeola",
            display_name=payload.display_name or "Olasquare Adeola",
            avatar_url=payload.avatar_url,
            phone=payload.phone,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr("backend.services.user_service.UserService.get_me", _fake_get_me)
    monkeypatch.setattr("backend.services.user_service.UserService.update_me", _fake_update_me)

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    client = TestClient(app)

    profile_response = client.get("/api/v1/users/me")
    update_response = client.put(
        "/api/v1/users/me",
        json={
            "display_name": "Olasquare A.",
            "phone": "+2348012345678",
            "avatar_url": "https://cdn.example.com/avatar.png",
        },
    )

    app.dependency_overrides.clear()

    assert profile_response.status_code == 200
    assert profile_response.json()["display_name"] == "Olasquare Adeola"

    assert update_response.status_code == 200
    assert update_response.json()["display_name"] == "Olasquare A."
    assert update_response.json()["phone"] == "+2348012345678"
