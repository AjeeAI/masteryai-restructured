from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import List
from uuid import UUID

import httpx

from backend.core.config import settings
from backend.core.internal_service_auth import INTERNAL_SERVICE_HEADER
from backend.schemas.quiz_schema import ConceptBreakdownItem, GraphMasteryUpdatePayload

logger = logging.getLogger(__name__)


class GraphMasteryUpdateService:
    def __init__(self, db=None):
        self.db = db

    async def send_update(
        self,
        student_id: UUID,
        quiz_id: UUID,
        attempt_id: UUID,
        subject: str,
        sss_level: str,
        term: int,
        source: str,
        concept_breakdown: List[ConceptBreakdownItem],
    ) -> bool:
        try:
            payload = GraphMasteryUpdatePayload(
                student_id=student_id,
                quiz_id=quiz_id,
                attempt_id=attempt_id,
                subject=subject,
                sss_level=sss_level,
                term=term,
                timestamp=datetime.now(timezone.utc),
                source=source,
                concept_breakdown=concept_breakdown,
            )
        except Exception as exc:
            logger.warning("Skipping graph mastery update due to invalid payload: %s", exc)
            return False

        base_url = settings.internal_graph_base_url.rstrip("/")
        if not base_url:
            logger.warning("Skipping graph mastery update: INTERNAL_GRAPH_BASE_URL is not configured")
            return False

        timeout = max(float(settings.internal_graph_timeout_seconds), 1.0)
        retries = max(int(settings.internal_graph_max_retries), 0)

        for attempt_index in range(retries + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        f"{base_url}/update-mastery",
                        json=payload.model_dump(mode="json"),
                        headers={INTERNAL_SERVICE_HEADER: settings.internal_service_key},
                    )
                    response.raise_for_status()
                return True
            except httpx.HTTPError as exc:
                if attempt_index >= retries:
                    logger.warning("Graph mastery update failed after retries: %s", exc)
                    return False
                await asyncio.sleep(min(0.25 * (attempt_index + 1), 1.0))

        return False
