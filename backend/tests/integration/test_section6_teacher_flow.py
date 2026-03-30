import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.auth import get_current_user
from backend.core.database import Base, get_db
from backend.main import app
from backend.models.teacher_assignment import TeacherAssignment
from backend.models.teacher_class import TeacherClass
from backend.models.teacher_intervention import TeacherIntervention
from backend.models.user import User
from backend.models.class_enrollment import ClassEnrollment
from backend.tests.integration.db_utils import resolve_test_database_url


TEST_DATABASE_URL = resolve_test_database_url(test_label="Section 6 integration flow")


engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    teacher_id = uuid4()
    student_id = uuid4()
    db.add(
        User(
            id=teacher_id,
            email=f"section6.teacher.{teacher_id}@example.com",
            password_hash="hash",
            role="teacher",
            is_active=True,
        )
    )
    db.add(
        User(
            id=student_id,
            email=f"section6.student.{student_id}@example.com",
            password_hash="hash",
            role="student",
            is_active=True,
        )
    )
    db.commit()

    def _override_user():
        return SimpleNamespace(id=teacher_id, role="teacher")

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = _override_user

    yield {"teacher_id": teacher_id, "student_id": student_id}

    cleanup = TestingSessionLocal()
    cleanup.query(TeacherIntervention).filter(TeacherIntervention.teacher_id == teacher_id).delete(synchronize_session=False)
    cleanup.query(TeacherAssignment).filter(TeacherAssignment.teacher_id == teacher_id).delete(synchronize_session=False)
    cleanup.query(ClassEnrollment).filter(ClassEnrollment.student_id == student_id).delete(synchronize_session=False)
    cleanup.query(TeacherClass).filter(TeacherClass.teacher_id == teacher_id).delete(synchronize_session=False)
    cleanup.query(User).filter(User.id.in_([teacher_id, student_id])).delete(synchronize_session=False)
    cleanup.commit()
    cleanup.close()
    app.dependency_overrides.clear()


def test_section6_teacher_flow(setup_database):
    client = TestClient(app)
    student_id = setup_database["student_id"]

    create_class = client.post(
        "/api/v1/teachers/classes",
        json={
            "name": f"SSS2 Math Cohort {str(uuid4())[:8]}",
            "description": "Section 6 integration test class",
            "subject": "math",
            "sss_level": "SSS2",
            "term": 1,
        },
    )
    assert create_class.status_code == 201
    class_id = create_class.json()["id"]

    enroll = client.post(
        f"/api/v1/teachers/classes/{class_id}/enroll",
        json={"student_ids": [str(student_id)]},
    )
    assert enroll.status_code == 200

    list_classes = client.get("/api/v1/teachers/classes")
    assert list_classes.status_code == 200
    assert any(item["id"] == class_id for item in list_classes.json()["classes"])

    dashboard = client.get(f"/api/v1/teachers/classes/{class_id}/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.json()["class_id"] == class_id

    heatmap = client.get(f"/api/v1/teachers/classes/{class_id}/heatmap")
    assert heatmap.status_code == 200

    alerts = client.get(f"/api/v1/teachers/classes/{class_id}/alerts")
    assert alerts.status_code == 200

    timeline = client.get(f"/api/v1/teachers/classes/{class_id}/students/{student_id}/timeline")
    assert timeline.status_code == 200
    assert timeline.json()["student_id"] == str(student_id)

    assignment = client.post(
        "/api/v1/teachers/assignments",
        json={
            "class_id": class_id,
            "student_id": str(student_id),
            "assignment_type": "topic",
            "ref_id": "linear-equations",
            "title": "Linear Equations Revision",
            "instructions": "Solve examples 1-10",
            "subject": "math",
            "sss_level": "SSS2",
            "term": 1,
            "due_at": None,
        },
    )
    assert assignment.status_code == 201

    intervention = client.post(
        "/api/v1/teachers/interventions",
        json={
            "class_id": class_id,
            "student_id": str(student_id),
            "intervention_type": "note",
            "severity": "medium",
            "subject": "math",
            "sss_level": "SSS2",
            "term": 1,
            "notes": "Provide additional guided practice.",
            "action_plan": "1:1 review after class.",
        },
    )
    assert intervention.status_code == 201

    remove = client.delete(f"/api/v1/teachers/classes/{class_id}/enroll/{student_id}")
    assert remove.status_code == 204
