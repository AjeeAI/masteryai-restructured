from uuid import uuid4

import pytest

from backend.core.config import settings
from backend.core.internal_service_auth import INTERNAL_SERVICE_HEADER
from backend.schemas.quiz_schema import ConceptBreakdownItem
from backend.services.graph_mastery_update_service import GraphMasteryUpdateService


class _DummyResponse:
    def raise_for_status(self) -> None:
        return None


class _RecordingAsyncClient:
    def __init__(self, *args, **kwargs):
        self.calls: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json=None, headers=None):
        self.calls.append({"url": url, "json": json, "headers": headers or {}})
        return _DummyResponse()


@pytest.mark.anyio
async def test_graph_mastery_update_sends_internal_service_key(monkeypatch):
    recorded = _RecordingAsyncClient()
    monkeypatch.setattr(settings, "internal_graph_base_url", "http://127.0.0.1:8001/api/v1/internal/graph")
    monkeypatch.setattr(settings, "internal_graph_timeout_seconds", 5.0)
    monkeypatch.setattr(settings, "internal_graph_max_retries", 0)
    monkeypatch.setattr(settings, "internal_service_key", "shared-test-key")
    monkeypatch.setattr(
        "backend.services.graph_mastery_update_service.httpx.AsyncClient",
        lambda timeout: recorded,
    )

    service = GraphMasteryUpdateService()
    ok = await service.send_update(
        student_id=uuid4(),
        quiz_id=uuid4(),
        attempt_id=uuid4(),
        subject="civic",
        sss_level="SSS1",
        term=2,
        source="practice",
        concept_breakdown=[
            ConceptBreakdownItem(
                concept_id="civic:sss1:t2:meaning-of-election",
                is_correct=True,
                weight_change=0.2,
            )
        ],
    )

    assert ok is True
    assert len(recorded.calls) == 1
    assert recorded.calls[0]["url"].endswith("/update-mastery")
    assert recorded.calls[0]["headers"][INTERNAL_SERVICE_HEADER] == "shared-test-key"
