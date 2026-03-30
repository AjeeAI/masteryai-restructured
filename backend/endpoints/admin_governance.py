"""Admin governance endpoints for trust, quality, and hallucination management."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.schemas.governance_schema import (
    GovernanceMetricsResponse,
    HallucinationListResponse,
    HallucinationResolveRequest,
    HallucinationResolveResponse,
)
from backend.services.governance_service import (
    GovernanceNotFoundError,
    GovernanceService,
    GovernanceValidationError,
)

router = APIRouter(prefix="/admin/governance", tags=["Admin Governance"])


def _service(db: Session) -> GovernanceService:
    return GovernanceService(db)


def _require_admin(current_user) -> None:
    if getattr(current_user, "role", None) != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required.",
        )


@router.get("/metrics", response_model=GovernanceMetricsResponse)
def governance_metrics(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return trust metrics (citation coverage, retrieval coverage, and costs)."""
    _require_admin(current_user)
    return _service(db).get_metrics()


@router.get("/hallucinations", response_model=HallucinationListResponse)
def list_hallucinations(
    status_filter: str | None = Query(default=None, alias="status"),
    severity: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List flagged hallucinations with optional status/severity filters."""
    _require_admin(current_user)
    try:
        return _service(db).list_hallucinations(status=status_filter, severity=severity, limit=limit)
    except GovernanceValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/hallucinations/{hallucination_id}/resolve", response_model=HallucinationResolveResponse)
def resolve_hallucination(
    hallucination_id: UUID,
    payload: HallucinationResolveRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Resolve, quarantine, or dismiss a flagged hallucination output."""
    _require_admin(current_user)
    if payload.reviewer_id is None:
        payload.reviewer_id = current_user.id
    try:
        return _service(db).resolve_hallucination(hallucination_id=hallucination_id, payload=payload)
    except GovernanceValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except GovernanceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
