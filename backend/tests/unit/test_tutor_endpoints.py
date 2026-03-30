from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.main import app


def _override_db():
    yield object()


def test_tutor_endpoints_chat_hint_explain(monkeypatch):
    student_id = uuid4()
    session_id = uuid4()

    def _override_user():
        return SimpleNamespace(id=student_id, role="student")

    class _FakeRepo:
        def session_exists_for_student(self, *, session_id, student_id):
            return True

        def add_message(self, *, session_id, role, content):
            return {"id": str(uuid4()), "role": role, "content": content}

    class _FakeService:
        async def chat(self, payload):
            return {
                "assistant_message": "Here is an explanation.",
                "citations": [],
                "actions": ["UPDATED_MASTERY_BASIC"],
                "recommendations": [{"type": "next_topic", "topic_id": None, "reason": "Keep practicing."}],
            }

        async def hint(self, payload):
            return {"hint": "Try elimination first.", "strategy": "guided_hint"}

        async def explain_mistake(self, payload):
            return {"explanation": "Rule mismatch.", "improvement_tip": "Apply the rule first."}

    class _FakeAssessmentService:
        async def start_assessment(self, payload):
            return {
                "assessment_id": str(uuid4()),
                "question": "What is a variable?",
                "concept_id": "math:sss2:t1:variables",
                "concept_label": "variables",
                "ideal_answer": "A symbol for an unknown value.",
                "hint": "Think of what x stands for.",
                "citations": [],
                "actions": ["ASSESSMENT_TARGET_CONCEPT"],
            }

        async def submit_assessment(self, payload):
            return {
                "assessment_id": str(payload.assessment_id),
                "is_correct": True,
                "score": 0.9,
                "feedback": "Correct answer.",
                "ideal_answer": "A symbol for an unknown value.",
                "concept_id": "math:sss2:t1:variables",
                "concept_label": "variables",
                "mastery_updated": True,
                "new_mastery": 0.62,
                "actions": ["MASTERED_CHECK_RECORDED"],
            }

    monkeypatch.setattr("backend.endpoints.tutor._service", lambda: _FakeService())
    monkeypatch.setattr("backend.endpoints.tutor._session_repo", lambda db: _FakeRepo())
    monkeypatch.setattr("backend.endpoints.tutor._assessment_service", lambda db: _FakeAssessmentService())

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    client = TestClient(app)

    chat_response = client.post(
        "/api/v1/tutor/chat",
        json={
            "student_id": str(student_id),
            "session_id": str(session_id),
            "subject": "math",
            "sss_level": "SSS2",
            "term": 1,
            "topic_id": str(uuid4()),
            "message": "Explain algebra",
        },
    )
    hint_response = client.post(
        "/api/v1/tutor/hint",
        json={
            "student_id": str(student_id),
            "session_id": str(session_id),
            "quiz_id": str(uuid4()),
            "question_id": "q1",
            "subject": "math",
            "sss_level": "SSS2",
            "term": 1,
            "topic_id": str(uuid4()),
            "message": "help me",
        },
    )
    explain_response = client.post(
        "/api/v1/tutor/explain-mistake",
        json={
            "student_id": str(student_id),
            "session_id": str(session_id),
            "subject": "math",
            "sss_level": "SSS2",
            "term": 1,
            "topic_id": str(uuid4()),
            "question": "2+2=?",
            "student_answer": "5",
            "correct_answer": "4",
        },
    )
    assessment_start_response = client.post(
        "/api/v1/tutor/assessment/start",
        json={
            "student_id": str(student_id),
            "session_id": str(session_id),
            "subject": "math",
            "sss_level": "SSS2",
            "term": 1,
            "topic_id": str(uuid4()),
            "difficulty": "medium",
        },
    )
    assessment_submit_response = client.post(
        "/api/v1/tutor/assessment/submit",
        json={
            "student_id": str(student_id),
            "session_id": str(session_id),
            "assessment_id": str(uuid4()),
            "subject": "math",
            "sss_level": "SSS2",
            "term": 1,
            "topic_id": str(uuid4()),
            "answer": "A variable is an unknown value.",
        },
    )

    app.dependency_overrides.clear()

    assert chat_response.status_code == 200
    assert hint_response.status_code == 200
    assert explain_response.status_code == 200
    assert assessment_start_response.status_code == 200
    assert assessment_submit_response.status_code == 200
    assert chat_response.json()["assistant_message"]


def test_tutor_chat_rejects_mismatched_student_id(monkeypatch):
    auth_user_id = uuid4()
    payload_student_id = uuid4()

    def _override_user():
        return SimpleNamespace(id=auth_user_id, role="student")

    class _FakeRepo:
        def session_exists_for_student(self, *, session_id, student_id):
            return True

        def add_message(self, *, session_id, role, content):
            return {"id": str(uuid4())}

    class _FakeService:
        async def chat(self, payload):
            return {
                "assistant_message": "ok",
                "citations": [],
                "actions": [],
                "recommendations": [],
            }

    monkeypatch.setattr("backend.endpoints.tutor._service", lambda: _FakeService())
    monkeypatch.setattr("backend.endpoints.tutor._session_repo", lambda db: _FakeRepo())

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    client = TestClient(app)

    response = client.post(
        "/api/v1/tutor/chat",
        json={
            "student_id": str(payload_student_id),
            "session_id": str(uuid4()),
            "subject": "english",
            "sss_level": "SSS1",
            "term": 1,
            "message": "Explain concord",
        },
    )

    app.dependency_overrides.clear()
    assert response.status_code == 403
