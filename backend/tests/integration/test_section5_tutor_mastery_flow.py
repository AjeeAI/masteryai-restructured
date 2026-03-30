import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.auth import get_current_user
from backend.core.config import settings
from backend.core.database import Base, get_db
from backend.main import app
from backend.models.student import StudentProfile
from backend.models.tutor_session import TutorSession
from backend.models.user import User
from backend.repositories.tutor_session_repo import TutorSessionRepository
from backend.tests.integration.db_utils import resolve_test_database_url


TEST_DATABASE_URL = resolve_test_database_url(test_label="Section 5 integration flow")


engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_database(monkeypatch):
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    student_id = uuid4()
    user = User(
        id=student_id,
        email=f"section5.student.{student_id}@example.com",
        password_hash="hash",
        role="student",
        is_active=True,
    )
    db.add(user)
    db.add(
        StudentProfile(
            id=uuid4(),
            student_id=student_id,
            sss_level="SSS2",
            active_term=1,
        )
    )
    db.commit()

    repo = TutorSessionRepository(db)
    session_row = repo.create_session(student_id=student_id, subject="math", term=1)
    session_id = session_row["id"]

    def _override_user():
        return SimpleNamespace(id=student_id, role="student")

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = _override_user

    monkeypatch.setattr(settings, "ai_core_base_url", "")
    monkeypatch.setattr(settings, "ai_core_allow_fallback", True)

    yield {"student_id": student_id, "session_id": session_id}

    cleanup = TestingSessionLocal()
    cleanup.query(TutorSession).filter(TutorSession.id == session_id).delete(synchronize_session=False)
    cleanup.query(StudentProfile).filter(StudentProfile.student_id == student_id).delete(synchronize_session=False)
    cleanup.query(User).filter(User.id == student_id).delete(synchronize_session=False)
    cleanup.commit()
    cleanup.close()
    app.dependency_overrides.clear()


def test_section5_tutor_and_mastery_flow(setup_database):
    client = TestClient(app)
    student_id = setup_database["student_id"]
    session_id = setup_database["session_id"]

    chat_response = client.post(
        "/api/v1/tutor/chat",
        json={
            "student_id": str(student_id),
            "session_id": str(session_id),
            "subject": "math",
            "sss_level": "SSS2",
            "term": 1,
            "topic_id": str(uuid4()),
            "message": "Explain linear equations with one example.",
        },
    )
    assert chat_response.status_code == 200
    assert "assistant_message" in chat_response.json()

    mastery_response = client.get(
        "/api/v1/learning/mastery",
        params={
            "student_id": str(student_id),
            "subject": "math",
            "term": 1,
            "view": "concept",
            "persist_snapshot": "true",
        },
    )
    assert mastery_response.status_code == 200
    mastery_json = mastery_response.json()
    assert mastery_json["subject"] == "math"
    assert mastery_json["view"] == "concept"
    assert "streak" in mastery_json
