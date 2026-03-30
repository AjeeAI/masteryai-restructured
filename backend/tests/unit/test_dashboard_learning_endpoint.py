from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.core.auth import get_current_user
from backend.main import app


def _override_user(user_id):
    def _inner():
        return SimpleNamespace(id=user_id, role="student")

    return _inner


def test_dashboard_bootstrap_requires_matching_student_id():
    auth_user_id = uuid4()
    payload_student_id = uuid4()
    client = TestClient(app)
    app.dependency_overrides[get_current_user] = _override_user(auth_user_id)

    response = client.get(
        "/api/v1/learning/dashboard/bootstrap",
        params={"student_id": str(payload_student_id)},
    )

    app.dependency_overrides.clear()
    assert response.status_code == 403


def test_dashboard_bootstrap_returns_active_subject_and_course(monkeypatch):
    student_id = uuid4()

    monkeypatch.setattr(
        "backend.endpoints.dashboard_learning.DashboardExperienceService.bootstrap",
        lambda self, **kwargs: {
            "student_id": str(student_id),
            "sss_level": "SSS2",
            "term": 2,
            "available_subjects": ["english", "math"],
            "active_subject": "english",
            "diagnostic_status": {
                "student_id": str(student_id),
                "onboarding_complete": True,
                "pending_subjects": [],
                "completed_subjects": ["english", "math"],
                "subject_runs": [],
            },
            "learning_gap_summary": {
                "weakest_concepts": [],
                "blocking_prerequisite_id": None,
                "blocking_prerequisite_label": None,
                "recommended_start_topic_id": str(uuid4()),
                "recommended_start_topic_title": "Comprehension Skills",
                "next_best_action": "Open Comprehension Skills",
                "rationale": "Diagnostic baseline points here first.",
                "question_count": 10,
                "completion_timestamp": "2026-03-19T10:00:00+00:00",
            },
            "initial_lesson_plan": {
                "recommended_topic_id": str(uuid4()),
                "recommended_topic_title": "Comprehension Skills",
                "prerequisite_repair_label": None,
                "next_best_action": "Open the recommended lesson",
                "rationale": "Diagnostic baseline points here first.",
            },
            "course_bootstrap": {
                "student_id": str(student_id),
                "subject": "english",
                "sss_level": "SSS2",
                "term": 2,
                "topics": [],
                "nodes": [],
                "edges": [],
                "next_step": None,
                "recent_evidence": None,
                "intervention_timeline": [],
                "recommendation_story": None,
                "map_error": None,
                "warmed_topic_ids": [],
                "cache_hit_topic_ids": [],
                "failed_topic_ids": [],
            },
        },
    )

    client = TestClient(app)
    app.dependency_overrides[get_current_user] = _override_user(student_id)
    response = client.get(
        "/api/v1/learning/dashboard/bootstrap",
        params={"student_id": str(student_id)},
    )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["active_subject"] == "english"
    assert body["diagnostic_status"]["onboarding_complete"] is True
    assert body["learning_gap_summary"]["recommended_start_topic_title"] == "Comprehension Skills"
    assert body["initial_lesson_plan"]["recommended_topic_title"] == "Comprehension Skills"
    assert body["course_bootstrap"]["subject"] == "english"


def test_dashboard_briefing_export_returns_student_path_story(monkeypatch):
    student_id = uuid4()

    monkeypatch.setattr(
        "backend.endpoints.dashboard_learning.DashboardExperienceService.get_path_briefing_export",
        lambda self, **kwargs: {
            "export_kind": "student_path_briefing",
            "student_id": str(student_id),
            "subject": "english",
            "sss_level": "SSS2",
            "term": 2,
            "title": "English learning path briefing",
            "subtitle": "Graph-backed student summary.",
            "generated_at": "2026-03-15T10:00:00+00:00",
            "file_name": "english-learning-path-briefing.md",
            "markdown": "# English learning path briefing",
            "sections": [{"title": "Graph signal", "items": ["Repair main idea first."]}],
        },
    )

    client = TestClient(app)
    app.dependency_overrides[get_current_user] = _override_user(student_id)
    response = client.get(
        "/api/v1/learning/dashboard/briefing/export",
        params={"student_id": str(student_id), "subject": "english"},
    )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["export_kind"] == "student_path_briefing"
    assert body["subject"] == "english"
