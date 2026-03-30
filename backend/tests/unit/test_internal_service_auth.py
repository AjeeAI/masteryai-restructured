from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.core.config import settings
from backend.main import app


@pytest.mark.parametrize(
    ("method", "path", "params", "json_body"),
    [
        ("get", "/api/v1/internal/postgres/profile", {"student_id": str(uuid4())}, None),
        (
            "get",
            "/api/v1/internal/graph/context",
            {
                "student_id": str(uuid4()),
                "subject": "math",
                "sss_level": "SSS1",
                "term": 1,
            },
            None,
        ),
        (
            "post",
            "/api/v1/internal/rag/retrieve",
            None,
            {
                "query": "Explain linear equations",
                "subject": "math",
                "sss_level": "SSS1",
                "term": 1,
                "topic_ids": [str(uuid4())],
                "top_k": 4,
                "approved_only": True,
            },
        ),
    ],
)
def test_internal_routes_require_service_key(monkeypatch, method, path, params, json_body):
    monkeypatch.setattr(settings, "internal_service_key", "test-internal-key")
    client = TestClient(app)

    response = client.request(method, path, params=params, json=json_body)

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid internal service credentials."


def test_internal_routes_fail_closed_when_service_key_missing(monkeypatch):
    monkeypatch.setattr(settings, "internal_service_key", "")
    client = TestClient(app)

    response = client.post(
        "/api/v1/internal/rag/retrieve",
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

    assert response.status_code == 503
    assert response.json()["detail"] == "Internal service authentication is not configured."
