import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.core.config import settings
from backend.core.database import Base, get_db
from backend.core.telemetry import reset_telemetry_snapshot
from backend.main import app
from backend.models.curriculum_topic_map import CurriculumTopicMap
from backend.models.curriculum_version import CurriculumVersion
from backend.models.lesson import Lesson, LessonBlock
from backend.models.prewarm_job import PrewarmJob
from backend.models.subject import Subject
from backend.models.topic import Topic
from backend.models.user import User
from backend.services.course_experience_service import _COURSE_BOOTSTRAP_CACHE
from backend.services.dashboard_experience_service import _DASHBOARD_BOOTSTRAP_CACHE
from backend.services.lesson_experience_service import _BOOTSTRAP_CACHE, _TOPIC_SNAPSHOT_CACHE
from backend.services.prewarm_job_service import PrewarmJobService
from backend.services.system_health_service import SystemHealthService
from backend.tests.integration.test_section8_graph_first_flow import (
    TestingSessionLocal,
    USER_EMAIL_PREFIX,
    _pick_empty_scope,
    _register_and_login_student,
    engine,
    override_get_db,
)


@pytest.fixture()
def setup_prewarm_scope(monkeypatch):
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    scope = _pick_empty_scope(db)
    subject = scope["subject"]
    sss_level = scope["sss_level"]
    term = scope["term"]
    subject_row = scope["subject_row"]
    token = uuid4().hex[:8]

    curriculum_version = CurriculumVersion(
        id=uuid4(),
        version_name=f"prewarm-{subject}-{sss_level.lower()}-t{term}-{token}",
        subject=subject,
        sss_level=sss_level,
        term=term,
        source_root="integration-test-prewarm",
        source_file_count=2,
        status="published",
        metadata_payload={},
    )
    db.add(curriculum_version)
    db.flush()

    prereq_topic = Topic(
        id=uuid4(),
        subject_id=subject_row.id,
        sss_level=sss_level,
        term=term,
        title=f"Prewarm Prerequisite {token}",
        description="Prerequisite topic used to validate queue-backed prewarming.",
        curriculum_version_id=curriculum_version.id,
        is_approved=True,
    )
    target_topic = Topic(
        id=uuid4(),
        subject_id=subject_row.id,
        sss_level=sss_level,
        term=term,
        title=f"Prewarm Target {token}",
        description="Target topic used to validate queue-backed prewarming.",
        curriculum_version_id=curriculum_version.id,
        is_approved=True,
    )
    db.add_all([prereq_topic, target_topic])
    db.flush()

    prereq_concept_id = f"{subject}:{sss_level.lower()}:t{term}:prewarm-prerequisite"
    target_concept_id = f"{subject}:{sss_level.lower()}:t{term}:prewarm-target"
    db.add_all(
        [
            CurriculumTopicMap(
                id=uuid4(),
                version_id=curriculum_version.id,
                topic_id=prereq_topic.id,
                concept_id=prereq_concept_id,
                prereq_concept_ids=[],
                confidence=0.95,
                is_manual_override=False,
                created_by=None,
            ),
            CurriculumTopicMap(
                id=uuid4(),
                version_id=curriculum_version.id,
                topic_id=target_topic.id,
                concept_id=target_concept_id,
                prereq_concept_ids=[prereq_concept_id],
                confidence=0.97,
                is_manual_override=False,
                created_by=None,
            ),
        ]
    )
    db.flush()

    prereq_lesson = Lesson(
        id=uuid4(),
        topic_id=prereq_topic.id,
        title=f"Lesson: {prereq_topic.title}",
        summary="Prerequisite lesson body for queue prewarm coverage.",
        estimated_duration_minutes=10,
    )
    target_lesson = Lesson(
        id=uuid4(),
        topic_id=target_topic.id,
        title=f"Lesson: {target_topic.title}",
        summary="Target lesson body for queue prewarm coverage.",
        estimated_duration_minutes=12,
    )
    db.add_all([prereq_lesson, target_lesson])
    db.flush()
    db.add_all(
        [
            LessonBlock(
                id=uuid4(),
                lesson_id=prereq_lesson.id,
                block_type="text",
                order_index=1,
                content={"text": "Define the prerequisite clearly before applying it."},
            ),
            LessonBlock(
                id=uuid4(),
                lesson_id=target_lesson.id,
                block_type="text",
                order_index=1,
                content={"text": "Apply the prerequisite idea to the target topic."},
            ),
        ]
    )
    db.commit()
    prereq_topic_id = prereq_topic.id
    target_topic_id = target_topic.id
    curriculum_version_id = curriculum_version.id
    prereq_lesson_id = prereq_lesson.id
    target_lesson_id = target_lesson.id
    db.close()

    monkeypatch.setattr(settings, "prewarm_queue_enabled", True)
    monkeypatch.setattr(settings, "prewarm_worker_enabled", False)
    monkeypatch.setattr(
        "backend.services.course_experience_service.RagRetrieveService.topic_has_chunks",
        lambda self, **kwargs: True,
    )
    monkeypatch.setattr(SystemHealthService, "_check_postgres", lambda self: {"status": "ok"})
    monkeypatch.setattr(SystemHealthService, "_check_schema", lambda self: {"status": "ok"})
    monkeypatch.setattr(SystemHealthService, "_check_redis", lambda self: {"status": "not_configured"})
    monkeypatch.setattr(SystemHealthService, "_check_neo4j", lambda self: {"status": "not_configured"})
    monkeypatch.setattr(SystemHealthService, "_check_vector_db", lambda self: {"status": "ok"})
    monkeypatch.setattr(SystemHealthService, "_check_llm_api", lambda self: {"status": "configured"})
    app.dependency_overrides[get_db] = override_get_db

    yield {
        "subject": subject,
        "sss_level": sss_level,
        "term": term,
        "prereq_topic_id": prereq_topic_id,
        "target_topic_id": target_topic_id,
        "curriculum_version_id": curriculum_version_id,
        "created_subject_ids": scope["created_subject_ids"],
        "prereq_lesson_id": prereq_lesson_id,
        "target_lesson_id": target_lesson_id,
    }

    cleanup = TestingSessionLocal()
    try:
        created_users = cleanup.query(User).filter(User.email.like(f"{USER_EMAIL_PREFIX}%")).all()
        for row in created_users:
            cleanup.query(PrewarmJob).filter(
                PrewarmJob.payload["student_id"].astext == str(row.id)
            ).delete(synchronize_session=False)
        cleanup.query(LessonBlock).filter(
            LessonBlock.lesson_id.in_([prereq_lesson_id, target_lesson_id])
        ).delete(synchronize_session=False)
        cleanup.query(Lesson).filter(
            Lesson.id.in_([prereq_lesson_id, target_lesson_id])
        ).delete(synchronize_session=False)
        cleanup.query(CurriculumTopicMap).filter(
            CurriculumTopicMap.version_id == curriculum_version_id
        ).delete(synchronize_session=False)
        cleanup.query(Topic).filter(
            Topic.id.in_([prereq_topic_id, target_topic_id])
        ).delete(synchronize_session=False)
        cleanup.query(CurriculumVersion).filter(
            CurriculumVersion.id == curriculum_version_id
        ).delete(synchronize_session=False)
        if scope["created_subject_ids"]:
            cleanup.query(Subject).filter(Subject.id.in_(scope["created_subject_ids"])).delete(synchronize_session=False)
        cleanup.query(User).filter(User.email.like(f"{USER_EMAIL_PREFIX}%")).delete(synchronize_session=False)
        cleanup.commit()
    finally:
        cleanup.close()
    app.dependency_overrides.clear()
    _TOPIC_SNAPSHOT_CACHE.clear()
    _BOOTSTRAP_CACHE.clear()
    _COURSE_BOOTSTRAP_CACHE.clear()
    _DASHBOARD_BOOTSTRAP_CACHE.clear()


def test_section9_prewarm_queue_flow(setup_prewarm_scope, monkeypatch):
    _TOPIC_SNAPSHOT_CACHE.clear()
    _BOOTSTRAP_CACHE.clear()
    _COURSE_BOOTSTRAP_CACHE.clear()
    _DASHBOARD_BOOTSTRAP_CACHE.clear()
    reset_telemetry_snapshot()

    client = TestClient(app)
    user_id, token = _register_and_login_student(client)
    headers = {"Authorization": f"Bearer {token}"}

    subject = setup_prewarm_scope["subject"]
    sss_level = setup_prewarm_scope["sss_level"]
    term = setup_prewarm_scope["term"]
    target_topic_id = setup_prewarm_scope["target_topic_id"]
    prereq_topic_id = setup_prewarm_scope["prereq_topic_id"]

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

    prewarm_response = client.post(
        "/api/v1/learning/lesson/prewarm",
        json={
            "student_id": user_id,
            "subject": subject,
            "sss_level": sss_level,
            "term": term,
            "topic_ids": [str(target_topic_id), str(prereq_topic_id)],
        },
        headers=headers,
    )
    assert prewarm_response.status_code == 200, prewarm_response.text
    prewarm_json = prewarm_response.json()
    assert len(prewarm_json["queued_job_ids"]) >= 2

    _TOPIC_SNAPSHOT_CACHE.clear()
    _BOOTSTRAP_CACHE.clear()
    _COURSE_BOOTSTRAP_CACHE.clear()
    _DASHBOARD_BOOTSTRAP_CACHE.clear()

    health_before = client.get("/api/v1/system/health")
    assert health_before.status_code == 200
    health_before_json = health_before.json()
    assert health_before_json["checks"]["prewarm_queue"]["status"] == "ok"
    assert int(health_before_json["checks"]["prewarm_queue"]["counts"]["queued"]) >= 2

    monkeypatch.setattr(
        "backend.services.prewarm_job_service.PrewarmJobService._process_lesson_related_job",
        staticmethod(
            lambda payload: (
                _TOPIC_SNAPSHOT_CACHE.__setitem__("queue-test-topic", (time.time(), {"payload": payload})),
                _BOOTSTRAP_CACHE.__setitem__("queue-test-bootstrap", (time.time(), {"payload": payload})),
            )
        ),
    )
    monkeypatch.setattr(
        "backend.services.prewarm_job_service.PrewarmJobService._process_course_scope_job",
        staticmethod(
            lambda payload: (
                _COURSE_BOOTSTRAP_CACHE.__setitem__("queue-test-course", (time.time(), {"payload": payload})),
                _DASHBOARD_BOOTSTRAP_CACHE.__setitem__("queue-test-dashboard", (time.time(), {"payload": payload})),
            )
        ),
    )

    processed = PrewarmJobService.process_once(batch_size=10)
    assert processed >= 2

    health_after = client.get("/api/v1/system/health")
    assert health_after.status_code == 200
    health_after_json = health_after.json()
    assert int(health_after_json["checks"]["prewarm_queue"]["counts"]["queued"]) == 0
    assert int(health_after_json["checks"]["prewarm_queue"]["counts"]["running"]) == 0
    assert int(health_after_json["checks"]["prewarm_queue"]["counts"]["completed"]) >= 2

    assert _TOPIC_SNAPSHOT_CACHE
    assert _COURSE_BOOTSTRAP_CACHE
    assert _DASHBOARD_BOOTSTRAP_CACHE

    course_bootstrap = client.get(
        "/api/v1/learning/course/bootstrap",
        params={"student_id": user_id, "subject": subject, "term": term},
        headers=headers,
    )
    assert course_bootstrap.status_code == 200

    dashboard_bootstrap = client.get(
        "/api/v1/learning/dashboard/bootstrap",
        params={"student_id": user_id, "subject": subject},
        headers=headers,
    )
    assert dashboard_bootstrap.status_code == 200

    lesson_bootstrap = client.post(
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
    assert lesson_bootstrap.status_code == 200
    lesson_bootstrap_json = lesson_bootstrap.json()

    lesson_cockpit = client.post(
        "/api/v1/learning/lesson/cockpit",
        json={
            "student_id": user_id,
            "subject": subject,
            "sss_level": sss_level,
            "term": term,
            "topic_id": str(target_topic_id),
            "session_id": lesson_bootstrap_json["session_id"],
        },
        headers=headers,
    )
    assert lesson_cockpit.status_code == 200

    health_runtime = client.get("/api/v1/system/health")
    assert health_runtime.status_code == 200
    health_runtime_json = health_runtime.json()
    assert health_runtime_json["runtime"]["status"] == "ok"
    assert int(health_runtime_json["runtime"]["telemetry"]["event_count"]) >= 3
    runtime_events = health_runtime_json["runtime"]["telemetry"]["events"]
    assert "course.bootstrap" in runtime_events
    assert "dashboard.bootstrap" in runtime_events
    assert "lesson.bootstrap" in runtime_events
    assert "lesson.cockpit.bootstrap" in runtime_events
    assert (
        health_runtime_json["runtime"]["caches"]["lesson_experience"]["topic_snapshot_cache"]["entries"] >= 1
    )
    assert health_runtime_json["runtime"]["caches"]["lesson_cockpit"]["bootstrap_cache"]["entries"] >= 1
