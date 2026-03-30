from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from backend.models.mastery_update_event import MasteryUpdateEvent
from backend.models.student_concept_mastery import StudentConceptMastery


class GraphRepository:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _to_float(value: Decimal | float | int | None) -> float:
        if value is None:
            return 0.0
        return float(value)

    def get_mastery_map(
        self,
        *,
        student_id: UUID,
        subject: str,
        sss_level: str,
        term: int,
    ) -> dict[str, float]:
        rows = (
            self.db.query(StudentConceptMastery)
            .filter(
                StudentConceptMastery.student_id == student_id,
                StudentConceptMastery.subject == subject,
                StudentConceptMastery.sss_level == sss_level,
                StudentConceptMastery.term == term,
            )
            .all()
        )
        return {row.concept_id: self._to_float(row.mastery_score) for row in rows}

    def upsert_mastery(
        self,
        *,
        student_id: UUID,
        subject: str,
        sss_level: str,
        term: int,
        concept_id: str,
        new_score: float,
        source: str,
        evaluated_at: datetime | None = None,
    ) -> tuple[float, float]:
        evaluated_at = evaluated_at or datetime.now(timezone.utc)
        safe_score = max(0.0, min(1.0, round(new_score, 4)))

        row = (
            self.db.query(StudentConceptMastery)
            .filter(
                StudentConceptMastery.student_id == student_id,
                StudentConceptMastery.subject == subject,
                StudentConceptMastery.sss_level == sss_level,
                StudentConceptMastery.term == term,
                StudentConceptMastery.concept_id == concept_id,
            )
            .first()
        )

        if row:
            previous = self._to_float(row.mastery_score)
            row.mastery_score = safe_score
            row.source = source
            row.last_evaluated_at = evaluated_at
            self.db.flush()
            return previous, safe_score

        created = StudentConceptMastery(
            student_id=student_id,
            subject=subject,
            sss_level=sss_level,
            term=term,
            concept_id=concept_id,
            mastery_score=safe_score,
            source=source,
            last_evaluated_at=evaluated_at,
        )
        self.db.add(created)
        self.db.flush()
        return 0.0, safe_score

    def record_update_event(
        self,
        *,
        student_id: UUID,
        quiz_id: UUID | None,
        attempt_id: UUID | None,
        subject: str,
        sss_level: str,
        term: int,
        source: str,
        concept_breakdown: list[dict[str, Any]],
        new_mastery: list[dict[str, Any]],
    ) -> None:
        event = MasteryUpdateEvent(
            student_id=student_id,
            quiz_id=quiz_id,
            attempt_id=attempt_id,
            subject=subject,
            sss_level=sss_level,
            term=term,
            source=source,
            concept_breakdown=concept_breakdown,
            new_mastery=new_mastery,
        )
        self.db.add(event)
        self.db.flush()

