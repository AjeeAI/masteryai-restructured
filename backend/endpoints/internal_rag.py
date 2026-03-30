"""Internal RAG retrieval endpoint for AI orchestration services."""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, status

from backend.core.internal_service_auth import require_internal_service_key
from backend.core.telemetry import log_timed_event
from backend.schemas.internal_rag_schema import InternalRagRetrieveRequest, InternalRagRetrieveResponse
from backend.services.rag_retrieve_service import RagRetrieveService, RagRetrieveServiceError

router = APIRouter(
    prefix="/internal/rag",
    tags=["Internal RAG APIs"],
    dependencies=[Depends(require_internal_service_key)],
)

_service = RagRetrieveService()
logger = logging.getLogger(__name__)


@router.post("/retrieve", response_model=InternalRagRetrieveResponse)
def retrieve_chunks(payload: InternalRagRetrieveRequest):
    """Retrieve scoped curriculum chunks for agentic tutor/quiz workflows.

    This API is intended for internal orchestration services, not direct frontend use.
    """
    started_at = time.perf_counter()
    try:
        response = _service.retrieve(payload)
        chunks = response.chunks if hasattr(response, "chunks") else response.get("chunks", [])
        log_timed_event(
            logger,
            "internal.rag.retrieve",
            started_at,
            outcome="success",
            subject=payload.subject,
            sss_level=payload.sss_level,
            term=payload.term,
            approved_only=payload.approved_only,
            topic_count=len(list(payload.topic_ids or [])),
            top_k=payload.top_k,
            chunk_count=len(list(chunks or [])),
            curriculum_version_id=str(payload.curriculum_version_id) if payload.curriculum_version_id else None,
        )
        return response
    except RagRetrieveServiceError as exc:
        log_timed_event(
            logger,
            "internal.rag.retrieve",
            started_at,
            outcome="error",
            subject=payload.subject,
            sss_level=payload.sss_level,
            term=payload.term,
            approved_only=payload.approved_only,
            topic_count=len(list(payload.topic_ids or [])),
            top_k=payload.top_k,
            error=str(exc),
            log_level=logging.WARNING,
        )
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
