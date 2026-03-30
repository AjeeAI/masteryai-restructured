import os
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.orm import sessionmaker

from backend.core.database import Base, get_db
from backend.core.config import settings
from backend.main import app
from backend.models.governance_hallucination import GovernanceHallucination
from backend.models.curriculum_ingestion_job import CurriculumIngestionJob
from backend.models.curriculum_topic_map import CurriculumTopicMap
from backend.models.curriculum_version import CurriculumVersion
from backend.models.subject import Subject
from backend.models.topic import Topic
from backend.models.user import User
from backend.services.rag_retrieve_service import QdrantVectorStore
from backend.tests.integration.db_utils import resolve_test_database_url


TEST_DATABASE_URL = resolve_test_database_url(test_label="Section 8 E2E admin flow")


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
        pytest.skip(f"E2E admin flow skipped: database unavailable ({exc})", allow_module_level=True)


@pytest.fixture(autouse=True)
def setup_database(monkeypatch, tmp_path):
    _ensure_db_available()
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    subject = db.query(Subject).filter(Subject.slug == "math").first()
    created_subject = False
    if subject is None:
        created_subject = True
        subject = Subject(id=uuid4(), slug="math", name="Mathematics")
        db.add(subject)
        db.flush()

    topic_id = uuid4()
    topic_token = uuid4().hex[:8]
    topic_title = f"Linear Equations {topic_token}"
    db.add(
        Topic(
            id=topic_id,
            subject_id=subject.id,
            sss_level="SSS2",
            term=1,
            title=topic_title,
            description="E2E admin flow topic",
            is_approved=False,
        )
    )

    hall_id = uuid4()
    db.add(
        GovernanceHallucination(
            id=hall_id,
            student_id=None,
            session_id=None,
            endpoint="/api/v1/tutor/chat",
            reason_code="UNVERIFIED_FACT",
            severity="medium",
            status="open",
            prompt_excerpt="Explain citizenship duties.",
            response_excerpt="Potentially unsupported statement.",
            citation_ids=[],
            evidence_payload={"source": "e2e_admin"},
        )
    )
    db.commit()
    subject_id = subject.id
    db.close()

    curriculum_root = Path(tmp_path) / "curriculum"
    curriculum_root.mkdir(parents=True, exist_ok=True)
    (curriculum_root / f"linear_equations_{topic_token}.txt").write_text(
        f"{topic_title}\nDefinition and examples.\nSolve 2x + 4 = 10 by isolating x.",
        encoding="utf-8",
    )

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(settings, "use_neo4j_graph", False)
    monkeypatch.setattr(settings, "internal_service_key", "test-internal-key")
    monkeypatch.setenv("CURRICULUM_CONCEPT_EXTRACT_USE_LLM", "false")
    monkeypatch.setenv("CURRICULUM_CONCEPT_USE_LLM", "false")
    monkeypatch.setenv("CURRICULUM_PREREQ_USE_LLM", "false")
    monkeypatch.setattr(QdrantVectorStore, "upsert_chunks", lambda self, rows: None)
    monkeypatch.setattr(
        QdrantVectorStore,
        "set_approval_flag",
        lambda self, *, curriculum_version_id, approved: None,
    )
    monkeypatch.setattr(
        "backend.endpoints.internal_rag._service.retrieve",
        lambda payload: {
            "chunks": [
                {
                    "chunk_id": "chunk-e2e-admin",
                    "source_id": "doc-e2e-admin",
                    "text": "Linear equations sample chunk",
                    "score": 0.91,
                    "metadata": {"subject": "math"},
                }
            ]
        },
    )

    yield {
        "topic_id": topic_id,
        "hall_id": hall_id,
        "source_root": str(curriculum_root),
        "created_subject": created_subject,
        "subject_id": subject_id,
    }

    cleanup = TestingSessionLocal()
    version_ids = [
        row[0]
        for row in cleanup.query(CurriculumVersion.id)
        .filter(CurriculumVersion.version_name.like("e2e-admin-version-%"))
        .all()
    ]
    if version_ids:
        cleanup.query(CurriculumTopicMap).filter(
            CurriculumTopicMap.version_id.in_(version_ids)
        ).delete(synchronize_session=False)
        cleanup.query(CurriculumIngestionJob).filter(
            CurriculumIngestionJob.version_id.in_(version_ids)
        ).delete(synchronize_session=False)
        cleanup.query(CurriculumVersion).filter(
            CurriculumVersion.id.in_(version_ids)
        ).delete(synchronize_session=False)
    cleanup.query(Topic).filter(Topic.id == topic_id).delete(synchronize_session=False)
    cleanup.query(GovernanceHallucination).filter(GovernanceHallucination.id == hall_id).delete(synchronize_session=False)
    cleanup.query(User).filter(User.email.like("e2e.admin.%@example.com")).delete(synchronize_session=False)
    if created_subject:
        cleanup.query(Subject).filter(Subject.id == subject_id).delete(synchronize_session=False)
    cleanup.commit()
    cleanup.close()
    app.dependency_overrides.clear()


def _register_and_login_admin(client: TestClient) -> tuple[str, str]:
    email = f"e2e.admin.{uuid4()}@example.com"
    password = "StrongPass123!"

    register = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "role": "admin",
            "first_name": "Admin",
            "last_name": "E2E",
            "display_name": "E2E Admin",
        },
    )
    assert register.status_code == 201
    user_id = register.json()["user_id"]

    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return user_id, login.json()["access_token"]


def test_e2e_admin_flow(setup_database):
    topic_id = setup_database["topic_id"]
    source_root = setup_database["source_root"]
    client = TestClient(app)
    admin_id, token = _register_and_login_admin(client)
    headers = {"Authorization": f"Bearer {token}"}

    upload = client.post(
        "/api/v1/admin/curriculum/upload",
        json={
            "subject": "math",
            "sss_level": "SSS2",
            "term": 1,
            "source_root": source_root,
            "version_name": f"e2e-admin-version-{uuid4().hex[:8]}",
        },
        headers=headers,
    )
    assert upload.status_code == 201, upload.text
    upload_data = upload.json()
    version_id = upload_data["version_id"]
    job_id = upload_data["job_id"]

    ingestion_status = client.get(
        "/api/v1/admin/curriculum/ingestion-status",
        params={"job_id": job_id},
        headers=headers,
    )
    assert ingestion_status.status_code == 200

    pending = client.get("/api/v1/admin/curriculum/pending-approvals", headers=headers)
    assert pending.status_code == 200
    assert any(item["id"] == version_id for item in pending.json()["versions"])

    inspect_topic = client.get(f"/api/v1/admin/curriculum/topics/{topic_id}", headers=headers)
    assert inspect_topic.status_code == 200
    mappings = inspect_topic.json()["mappings"]
    assert len(mappings) >= 1
    concept_id = mappings[0]["concept_id"]

    inspect_concept = client.get(
        f"/api/v1/admin/curriculum/concepts/{concept_id}",
        headers=headers,
    )
    assert inspect_concept.status_code == 200

    approve = client.post(
        f"/api/v1/admin/curriculum/versions/{version_id}/approve",
        json={"actor_user_id": admin_id, "note": "E2E approval"},
        headers=headers,
    )
    assert approve.status_code == 200

    metrics = client.get("/api/v1/admin/governance/metrics", headers=headers)
    assert metrics.status_code == 200

    hallucinations = client.get("/api/v1/admin/governance/hallucinations", headers=headers)
    assert hallucinations.status_code == 200
    assert len(hallucinations.json()["items"]) >= 1
    hallucination_id = hallucinations.json()["items"][0]["id"]

    resolve = client.post(
        f"/api/v1/admin/governance/hallucinations/{hallucination_id}/resolve",
        json={"action": "resolved", "resolution_note": "validated", "reviewer_id": admin_id},
        headers=headers,
    )
    assert resolve.status_code == 200

    internal_headers = dict(headers)
    internal_headers["X-Internal-Service-Key"] = "test-internal-key"
    rag = client.post(
        "/api/v1/internal/rag/retrieve",
        json={
            "query": "Explain linear equations",
            "subject": "math",
            "sss_level": "SSS2",
            "term": 1,
            "topic_ids": [str(topic_id)],
            "top_k": 3,
            "approved_only": True,
            "curriculum_version_id": version_id,
        },
        headers=internal_headers,
    )
    assert rag.status_code == 200
    assert len(rag.json()["chunks"]) == 1

    rollback = client.post(
        f"/api/v1/admin/curriculum/versions/{version_id}/rollback",
        json={"actor_user_id": admin_id, "note": "E2E rollback"},
        headers=headers,
    )
    assert rollback.status_code == 200
