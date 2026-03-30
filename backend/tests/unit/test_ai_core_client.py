from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

from backend.core.ai_core_client import generate_quiz_insights
from backend.core.config import settings


@pytest.mark.anyio
async def test_generate_quiz_insights_returns_empty_when_base_url_missing(monkeypatch):
    monkeypatch.setattr(settings, "ai_core_base_url", "")

    out = await generate_quiz_insights(uuid4(), uuid4())

    assert out == []


@pytest.mark.anyio
async def test_generate_quiz_insights_returns_empty_on_http_error(monkeypatch):
    monkeypatch.setattr(settings, "ai_core_base_url", "https://mastery-ai-core.onrender.com")

    mocked_client = AsyncMock()
    mocked_client.__aenter__.return_value.get.side_effect = httpx.RequestError("boom")
    mocked_client.__aexit__.return_value = False
    monkeypatch.setattr("backend.core.ai_core_client.httpx.AsyncClient", lambda timeout: mocked_client)

    out = await generate_quiz_insights(uuid4(), uuid4())

    assert out == []
