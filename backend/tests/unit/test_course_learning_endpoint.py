from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.core.auth import get_current_user
from backend.main import app


def _override_user(user_id):
    def _inner():
        return SimpleNamespace(id=user_id, role="student")

    return _inner


def test_course_bootstrap_requires_matching_student_id():
    auth_user_id = uuid4()
    payload_student_id = uuid4()
    client = TestClient(app)
    app.dependency_overrides[get_current_user] = _override_user(auth_user_id)

    response = client.get(
        "/api/v1/learning/course/bootstrap",
        params={
            "student_id": str(payload_student_id),
            "subject": "math",
            "term": 1,
        },
    )

    app.dependency_overrides.clear()
    assert response.status_code == 403


def test_course_bootstrap_returns_graph_ready_payload(monkeypatch):
    student_id = uuid4()

    monkeypatch.setattr(
        "backend.endpoints.course_learning.CourseExperienceService.bootstrap",
        lambda self, **kwargs: {
            "student_id": str(kwargs["student_id"]),
            "subject": kwargs["subject"],
            "sss_level": "SSS2",
            "term": kwargs["term"],
            "topics": [
                {
                    "topic_id": str(uuid4()),
                    "title": "Sequences and Series",
                    "description": "Graph-backed progression entry.",
                    "lesson_title": "Lesson: Sequences and Series",
                    "estimated_duration_minutes": 24,
                    "lesson_ready": True,
                    "lesson_unavailable_reason": None,
                    "sss_level": "SSS2",
                    "term": kwargs["term"],
                    "subject_id": str(uuid4()),
                    "status": "current",
                    "mastery_score": 0.42,
                    "concept_label": "Arithmetic Progression",
                    "graph_details": "Weakest focus: Arithmetic Progression",
                    "is_recommended": True,
                }
            ],
            "next_step": {
                "recommended_topic_id": str(uuid4()),
                "recommended_topic_title": "Sequences and Series",
                "recommended_concept_id": "math:sss2:t2:arithmetic-progression",
                "recommended_concept_label": "Arithmetic Progression",
                "reason": "Recommended next topic based on the weakest concept still below mastery threshold.",
                "prereq_gaps": [],
                "prereq_gap_labels": [],
                "scope_warning": None,
                "unmapped_topic_titles": [],
            },
            "recent_evidence": {
                "source": "practice",
                "created_at": "2026-03-12T10:00:00Z",
                "strongest_gain_concept_label": "Arithmetic Progression",
                "strongest_drop_concept_label": "Simple Interest",
                "summary": "Latest practice strengthened Arithmetic Progression but exposed a gap in Simple Interest.",
            },
            "intervention_timeline": [
                {
                    "kind": "quiz",
                    "source": "practice",
                    "source_label": "Quiz result",
                    "created_at": "2026-03-12T10:00:00Z",
                    "summary": "Quiz result strengthened Arithmetic Progression but exposed a gap in Simple Interest.",
                    "focus_concept_label": "Simple Interest",
                    "strongest_gain_concept_label": "Arithmetic Progression",
                    "strongest_drop_concept_label": "Simple Interest",
                    "action_label": "Review weak concept",
                }
            ],
            "recommendation_story": {
                "status": "advance_to_next",
                "headline": "Push into Sequences and Series next.",
                "supporting_reason": "Recommended next topic based on the weakest concept still below mastery threshold.",
                "blocking_prerequisite_label": None,
                "next_concept_label": "Arithmetic Progression",
                "evidence_summary": "Latest practice strengthened Arithmetic Progression but exposed a gap in Simple Interest.",
                "action_label": "Open recommended lesson",
            },
            "diagnostic_status": {
                "subject": kwargs["subject"],
                "status": "completed",
                "diagnostic_id": str(uuid4()),
                "question_count": 10,
                "recommended_start_topic_id": str(uuid4()),
                "recommended_start_topic_title": "Sequences and Series",
                "weakest_concepts": [],
                "blocking_prerequisite_id": None,
                "blocking_prerequisite_label": None,
                "completion_timestamp": "2026-03-19T10:00:00+00:00",
            },
            "learning_gap_summary": {
                "weakest_concepts": [],
                "blocking_prerequisite_id": None,
                "blocking_prerequisite_label": None,
                "recommended_start_topic_id": str(uuid4()),
                "recommended_start_topic_title": "Sequences and Series",
                "next_best_action": "Open Sequences and Series",
                "rationale": "Diagnostic baseline points here first.",
                "question_count": 10,
                "completion_timestamp": "2026-03-19T10:00:00+00:00",
            },
            "initial_lesson_plan": {
                "recommended_topic_id": str(uuid4()),
                "recommended_topic_title": "Sequences and Series",
                "prerequisite_repair_label": None,
                "next_best_action": "Open recommended lesson",
                "rationale": "Diagnostic baseline points here first.",
            },
            "map_error": None,
            "warmed_topic_ids": [],
            "cache_hit_topic_ids": [],
            "failed_topic_ids": [],
        },
    )

    client = TestClient(app)
    app.dependency_overrides[get_current_user] = _override_user(student_id)

    response = client.get(
        "/api/v1/learning/course/bootstrap",
        params={
            "student_id": str(student_id),
            "subject": "math",
            "term": 2,
        },
    )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["subject"] == "math"
    assert body["topics"][0]["status"] == "current"
    assert body["topics"][0]["concept_label"] == "Arithmetic Progression"
    assert body["next_step"]["recommended_concept_label"] == "Arithmetic Progression"
    assert body["recent_evidence"]["strongest_drop_concept_label"] == "Simple Interest"
    assert body["intervention_timeline"][0]["source_label"] == "Quiz result"
    assert body["recommendation_story"]["headline"] == "Push into Sequences and Series next."
    assert body["diagnostic_status"]["status"] == "completed"
    assert body["learning_gap_summary"]["recommended_start_topic_title"] == "Sequences and Series"
    assert body["initial_lesson_plan"]["recommended_topic_title"] == "Sequences and Series"


def test_latest_intervention_bootstrap_returns_recent_scope(monkeypatch):
    student_id = uuid4()

    monkeypatch.setattr(
        "backend.endpoints.course_learning.CourseExperienceService.latest_intervention_bootstrap",
        lambda self, *, student_id: {
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
    )

    client = TestClient(app)
    app.dependency_overrides[get_current_user] = _override_user(student_id)

    response = client.get(
        "/api/v1/learning/course/latest-intervention",
        params={"student_id": str(student_id)},
    )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["subject"] == "english"
    assert body["term"] == 2
