from __future__ import annotations

from datetime import date
from statistics import mean
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.activity import StudentStats
from backend.models.mastery_snapshot import MasterySnapshot
from backend.models.student_badge import StudentBadge
from backend.models.student_concept_mastery import StudentConceptMastery


class MasteryRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_concept_mastery(
        self,
        *,
        student_id: UUID,
        subject: str,
        term: int,
    ) -> list[dict]:
        rows = (
            self.db.query(StudentConceptMastery.concept_id, StudentConceptMastery.mastery_score)
            .filter(
                StudentConceptMastery.student_id == student_id,
                StudentConceptMastery.subject == subject,
                StudentConceptMastery.term == term,
            )
            .order_by(StudentConceptMastery.mastery_score.desc())
            .all()
        )
        return [
            {"concept_id": str(concept_id), "score": round(float(score), 4)}
            for concept_id, score in rows
        ]

    def get_topic_mastery(
        self,
        *,
        student_id: UUID,
        subject: str,
        term: int,
    ) -> list[dict]:
        rows = (
            self.db.query(
                StudentConceptMastery.concept_id,
                func.avg(StudentConceptMastery.mastery_score).label("avg_score"),
            )
            .filter(
                StudentConceptMastery.student_id == student_id,
                StudentConceptMastery.subject == subject,
                StudentConceptMastery.term == term,
            )
            .group_by(StudentConceptMastery.concept_id)
            .order_by(func.avg(StudentConceptMastery.mastery_score).desc())
            .all()
        )
        return [
            {"topic_id": str(topic_id), "score": round(float(avg_score), 4)}
            for topic_id, avg_score in rows
        ]

    def get_student_stats(self, student_id: UUID) -> StudentStats | None:
        return self.db.get(StudentStats, student_id)

    def list_badges(self, student_id: UUID) -> list[str]:
        rows = (
            self.db.query(StudentBadge.badge_name)
            .filter(StudentBadge.student_id == student_id)
            .order_by(StudentBadge.awarded_at.desc())
            .all()
        )
        return [str(name) for (name,) in rows]

    def ensure_badge(
        self,
        *,
        student_id: UUID,
        badge_code: str,
        badge_name: str,
        description: str | None = None,
        metadata: dict | None = None,
    ) -> StudentBadge:
        existing = (
            self.db.query(StudentBadge)
            .filter(
                StudentBadge.student_id == student_id,
                StudentBadge.badge_code == badge_code,
            )
            .first()
        )
        if existing:
            return existing

        badge = StudentBadge(
            student_id=student_id,
            badge_code=badge_code,
            badge_name=badge_name,
            description=description,
            metadata_payload=metadata or {},
        )
        self.db.add(badge)
        self.db.flush()
        return badge

    def upsert_snapshot(
        self,
        *,
        student_id: UUID,
        subject: str,
        term: int,
        view: str,
        mastery_payload: list[dict],
        overall_mastery: float | None = None,
        source: str = "dashboard",
        snapshot_date: date | None = None,
    ) -> MasterySnapshot:
        snapshot_date = snapshot_date or date.today()
        row = (
            self.db.query(MasterySnapshot)
            .filter(
                MasterySnapshot.student_id == student_id,
                MasterySnapshot.subject == subject,
                MasterySnapshot.term == term,
                MasterySnapshot.view == view,
                MasterySnapshot.snapshot_date == snapshot_date,
            )
            .first()
        )

        if overall_mastery is None:
            scores = [float(item.get("score", 0)) for item in mastery_payload]
            overall_mastery = mean(scores) if scores else 0.0

        if row:
            row.mastery_payload = mastery_payload
            row.overall_mastery = overall_mastery
            row.source = source
            return row

        snapshot = MasterySnapshot(
            student_id=student_id,
            subject=subject,
            term=term,
            view=view,
            snapshot_date=snapshot_date,
            mastery_payload=mastery_payload,
            overall_mastery=overall_mastery,
            source=source,
        )
        self.db.add(snapshot)
        self.db.flush()
        return snapshot

    def commit(self) -> None:
        self.db.commit()
