from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.core.auth import get_current_user
from backend.main import app


def _override_user(user_id):
    def _inner():
        return SimpleNamespace(id=user_id, role="student")
    return _inner


def test_lesson_prewarm_endpoint_requires_matching_student_id(monkeypatch):
    auth_user_id = uuid4()
    payload_student_id = uuid4()
    client = TestClient(app)
    app.dependency_overrides[get_current_user] = _override_user(auth_user_id)

    response = client.post(
        "/api/v1/learning/lesson/prewarm",
        json={
            "student_id": str(payload_student_id),
            "subject": "math",
            "sss_level": "SSS2",
            "term": 1,
            "topic_ids": [str(uuid4())],
        },
    )

    app.dependency_overrides.clear()
    assert response.status_code == 403


def test_lesson_prewarm_endpoint_returns_warm_result(monkeypatch):
    student_id = uuid4()
    calls = {"course": 0, "dashboard": 0}
    queued_job_id = uuid4()
    queued_scope_job_id = uuid4()

    monkeypatch.setattr(
        "backend.endpoints.lessons.LessonExperienceService.prewarm_related_topics",
        lambda **kwargs: {
            "warmed_topic_ids": [str(kwargs["topic_ids"][0])],
            "cache_hit_topic_ids": [],
            "failed_topic_ids": [],
        },
    )
    monkeypatch.setattr(
        "backend.endpoints.lessons.CourseExperienceService.prewarm_scope",
        lambda **kwargs: calls.__setitem__("course", calls["course"] + 1) or True,
    )
    monkeypatch.setattr(
        "backend.endpoints.lessons.DashboardExperienceService.prewarm",
        lambda **kwargs: calls.__setitem__("dashboard", calls["dashboard"] + 1) or True,
    )
    monkeypatch.setattr(
        "backend.endpoints.lessons.PrewarmJobService.enqueue_lesson_related_job",
        lambda **kwargs: queued_job_id,
    )
    monkeypatch.setattr(
        "backend.endpoints.lessons.PrewarmJobService.enqueue_course_scope_job",
        lambda **kwargs: queued_scope_job_id,
    )

    client = TestClient(app)
    app.dependency_overrides[get_current_user] = _override_user(student_id)
    topic_id = uuid4()

    response = client.post(
        "/api/v1/learning/lesson/prewarm",
        json={
            "student_id": str(student_id),
            "subject": "math",
            "sss_level": "SSS2",
            "term": 1,
            "topic_ids": [str(topic_id)],
        },
    )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["requested_topic_ids"] == [str(topic_id)]
    assert body["warmed_topic_ids"] == [str(topic_id)]
    assert body["queued_job_ids"] == [str(queued_job_id), str(queued_scope_job_id)]
    assert calls["course"] == 1
    assert calls["dashboard"] == 1
