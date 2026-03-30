"""Schemas for admin governance endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


HallucinationSeverity = Literal["low", "medium", "high"]
HallucinationStatus = Literal["open", "quarantined", "dismissed", "resolved"]


class GovernanceMetricsResponse(BaseModel):
    """Aggregated trust/quality metrics for admin dashboard."""

    total_hallucination_flags: int
    open_hallucination_flags: int
    resolved_hallucination_flags: int
    high_severity_open_flags: int
    citation_rate: float = Field(ge=0.0, le=1.0)
    retrieval_coverage: float = Field(ge=0.0, le=1.0)
    total_cost_usd: float = Field(ge=0.0)
    avg_session_cost_usd: float = Field(ge=0.0)


class HallucinationOut(BaseModel):
    id: UUID
    student_id: UUID | None = None
    session_id: UUID | None = None
    endpoint: str
    reason_code: str
    severity: HallucinationSeverity
    status: HallucinationStatus
    prompt_excerpt: str | None = None
    response_excerpt: str | None = None
    citation_ids: list[str]
    evidence_payload: dict
    reviewer_id: UUID | None = None
    resolution_note: str | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class HallucinationListResponse(BaseModel):
    items: list[HallucinationOut]


class HallucinationResolveRequest(BaseModel):
    action: Literal["quarantined", "dismissed", "resolved"]
    resolution_note: str | None = Field(default=None, max_length=2000)
    reviewer_id: UUID | None = None


class HallucinationResolveResponse(BaseModel):
    id: UUID
    status: HallucinationStatus
    reviewer_id: UUID | None = None
    resolved_at: datetime | None = None
    message: str
