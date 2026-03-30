import os
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.orm import sessionmaker

from backend.core.database import Base, get_db
from backend.main import app
from backend.models.activity import ActivityLog
from backend.models.class_enrollment import ClassEnrollment
from backend.models.curriculum_topic_map import CurriculumTopicMap
from backend.models.curriculum_version import CurriculumVersion
from backend.models.mastery_update_event import MasteryUpdateEvent
from backend.models.student_concept_mastery import StudentConceptMastery
from backend.models.subject import Subject
from backend.models.teacher_assignment import TeacherAssignment
from backend.models.teacher_class import TeacherClass
from backend.models.teacher_intervention import TeacherIntervention
from backend.models.topic import Topic
from backend.models.user import User
from backend.tests.integration.db_utils import resolve_test_database_url


TEST_DATABASE_URL = resolve_test_database_url(test_label="Section 8 E2E teacher flow")


engine = create_engine(
    TEST_DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"connect_timeout": int(os.getenv("TEST_DB_CONNECT_TIMEOUT", "5"))},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
USER_TEACHER_PREFIX = "e2e.teacher.section8."
USER_STUDENT_PREFIX = "e2e.student.section8."


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        try:
            db.close()
        except DBAPIError:
            pass


def _register_and_login_user(
    client: TestClient,
    *,
    role: str,
    email_prefix: str,
    first_name: str,
    last_name: str,
    display_name: str,
) -> tuple[str, str]:
    email = f"{email_prefix}{uuid4()}@example.com"
    password = "StrongPass123!"

    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "role": role,
            "first_name": first_name,
            "last_name": last_name,
            "display_name": display_name,
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


def _ensure_db_available() -> None:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except OperationalError as exc:
        pytest.skip(f"E2E teacher flow skipped: database unavailable ({exc})", allow_module_level=True)


@pytest.fixture(autouse=True)
def setup_database():
    _ensure_db_available()
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    created_subject_ids = []
    subject = db.query(Subject).filter(Subject.slug == "math").first()
    if subject is None:
        subject = Subject(id=uuid4(), slug="math", name="Mathematics")
        db.add(subject)
        db.flush()
        created_subject_ids.append(subject.id)

    token = uuid4().hex[:8]
    curriculum_version = CurriculumVersion(
        id=uuid4(),
        version_name=f"e2e-teacher-version-{token}",
        subject="math",
        sss_level="SSS1",
        term=1,
        source_root="integration-test",
        source_file_count=2,
        status="published",
        metadata_payload={},
    )
    db.add(curriculum_version)
    db.flush()
    curriculum_version_id = curriculum_version.id

    prereq_topic = Topic(
        id=uuid4(),
        subject_id=subject.id,
        sss_level="SSS1",
        term=1,
        title=f"Foundations {token}",
        description="E2E teacher flow prerequisite topic.",
        is_approved=True,
        curriculum_version_id=curriculum_version_id,
    )
    target_topic = Topic(
        id=uuid4(),
        subject_id=subject.id,
        sss_level="SSS1",
        term=1,
        title=f"Applications {token}",
        description="E2E teacher flow target topic.",
        is_approved=True,
        curriculum_version_id=curriculum_version_id,
    )
    db.add_all([prereq_topic, target_topic])
    db.flush()
    prereq_topic_id = prereq_topic.id
    target_topic_id = target_topic.id

    prereq_concept_id = f"math:sss1:t1:foundations-{token}"
    target_concept_id = f"math:sss1:t1:applications-{token}"
    db.add_all(
        [
            CurriculumTopicMap(
                id=uuid4(),
                version_id=curriculum_version_id,
                topic_id=prereq_topic_id,
                concept_id=prereq_concept_id,
                prereq_concept_ids=[],
                confidence=0.98,
                is_manual_override=False,
                created_by=None,
            ),
            CurriculumTopicMap(
                id=uuid4(),
                version_id=curriculum_version_id,
                topic_id=target_topic_id,
                concept_id=target_concept_id,
                prereq_concept_ids=[prereq_concept_id],
                confidence=0.99,
                is_manual_override=False,
                created_by=None,
            ),
        ]
    )
    db.commit()
    db.close()

    app.dependency_overrides[get_db] = override_get_db

    yield {
        "subject": "math",
        "sss_level": "SSS1",
        "term": 1,
        "prereq_concept_id": prereq_concept_id,
        "target_concept_id": target_concept_id,
        "topic_ids": [prereq_topic_id, target_topic_id],
        "version_id": curriculum_version_id,
        "created_subject_ids": created_subject_ids,
    }

    cleanup = TestingSessionLocal()
    teacher_rows = cleanup.query(User).filter(User.email.like(f"{USER_TEACHER_PREFIX}%")).all()
    student_rows = cleanup.query(User).filter(User.email.like(f"{USER_STUDENT_PREFIX}%")).all()
    teacher_ids = [row.id for row in teacher_rows]
    student_ids = [row.id for row in student_rows]

    if student_ids:
        cleanup.query(ActivityLog).filter(ActivityLog.student_id.in_(student_ids)).delete(synchronize_session=False)
        cleanup.query(MasteryUpdateEvent).filter(MasteryUpdateEvent.student_id.in_(student_ids)).delete(
            synchronize_session=False
        )
        cleanup.query(StudentConceptMastery).filter(StudentConceptMastery.student_id.in_(student_ids)).delete(
            synchronize_session=False
        )

    if teacher_ids:
        class_ids = [
            row.id for row in cleanup.query(TeacherClass.id).filter(TeacherClass.teacher_id.in_(teacher_ids)).all()
        ]
        if class_ids:
            cleanup.query(ClassEnrollment).filter(ClassEnrollment.class_id.in_(class_ids)).delete(
                synchronize_session=False
            )
            cleanup.query(TeacherAssignment).filter(TeacherAssignment.class_id.in_(class_ids)).delete(
                synchronize_session=False
            )
            cleanup.query(TeacherIntervention).filter(TeacherIntervention.class_id.in_(class_ids)).delete(
                synchronize_session=False
            )
            cleanup.query(TeacherClass).filter(TeacherClass.id.in_(class_ids)).delete(synchronize_session=False)

        cleanup.query(TeacherAssignment).filter(TeacherAssignment.teacher_id.in_(teacher_ids)).delete(
            synchronize_session=False
        )
        cleanup.query(TeacherIntervention).filter(TeacherIntervention.teacher_id.in_(teacher_ids)).delete(
            synchronize_session=False
        )

    if teacher_ids:
        cleanup.query(User).filter(User.id.in_(teacher_ids)).delete(synchronize_session=False)
    if student_ids:
        cleanup.query(User).filter(User.id.in_(student_ids)).delete(synchronize_session=False)

    cleanup.query(CurriculumTopicMap).filter(CurriculumTopicMap.version_id == curriculum_version_id).delete(
        synchronize_session=False
    )
    cleanup.query(Topic).filter(Topic.id.in_([prereq_topic_id, target_topic_id])).delete(synchronize_session=False)
    cleanup.query(CurriculumVersion).filter(CurriculumVersion.id == curriculum_version_id).delete(
        synchronize_session=False
    )
    if created_subject_ids:
        cleanup.query(Subject).filter(Subject.id.in_(created_subject_ids)).delete(synchronize_session=False)
    cleanup.commit()
    cleanup.close()
    app.dependency_overrides.clear()


def test_e2e_teacher_flow(setup_database):
    client = TestClient(app)

    _teacher_id, token = _register_and_login_user(
        client,
        role="teacher",
        email_prefix=USER_TEACHER_PREFIX,
        first_name="Section",
        last_name="Teacher",
        display_name="Section Teacher",
    )
    student_one_id, _ = _register_and_login_user(
        client,
        role="student",
        email_prefix=USER_STUDENT_PREFIX,
        first_name="Student",
        last_name="One",
        display_name="Student One",
    )
    student_two_id, _ = _register_and_login_user(
        client,
        role="student",
        email_prefix=USER_STUDENT_PREFIX,
        first_name="Student",
        last_name="Two",
        display_name="Student Two",
    )

    headers = {"Authorization": f"Bearer {token}"}

    create_class = client.post(
        "/api/v1/teachers/classes",
        json={
            "name": f"SSS1 Math Graph Cohort {uuid4().hex[:6]}",
            "description": "Section 8 E2E teacher class",
            "subject": setup_database["subject"],
            "sss_level": setup_database["sss_level"],
            "term": setup_database["term"],
        },
        headers=headers,
    )
    assert create_class.status_code == 201
    class_id = create_class.json()["id"]

    enroll = client.post(
        f"/api/v1/teachers/classes/{class_id}/enroll",
        json={"student_ids": [student_one_id, student_two_id]},
        headers=headers,
    )
    assert enroll.status_code == 200

    seed_db = TestingSessionLocal()
    prereq_concept_id = setup_database["prereq_concept_id"]
    target_concept_id = setup_database["target_concept_id"]
    subject = setup_database["subject"]
    sss_level = setup_database["sss_level"]
    term = setup_database["term"]
    topic_id = setup_database["topic_ids"][1]

    for idx, student_id in enumerate([student_one_id, student_two_id]):
        student_uuid = UUID(student_id)
        prereq_score = 0.42 + idx * 0.12
        target_score = 0.32 + idx * 0.1
        seed_db.add_all(
            [
                StudentConceptMastery(
                    student_id=student_uuid,
                    subject=subject,
                    sss_level=sss_level,
                    term=term,
                    concept_id=prereq_concept_id,
                    mastery_score=prereq_score,
                    source="diagnostic",
                ),
                StudentConceptMastery(
                    student_id=student_uuid,
                    subject=subject,
                    sss_level=sss_level,
                    term=term,
                    concept_id=target_concept_id,
                    mastery_score=target_score,
                    source="practice",
                ),
                ActivityLog(
                    id=uuid4(),
                    student_id=student_uuid,
                    subject=subject,
                    term=term,
                    event_type="lesson_viewed",
                    ref_id=str(topic_id),
                    duration_seconds=360,
                ),
                ActivityLog(
                    id=uuid4(),
                    student_id=student_uuid,
                    subject=subject,
                    term=term,
                    event_type="quiz_submitted",
                    ref_id=str(topic_id),
                    duration_seconds=240,
                ),
            ]
        )
    seed_db.commit()
    seed_db.close()

    list_classes = client.get("/api/v1/teachers/classes", headers=headers)
    assert list_classes.status_code == 200
    assert any(item["id"] == class_id for item in list_classes.json()["classes"])

    dashboard = client.get(f"/api/v1/teachers/classes/{class_id}/dashboard", headers=headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["total_students"] == 2

    heatmap = client.get(f"/api/v1/teachers/classes/{class_id}/heatmap", headers=headers)
    assert heatmap.status_code == 200
    assert len(heatmap.json()["points"]) >= 2

    graph_summary = client.get(f"/api/v1/teachers/classes/{class_id}/graph-summary", headers=headers)
    assert graph_summary.status_code == 200
    graph_json = graph_summary.json()
    assert graph_json["metrics"]["mapped_concepts"] >= 2

    playbook = client.get(f"/api/v1/teachers/classes/{class_id}/graph-playbook", headers=headers)
    assert playbook.status_code == 200

    intervention_queue = client.get(f"/api/v1/teachers/classes/{class_id}/intervention-queue", headers=headers)
    assert intervention_queue.status_code == 200
    assert intervention_queue.json()["total_items"] >= 1

    next_cluster = client.get(f"/api/v1/teachers/classes/{class_id}/next-cluster-plan", headers=headers)
    assert next_cluster.status_code == 200

    risk_matrix = client.get(f"/api/v1/teachers/classes/{class_id}/risk-matrix", headers=headers)
    assert risk_matrix.status_code == 200

    concept_compare = client.get(
        f"/api/v1/teachers/classes/{class_id}/concept-compare",
        params={"left_concept_id": prereq_concept_id, "right_concept_id": target_concept_id},
        headers=headers,
    )
    assert concept_compare.status_code == 200
    compare_json = concept_compare.json()
    assert compare_json["left"]["concept_id"] == prereq_concept_id
    assert compare_json["right"]["concept_id"] == target_concept_id

    presentation = client.get(f"/api/v1/teachers/classes/{class_id}/presentation", headers=headers)
    assert presentation.status_code == 200
    assert presentation.json()["dashboard"]["class_id"] == class_id

    timeline = client.get(
        f"/api/v1/teachers/classes/{class_id}/students/{student_one_id}/timeline",
        headers=headers,
    )
    assert timeline.status_code == 200
