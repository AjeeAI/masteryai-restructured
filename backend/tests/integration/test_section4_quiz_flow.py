import os
from uuid import uuid4
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.auth import get_current_user
from backend.core.database import Base, get_db
from backend.main import app
from backend.models.subject import Subject
from backend.models.topic import Topic
from backend.models.user import User
from backend.tests.integration.db_utils import resolve_test_database_url


TEST_DATABASE_URL = resolve_test_database_url(test_label="Section 4 integration flow")


engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    student_id = uuid4()
    topic_id = uuid4()
    created_subject = False

    subject_row = db.query(Subject).filter(Subject.slug == "math").first()
    if subject_row is None:
        subject_row = Subject(id=uuid4(), slug="math", name="Mathematics")
        db.add(subject_row)
        db.flush()
        created_subject = True
    subject_id = subject_row.id

    db.add(
        User(
            id=student_id,
            email=f"section4.student.{student_id}@example.com",
            password_hash="hash",
            role="student",
            is_active=True,
        )
    )
    db.add(
        Topic(
            id=topic_id,
            subject_id=subject_id,
            sss_level="SSS2",
            term=1,
            title=f"Algebra Foundations {topic_id.hex[:8]}",
            description="Intro algebra",
            is_approved=True,
        )
    )
    db.commit()
    db.close()

    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=student_id)

    yield {"student_id": student_id, "topic_id": topic_id, "subject_id": subject_id, "created_subject": created_subject}

    cleanup = TestingSessionLocal()
    cleanup.query(Topic).filter(Topic.id == topic_id).delete(synchronize_session=False)
    if created_subject:
        cleanup.query(Subject).filter(Subject.id == subject_id).delete(synchronize_session=False)
    cleanup.query(User).filter(User.id == student_id).delete(synchronize_session=False)
    cleanup.commit()
    cleanup.close()
    app.dependency_overrides.pop(get_current_user, None)


def test_full_quiz_flow(setup_database):
    student_id = setup_database["student_id"]
    topic_id = setup_database["topic_id"]

    generate_payload = {
        "student_id": str(student_id),
        "subject": "math",
        "sss_level": "SSS2",
        "term": 1,
        "topic_id": str(topic_id),
        "purpose": "practice",
        "difficulty": "medium",
        "num_questions": 2,
    }
    gen_response = client.post("/api/v1/learning/quizzes/generate", json=generate_payload)
    assert gen_response.status_code == 200
    gen_data = gen_response.json()
    quiz_id = gen_data["quiz_id"]
    questions = gen_data["questions"]
    assert len(questions) == 2

    submit_payload = {
        "student_id": str(student_id),
        "answers": [
            {"question_id": questions[0]["id"], "answer": "A"},
            {"question_id": questions[1]["id"], "answer": "B"},
        ],
        "time_taken_seconds": 180,
    }
    submit_response = client.post(f"/api/v1/learning/quizzes/{quiz_id}/submit", json=submit_payload)
    assert submit_response.status_code == 200
    submit_data = submit_response.json()
    attempt_id = submit_data["attempt_id"]
    assert "score" in submit_data

    results_response = client.get(
        f"/api/v1/learning/quizzes/{quiz_id}/results",
        params={"student_id": str(student_id), "attempt_id": attempt_id},
    )
    assert results_response.status_code == 200
    results_data = results_response.json()
    assert "score" in results_data
    assert "concept_breakdown" in results_data
    assert "insights" in results_data
