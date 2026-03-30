"""Repository for governance metrics and hallucination workflow."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session

from backend.models.curriculum_topic_map import CurriculumTopicMap
from backend.models.curriculum_version import CurriculumVersion
from backend.models.governance_hallucination import GovernanceHallucination
from backend.models.tutor_session import TutorSession


class GovernanceRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_hallucinations(
        self,
        *,
        status: str | None = None,
        severity: str | None = None,
        limit: int = 100,
    ) -> list[GovernanceHallucination]:
        query = self.db.query(GovernanceHallucination)
        if status:
            query = query.filter(GovernanceHallucination.status == status)
        if severity:
            query = query.filter(GovernanceHallucination.severity == severity)
        return query.order_by(desc(GovernanceHallucination.created_at)).limit(limit).all()

    def get_hallucination(self, hallucination_id: UUID) -> GovernanceHallucination | None:
        return (
            self.db.query(GovernanceHallucination)
            .filter(GovernanceHallucination.id == hallucination_id)
            .first()
        )

    def update_hallucination_status(
        self,
        row: GovernanceHallucination,
        *,
        status: str,
        resolution_note: str | None,
        reviewer_id: UUID | None,
    ) -> GovernanceHallucination:
        row.status = status
        row.resolution_note = resolution_note
        row.reviewer_id = reviewer_id
        if status in {"resolved", "dismissed", "quarantined"}:
            row.resolved_at = datetime.now(timezone.utc)
        self.db.flush()
        return row

    def count_hallucinations(self, *, status: str | None = None, severity: str | None = None) -> int:
        query = self.db.query(func.count(GovernanceHallucination.id))
        filters = []
        if status is not None:
            filters.append(GovernanceHallucination.status == status)
        if severity is not None:
            filters.append(GovernanceHallucination.severity == severity)
        if filters:
            query = query.filter(and_(*filters))
        return int(query.scalar() or 0)

    def tutor_cost_stats(self) -> tuple[float, float]:
        total_cost = float(self.db.query(func.coalesce(func.sum(TutorSession.cost_usd), 0.0)).scalar() or 0.0)
        avg_cost = float(self.db.query(func.coalesce(func.avg(TutorSession.cost_usd), 0.0)).scalar() or 0.0)
        return total_cost, avg_cost

    def citation_rate(self) -> float:
        total = self.count_hallucinations()
        if total == 0:
            return 1.0
        with_citations = int(
            self.db.query(func.count(GovernanceHallucination.id))
            .filter(func.jsonb_array_length(GovernanceHallucination.citation_ids) > 0)
            .scalar()
            or 0
        )
        return round(with_citations / total, 4)

    def retrieval_coverage(self) -> float:
        approved_versions = int(
            self.db.query(func.count(CurriculumVersion.id))
            .filter(CurriculumVersion.status.in_(("approved", "published")))
            .scalar()
            or 0
        )
        if approved_versions == 0:
            return 0.0

        mapped_versions = int(
            self.db.query(func.count(func.distinct(CurriculumTopicMap.version_id))).scalar()
            or 0
        )
        return round(min(mapped_versions / approved_versions, 1.0), 4)

