from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.core.auth import get_current_user
from backend.core.config import settings
from backend.core.database import get_db
from backend.main import app


def _override_db():
    yield object()


def _admin_user():
    return SimpleNamespace(id=uuid4(), role="admin")


def _student_user():
    return SimpleNamespace(id=uuid4(), role="student")


def test_section7_admin_routes_require_admin_role():
    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _student_user
    client = TestClient(app)

    response = client.get("/api/v1/admin/governance/metrics")
    app.dependency_overrides.clear()

    assert response.status_code == 403


def test_section7_admin_flow_with_mocked_services(monkeypatch):
    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _admin_user
    monkeypatch.setattr(settings, "internal_service_key", "test-internal-key")

    class _CurriculumService:
        def get_pending_approvals(self):
            return {"versions": []}

        def get_ingestion_status(self, job_id=None):
            return {"jobs": []}

    class _GovernanceService:
        def get_metrics(self):
            return {
                "total_hallucination_flags": 0,
                "open_hallucination_flags": 0,
                "resolved_hallucination_flags": 0,
                "high_severity_open_flags": 0,
                "citation_rate": 1.0,
                "retrieval_coverage": 0.0,
                "total_cost_usd": 0.0,
                "avg_session_cost_usd": 0.0,
            }

    monkeypatch.setattr("backend.endpoints.admin_curriculum._service", lambda db: _CurriculumService())
    monkeypatch.setattr("backend.endpoints.admin_governance._service", lambda db: _GovernanceService())
    monkeypatch.setattr(
        "backend.endpoints.internal_rag._service.retrieve",
        lambda payload: {
            "chunks": [
                {
                    "chunk_id": "chunk-1",
                    "source_id": "doc-1",
                    "text": "hello",
                    "score": 0.8,
                    "metadata": {},
                }
            ]
        },
    )

    client = TestClient(app)
    pending = client.get("/api/v1/admin/curriculum/pending-approvals")
    health = client.get("/api/v1/admin/governance/metrics")
    rag = client.post(
        "/api/v1/internal/rag/retrieve",
        json={
            "query": "Explain concord",
            "subject": "english",
            "sss_level": "SSS1",
            "term": 1,
            "topic_ids": [],
            "top_k": 6,
            "approved_only": True,
        },
        headers={"X-Internal-Service-Key": "test-internal-key"},
    )

    app.dependency_overrides.clear()

    assert pending.status_code == 200
    assert health.status_code == 200
    assert rag.status_code == 200
