"""Service layer for governance metrics and hallucination review workflows."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from backend.repositories.governance_repo import GovernanceRepository
from backend.schemas.governance_schema import (
    GovernanceMetricsResponse,
    HallucinationListResponse,
    HallucinationOut,
    HallucinationResolveRequest,
    HallucinationResolveResponse,
)


class GovernanceNotFoundError(LookupError):
    pass


class GovernanceValidationError(ValueError):
    pass


class GovernanceService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = GovernanceRepository(db)

    def get_metrics(self) -> GovernanceMetricsResponse:
        total_flags = self.repo.count_hallucinations()
        open_flags = self.repo.count_hallucinations(status="open")
        resolved_flags = self.repo.count_hallucinations(status="resolved")
        high_severity_open = self.repo.count_hallucinations(status="open", severity="high")

        total_cost_usd, avg_session_cost_usd = self.repo.tutor_cost_stats()
        citation_rate = self.repo.citation_rate()
        retrieval_coverage = self.repo.retrieval_coverage()

        return GovernanceMetricsResponse(
            total_hallucination_flags=total_flags,
            open_hallucination_flags=open_flags,
            resolved_hallucination_flags=resolved_flags,
            high_severity_open_flags=high_severity_open,
            citation_rate=citation_rate,
            retrieval_coverage=retrieval_coverage,
            total_cost_usd=round(total_cost_usd, 4),
            avg_session_cost_usd=round(avg_session_cost_usd, 4),
        )

    def list_hallucinations(
        self,
        *,
        status: str | None = None,
        severity: str | None = None,
        limit: int = 100,
    ) -> HallucinationListResponse:
        if limit < 1 or limit > 500:
            raise GovernanceValidationError("limit must be between 1 and 500")

        rows = self.repo.list_hallucinations(status=status, severity=severity, limit=limit)
        return HallucinationListResponse(
            items=[
                HallucinationOut(
                    id=row.id,
                    student_id=row.student_id,
                    session_id=row.session_id,
                    endpoint=row.endpoint,
                    reason_code=row.reason_code,
                    severity=row.severity,  # type: ignore[arg-type]
                    status=row.status,  # type: ignore[arg-type]
                    prompt_excerpt=row.prompt_excerpt,
                    response_excerpt=row.response_excerpt,
                    citation_ids=list(row.citation_ids or []),
                    evidence_payload=dict(row.evidence_payload or {}),
                    reviewer_id=row.reviewer_id,
                    resolution_note=row.resolution_note,
                    resolved_at=row.resolved_at,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                )
                for row in rows
            ]
        )

    def resolve_hallucination(
        self,
        *,
        hallucination_id: UUID,
        payload: HallucinationResolveRequest,
    ) -> HallucinationResolveResponse:
        row = self.repo.get_hallucination(hallucination_id)
        if row is None:
            raise GovernanceNotFoundError(f"Hallucination flag not found: {hallucination_id}")

        if payload.action in {"resolved", "quarantined"} and not payload.resolution_note:
            raise GovernanceValidationError("resolution_note is required for resolved/quarantined actions")

        row = self.repo.update_hallucination_status(
            row,
            status=payload.action,
            resolution_note=payload.resolution_note,
            reviewer_id=payload.reviewer_id,
        )
        self.db.commit()
        return HallucinationResolveResponse(
            id=row.id,
            status=row.status,  # type: ignore[arg-type]
            reviewer_id=row.reviewer_id,
            resolved_at=row.resolved_at,
            message=f"Hallucination flag updated to '{row.status}'.",
        )
