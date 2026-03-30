from uuid import uuid4

from fastapi.testclient import TestClient

from backend.core.config import settings
from backend.main import app


def test_internal_rag_retrieve_success(monkeypatch):
    def _fake_retrieve(payload):
        return {
            "chunks": [
                {
                    "chunk_id": "chunk-1",
                    "source_id": "source.docx",
                    "text": "sample text",
                    "score": 0.91,
                    "metadata": {"subject": "math"},
                }
            ]
        }

    monkeypatch.setattr("backend.endpoints.internal_rag._service.retrieve", _fake_retrieve)
    monkeypatch.setattr(settings, "internal_service_key", "test-internal-key")
    client = TestClient(app)
    response = client.post(
        "/api/v1/internal/rag/retrieve",
        headers={"X-Internal-Service-Key": "test-internal-key"},
        json={
            "query": "Explain linear equations",
            "subject": "math",
            "sss_level": "SSS1",
            "term": 1,
            "topic_ids": [str(uuid4())],
            "top_k": 4,
            "approved_only": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["chunks"][0]["chunk_id"] == "chunk-1"


def test_internal_rag_retrieve_validation_error(monkeypatch):
    monkeypatch.setattr(settings, "internal_service_key", "test-internal-key")
    client = TestClient(app)
    response = client.post(
        "/api/v1/internal/rag/retrieve",
        headers={"X-Internal-Service-Key": "test-internal-key"},
        json={
            "query": "x",  # too short
            "subject": "math",
            "sss_level": "SSS1",
            "term": 1,
            "topic_ids": [],
            "top_k": 4,
            "approved_only": True,
        },
    )
    assert response.status_code == 422
