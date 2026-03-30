from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.core.auth import get_current_user
from backend.main import app


def _override_user(user_id):
    def _inner():
        return SimpleNamespace(id=user_id, role="student")

    return _inner


def test_lesson_cockpit_requires_matching_student_id():
    auth_user_id = uuid4()
    payload_student_id = uuid4()
    client = TestClient(app)
    app.dependency_overrides[get_current_user] = _override_user(auth_user_id)

    response = client.post(
        "/api/v1/learning/lesson/cockpit",
        json={
            "student_id": str(payload_student_id),
            "subject": "math",
            "sss_level": "SSS2",
            "term": 2,
            "topic_id": str(uuid4()),
        },
    )

    app.dependency_overrides.clear()
    assert response.status_code == 403


def test_lesson_cockpit_returns_merged_payload(monkeypatch):
    student_id = uuid4()
    topic_id = uuid4()

    monkeypatch.setattr(
        "backend.endpoints.lessons.LessonCockpitService.bootstrap",
        lambda self, payload: {
            "student_id": str(payload.student_id),
            "topic_id": str(payload.topic_id),
            "subject": payload.subject,
            "sss_level": payload.sss_level,
            "term": payload.term,
            "topics": [],
            "next_step": None,
            "intervention_timeline": [],
            "map_error": None,
            "tutor_bootstrap": {
                "session_id": str(uuid4()),
                "session_started": True,
                "greeting": "Ready.",
                "topic_id": str(payload.topic_id),
                "lesson": {
                    "topic_id": str(payload.topic_id),
                    "title": "Lesson: Sequences and Series",
                    "summary": "Structured lesson.",
                    "estimated_duration_minutes": 18,
                    "content_blocks": [{"type": "text", "value": "Intro", "url": None}],
                    "covered_concepts": [],
                    "prerequisites": [],
                    "weakest_concepts": [],
                    "next_unlock": None,
                    "why_this_matters": "Builds later algebra.",
                    "assessment_ready": True,
                },
                "graph_context": {
                    "student_id": str(payload.student_id),
                    "subject": payload.subject,
                    "sss_level": payload.sss_level,
                    "term": payload.term,
                    "topic_id": str(payload.topic_id),
                    "topic_title": "Sequences and Series",
                    "overall_mastery": 0.42,
                    "current_concepts": [],
                    "prerequisite_concepts": [],
                    "downstream_concepts": [],
                    "weakest_concepts": [],
                    "graph_nodes": [],
                    "graph_edges": [],
                    "next_unlock": None,
                    "why_this_matters": "Builds later algebra.",
                },
                "suggested_actions": [],
                "pending_assessment": None,
                "next_unlock": None,
                "why_this_topic": "Builds later algebra.",
                "graph_nodes": [],
                "graph_edges": [],
                "assessment_ready": True,
            },
            "why_topic_detail": {
                "student_id": str(payload.student_id),
                "subject": payload.subject,
                "sss_level": payload.sss_level,
                "term": payload.term,
                "topic_id": str(payload.topic_id),
                "topic_title": "Sequences and Series",
                "explanation": "Builds later algebra.",
                "prerequisite_labels": [],
                "unlock_labels": [],
                "weakest_prerequisite_label": None,
                "recommended_next": None,
            },
            "warmed_topic_ids": [],
            "cache_hit_topic_ids": [],
            "failed_topic_ids": [],
        },
    )

    client = TestClient(app)
    app.dependency_overrides[get_current_user] = _override_user(student_id)
    response = client.post(
        "/api/v1/learning/lesson/cockpit",
        json={
            "student_id": str(student_id),
            "subject": "math",
            "sss_level": "SSS2",
            "term": 2,
            "topic_id": str(topic_id),
        },
    )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["topic_id"] == str(topic_id)
    assert body["tutor_bootstrap"]["lesson"]["title"] == "Lesson: Sequences and Series"
    assert body["intervention_timeline"] == []
    assert body["why_topic_detail"]["explanation"] == "Builds later algebra."
