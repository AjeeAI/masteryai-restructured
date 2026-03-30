from uuid import UUID
from fastapi.testclient import TestClient

from backend.core.telemetry import reset_telemetry_snapshot
from backend.main import app
from backend.models.student_concept_mastery import StudentConceptMastery
from backend.services.system_health_service import SystemHealthService
from backend.tests.integration.test_section8_graph_first_flow import (
    TestingSessionLocal,
    _register_and_login_student,
    setup_graph_first_scope,
)


def test_section10_runtime_graph_story_flow(setup_graph_first_scope, monkeypatch):
    reset_telemetry_snapshot()
    monkeypatch.setattr(SystemHealthService, "_check_postgres", lambda self: {"status": "ok"})
    monkeypatch.setattr(SystemHealthService, "_check_schema", lambda self: {"status": "ok"})
    monkeypatch.setattr(SystemHealthService, "_check_redis", lambda self: {"status": "not_configured"})
    monkeypatch.setattr(SystemHealthService, "_check_neo4j", lambda self: {"status": "not_configured"})
    monkeypatch.setattr(SystemHealthService, "_check_vector_db", lambda self: {"status": "ok"})
    monkeypatch.setattr(SystemHealthService, "_check_llm_api", lambda self: {"status": "configured"})

    client = TestClient(app)
    user_id, token = _register_and_login_student(client)
    headers = {"Authorization": f"Bearer {token}"}

    subject = setup_graph_first_scope["subject"]
    sss_level = setup_graph_first_scope["sss_level"]
    term = setup_graph_first_scope["term"]
    target_topic_id = setup_graph_first_scope["target_topic_id"]
    prereq_concept_id = setup_graph_first_scope["prereq_concept_id"]
    target_concept_id = setup_graph_first_scope["target_concept_id"]

    profile_response = client.post(
        "/api/v1/students/profile/setup",
        json={
            "student_id": user_id,
            "sss_level": sss_level,
            "subjects": [subject],
            "term": term,
        },
        headers=headers,
    )
    assert profile_response.status_code == 200

    seed_db = TestingSessionLocal()
    seed_db.add(
        StudentConceptMastery(
            student_id=UUID(user_id),
            subject=subject,
            sss_level=sss_level,
            term=term,
            concept_id=prereq_concept_id,
            mastery_score=0.55,
            source="diagnostic",
        )
    )
    seed_db.commit()
    seed_db.close()

    dashboard_before = client.get(
        "/api/v1/learning/dashboard/bootstrap",
        params={"student_id": user_id},
        headers=headers,
    )
    assert dashboard_before.status_code == 200
    dashboard_before_json = dashboard_before.json()
    assert dashboard_before_json["active_subject"] == subject

    course_before = client.get(
        "/api/v1/learning/course/bootstrap",
        params={"student_id": user_id, "subject": subject, "term": term},
        headers=headers,
    )
    assert course_before.status_code == 200
    course_before_json = course_before.json()
    assert course_before_json["subject"] == subject
    assert course_before_json["recommendation_story"] is not None

    session_bootstrap = client.post(
        "/api/v1/tutor/session/bootstrap",
        json={
            "student_id": user_id,
            "subject": subject,
            "sss_level": sss_level,
            "term": term,
            "topic_id": str(target_topic_id),
        },
        headers=headers,
    )
    assert session_bootstrap.status_code == 200
    session_bootstrap_json = session_bootstrap.json()
    session_id = session_bootstrap_json["session_id"]

    lesson_cockpit = client.post(
        "/api/v1/learning/lesson/cockpit",
        json={
            "student_id": user_id,
            "subject": subject,
            "sss_level": sss_level,
            "term": term,
            "topic_id": str(target_topic_id),
            "session_id": session_id,
        },
        headers=headers,
    )
    assert lesson_cockpit.status_code == 200

    assessment_start = client.post(
        "/api/v1/tutor/assessment/start",
        json={
            "student_id": user_id,
            "session_id": session_id,
            "subject": subject,
            "sss_level": sss_level,
            "term": term,
            "topic_id": str(target_topic_id),
            "focus_concept_id": prereq_concept_id,
            "focus_concept_label": "Graph prerequisite",
            "difficulty": "medium",
        },
        headers=headers,
    )
    assert assessment_start.status_code == 200
    assessment_start_json = assessment_start.json()

    assessment_submit = client.post(
        "/api/v1/tutor/assessment/submit",
        json={
            "student_id": user_id,
            "session_id": session_id,
            "assessment_id": assessment_start_json["assessment_id"],
            "subject": subject,
            "sss_level": sss_level,
            "term": term,
            "topic_id": str(target_topic_id),
            "answer": "State the prerequisite clearly, then show a short valid example before moving to the target step.",
        },
        headers=headers,
    )
    assert assessment_submit.status_code == 200
    assessment_submit_json = assessment_submit.json()
    assert assessment_submit_json["graph_remediation"]["focus_concept_id"] == prereq_concept_id

    generate_quiz = client.post(
        "/api/v1/learning/quizzes/generate",
        json={
            "student_id": user_id,
            "subject": subject,
            "sss_level": sss_level,
            "term": term,
            "topic_id": str(target_topic_id),
            "purpose": "practice",
            "difficulty": "medium",
            "num_questions": 1,
        },
        headers=headers,
    )
    assert generate_quiz.status_code == 200
    quiz_json = generate_quiz.json()
    assert quiz_json["questions"][0]["concept_id"] == target_concept_id

    submit_quiz = client.post(
        f"/api/v1/learning/quizzes/{quiz_json['quiz_id']}/submit",
        json={
            "student_id": user_id,
            "answers": [{"question_id": quiz_json["questions"][0]["id"], "answer": "B"}],
            "time_taken_seconds": 84,
        },
        headers=headers,
    )
    assert submit_quiz.status_code == 200
    attempt_id = submit_quiz.json()["attempt_id"]

    quiz_results = client.get(
        f"/api/v1/learning/quizzes/{quiz_json['quiz_id']}/results",
        params={"student_id": user_id, "attempt_id": attempt_id},
        headers=headers,
    )
    assert quiz_results.status_code == 200
    quiz_results_json = quiz_results.json()
    assert quiz_results_json["concept_breakdown"][0]["concept_id"] == target_concept_id

    latest_intervention = client.get(
        "/api/v1/learning/course/latest-intervention",
        params={"student_id": user_id},
        headers=headers,
    )
    assert latest_intervention.status_code == 200
    latest_intervention_json = latest_intervention.json()
    assert latest_intervention_json["subject"] == subject
    assert len(latest_intervention_json["intervention_timeline"]) >= 2
    assert latest_intervention_json["recent_evidence"]["source"] == "practice"
    assert latest_intervention_json["recommendation_story"] is not None

    dashboard_after = client.get(
        "/api/v1/learning/dashboard/bootstrap",
        params={"student_id": user_id},
        headers=headers,
    )
    assert dashboard_after.status_code == 200
    dashboard_after_json = dashboard_after.json()
    assert dashboard_after_json["active_subject"] == subject
    assert dashboard_after_json["course_bootstrap"]["recent_evidence"]["source"] == "practice"
    assert dashboard_after_json["course_bootstrap"]["recommendation_story"] is not None

    health = client.get("/api/v1/system/health")
    assert health.status_code == 200
    health_json = health.json()
    assert health_json["status"] == "ok"
    assert health_json["runtime"]["status"] == "ok"
    runtime_events = health_json["runtime"]["telemetry"]["events"]
    expected_events = {
        "dashboard.bootstrap",
        "course.bootstrap",
        "lesson.bootstrap",
        "lesson.cockpit.bootstrap",
        "tutor.session.bootstrap",
        "tutor.assessment.start",
        "tutor.assessment.submit",
        "quiz.generate",
        "quiz.submit",
        "quiz.results",
    }
    assert expected_events.issubset(set(runtime_events))
    assert health_json["runtime"]["caches"]["lesson_experience"]["topic_snapshot_cache"]["ttl_seconds"] > 0
    assert health_json["runtime"]["caches"]["lesson_cockpit"]["bootstrap_cache"]["ttl_seconds"] > 0
