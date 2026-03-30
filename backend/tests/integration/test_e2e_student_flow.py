import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.orm import sessionmaker

from backend.core.config import settings
from backend.core.database import Base, get_db
from backend.main import app
from backend.models.lesson import Lesson, LessonBlock
from backend.models.subject import Subject
from backend.models.topic import Topic
from backend.models.user import User
from backend.models.curriculum_version import CurriculumVersion
from backend.tests.integration.db_utils import resolve_test_database_url


TEST_DATABASE_URL = resolve_test_database_url(test_label="Section 8 E2E student flow")


engine = create_engine(
    TEST_DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"connect_timeout": int(os.getenv("TEST_DB_CONNECT_TIMEOUT", "5"))},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        try:
            db.close()
        except DBAPIError:
            pass


def _ensure_db_available() -> None:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except OperationalError as exc:
        pytest.skip(f"E2E student flow skipped: database unavailable ({exc})", allow_module_level=True)


@pytest.fixture(autouse=True)
def setup_database(monkeypatch):
    _ensure_db_available()
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    created_subject_ids = []
    subject_by_slug = {}
    for slug, name in [("math", "Mathematics"), ("english", "English"), ("civic", "Civic Education")]:
        subject = db.query(Subject).filter(Subject.slug == slug).first()
        if subject is None:
            subject = Subject(id=uuid4(), slug=slug, name=name)
            db.add(subject)
            db.flush()
            created_subject_ids.append(subject.id)
        subject_by_slug[slug] = subject

    topic_id = uuid4()
    curriculum_version = CurriculumVersion(
        id=uuid4(),
        version_name=f"e2e-student-version-{topic_id.hex[:6]}",
        subject="math",
        sss_level="SSS2",
        term=1,
        source_root="integration-test",
        source_file_count=1,
        status="published",
        metadata_payload={},
    )
    db.add(curriculum_version)
    db.flush()
    curriculum_version_id = curriculum_version.id
    lesson_id = uuid4()
    db.add(
        Topic(
            id=topic_id,
            subject_id=subject_by_slug["math"].id,
            sss_level="SSS2",
            term=1,
            title=f"E2E Linear Equations {topic_id.hex[:8]}",
            description="E2E seeded topic",
            is_approved=True,
            curriculum_version_id=curriculum_version_id,
        )
    )
    db.add(
        Lesson(
            id=lesson_id,
            topic_id=topic_id,
            title="E2E Lesson",
            summary="E2E lesson summary",
            estimated_duration_minutes=12,
        )
    )
    db.add_all(
        [
            LessonBlock(
                id=uuid4(),
                lesson_id=lesson_id,
                block_type="text",
                order_index=1,
                content={"text": "Solve by isolating x."},
            ),
            LessonBlock(
                id=uuid4(),
                lesson_id=lesson_id,
                block_type="example",
                order_index=2,
                content={"prompt": "2x + 4 = 10", "solution": "x = 3"},
            ),
        ]
    )
    db.commit()
    db.close()

    monkeypatch.setattr(settings, "ai_core_base_url", "")
    monkeypatch.setattr(settings, "ai_core_allow_fallback", True)
    async def _fake_generate_quiz_questions(**kwargs):
        count = int(kwargs.get("num_questions") or 1)
        questions = []
        for index in range(max(count, 1)):
            questions.append(
                {
                    "id": uuid4(),
                    "text": f"What is the value of x in 2x + {4 + index} = {10 + index}?",
                    "options": ["x = 2", "x = 3", "x = 4", "x = 5"],
                    "correct_answer": "B",
                    "concept_id": "math:sss2:t1:linear-equations",
                    "difficulty": kwargs.get("difficulty", "medium"),
                }
            )
        return questions

    monkeypatch.setattr(
        "backend.services.quiz_generate_service.generate_quiz_questions",
        _fake_generate_quiz_questions,
    )
    app.dependency_overrides[get_db] = override_get_db

    fixture_payload = {
        "topic_id": topic_id,
        "created_subject_ids": created_subject_ids,
        "curriculum_version_id": curriculum_version_id,
    }
    yield fixture_payload

    cleanup = TestingSessionLocal()
    cleanup.query(LessonBlock).filter(LessonBlock.lesson_id == lesson_id).delete(synchronize_session=False)
    cleanup.query(Lesson).filter(Lesson.id == lesson_id).delete(synchronize_session=False)
    cleanup.query(Topic).filter(Topic.id == topic_id).delete(synchronize_session=False)
    cleanup.query(CurriculumVersion).filter(
        CurriculumVersion.id == fixture_payload["curriculum_version_id"]
    ).delete(synchronize_session=False)
    cleanup.query(User).filter(User.email.like("e2e.student.%@example.com")).delete(synchronize_session=False)
    if created_subject_ids:
        cleanup.query(Subject).filter(Subject.id.in_(created_subject_ids)).delete(synchronize_session=False)
    cleanup.commit()
    cleanup.close()
    app.dependency_overrides.clear()


def _register_and_login_student(client: TestClient) -> tuple[str, str]:
    email = f"e2e.student.{uuid4()}@example.com"
    password = "StrongPass123!"

    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "role": "student",
            "first_name": "Olasquare",
            "last_name": "Adebayo",
            "display_name": "Olasquare",
        },
    )
    assert register_response.status_code == 201
    user_id = register_response.json()["user_id"]

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    return user_id, token


def test_e2e_student_flow(setup_database):
    topic_id = setup_database["topic_id"]
    client = TestClient(app)
    user_id, token = _register_and_login_student(client)
    headers = {"Authorization": f"Bearer {token}"}

    setup_profile = client.post(
        "/api/v1/students/profile/setup",
        json={
            "student_id": user_id,
            "sss_level": "SSS2",
            "subjects": ["math", "english", "civic"],
            "term": 1,
        },
        headers=headers,
    )
    assert setup_profile.status_code == 200

    profile = client.get("/api/v1/students/profile", headers=headers)
    assert profile.status_code == 200
    assert profile.json()["user_id"] == user_id

    update_preferences = client.put(
        f"/api/v1/users/{user_id}/preferences",
        json={"explanation_depth": "detailed", "examples_first": True, "pace": "normal"},
        headers=headers,
    )
    assert update_preferences.status_code == 200

    topics = client.get(
        "/api/v1/learning/topics",
        params={"student_id": user_id, "subject": "math", "term": 1, "include_unready": True},
    )
    assert topics.status_code == 200
    assert any(item["topic_id"] == str(topic_id) for item in topics.json())

    lesson = client.get(
        f"/api/v1/learning/topics/{topic_id}/lesson",
        params={"student_id": user_id},
        headers=headers,
    )
    assert lesson.status_code == 200, lesson.text

    activity = client.post(
        "/api/v1/learning/activity/log",
        json={
            "student_id": user_id,
            "subject": "math",
            "term": 1,
            "event_type": "lesson_viewed",
            "ref_id": str(topic_id),
            "duration_seconds": 180,
        },
        headers=headers,
    )
    assert activity.status_code == 201

    stats = client.get("/api/v1/students/stats", headers=headers)
    assert stats.status_code == 200

    start_session = client.post(
        "/api/v1/tutor/sessions/start",
        json={"student_id": user_id, "subject": "math", "term": 1},
        headers=headers,
    )
    assert start_session.status_code == 201
    session_id = start_session.json()["session_id"]

    chat = client.post(
        "/api/v1/tutor/chat",
        json={
            "student_id": user_id,
            "session_id": session_id,
            "subject": "math",
            "sss_level": "SSS2",
            "term": 1,
            "topic_id": str(topic_id),
            "message": "Explain linear equations with one example.",
        },
        headers=headers,
    )
    assert chat.status_code == 200
    assert "assistant_message" in chat.json()

    generate_quiz = client.post(
        "/api/v1/learning/quizzes/generate",
        json={
            "student_id": user_id,
            "subject": "math",
            "sss_level": "SSS2",
            "term": 1,
            "topic_id": str(topic_id),
            "purpose": "practice",
            "difficulty": "medium",
            "num_questions": 2,
        },
        headers=headers,
    )
    assert generate_quiz.status_code == 200
    quiz_data = generate_quiz.json()
    quiz_id = quiz_data["quiz_id"]
    questions = quiz_data["questions"]

    submit_quiz = client.post(
        f"/api/v1/learning/quizzes/{quiz_id}/submit",
        json={
            "student_id": user_id,
            "answers": [
                {"question_id": questions[0]["id"], "answer": "A"},
                {"question_id": questions[1]["id"], "answer": "B"},
            ],
            "time_taken_seconds": 90,
        },
        headers=headers,
    )
    assert submit_quiz.status_code == 200
    attempt_id = submit_quiz.json()["attempt_id"]

    results = client.get(
        f"/api/v1/learning/quizzes/{quiz_id}/results",
        params={"student_id": user_id, "attempt_id": attempt_id},
        headers=headers,
    )
    assert results.status_code == 200

    mastery = client.get(
        "/api/v1/learning/mastery",
        params={"student_id": user_id, "subject": "math", "term": 1, "view": "concept"},
        headers=headers,
    )
    assert mastery.status_code == 200

    history = client.get(
        f"/api/v1/tutor/sessions/{session_id}/history",
        params={"student_id": user_id},
        headers=headers,
    )
    assert history.status_code == 200
    assert len(history.json()["messages"]) >= 2

    end_session = client.post(
        f"/api/v1/tutor/sessions/{session_id}/end",
        params={"student_id": user_id},
        json={"end_reason": "completed"},
        headers=headers,
    )
    assert end_session.status_code == 200
