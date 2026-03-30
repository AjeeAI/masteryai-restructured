from __future__ import annotations

from statistics import mean
from uuid import UUID

from backend.repositories.mastery_repo import MasteryRepository
from backend.schemas.mastery_schema import MasteryDashboardOut, MasteryEvidenceSummary, MasteryView, StreakOut


MASTERY_THRESHOLD = 0.7


class MasteryDashboardService:
    def __init__(self, repo: MasteryRepository):
        self.repo = repo

    @staticmethod
    def _validate_scope(*, subject: str, term: int, view: str) -> None:
        if subject not in {"math", "english", "civic"}:
            raise ValueError("subject must be one of: math, english, civic")
        if term not in {1, 2, 3}:
            raise ValueError("term must be one of: 1, 2, 3")
        if view not in {"concept", "topic"}:
            raise ValueError("view must be one of: concept, topic")

    def _award_mvp_badges(self, *, student_id: UUID, mastery: list[dict], streak_current: int) -> None:
        changed = False

        if streak_current >= 5:
            self.repo.ensure_badge(
                student_id=student_id,
                badge_code="consistency_5",
                badge_name="Consistency-5",
                description="Completed at least 5 consecutive active study days.",
                metadata={"threshold": 5},
            )
            changed = True

        if any(float(item.get("score", 0.0)) >= MASTERY_THRESHOLD for item in mastery):
            self.repo.ensure_badge(
                student_id=student_id,
                badge_code="topic_milestone_1",
                badge_name="Topic-Milestone-1",
                description="Reached mastery threshold in at least one topic/concept.",
                metadata={"mastery_threshold": MASTERY_THRESHOLD},
            )
            changed = True

        if changed:
            self.repo.commit()

    def get_dashboard(
        self,
        *,
        student_id: UUID,
        subject: str,
        term: int,
        view: MasteryView = "concept",
        persist_snapshot: bool = False,
    ) -> MasteryDashboardOut:
        self._validate_scope(subject=subject, term=term, view=view)

        mastery = (
            self.repo.get_concept_mastery(student_id=student_id, subject=subject, term=term)
            if view == "concept"
            else self.repo.get_topic_mastery(student_id=student_id, subject=subject, term=term)
        )
        evidence_summary = MasteryEvidenceSummary()
        for item in mastery:
            score = float(item.get("score", 0.0) or 0.0)
            if score >= MASTERY_THRESHOLD:
                item["mastery_state"] = "demonstrated"
                evidence_summary.demonstrated += 1
            elif score > 0:
                item["mastery_state"] = "needs_review"
                evidence_summary.needs_review += 1
            else:
                item["mastery_state"] = "unassessed"
                evidence_summary.unassessed += 1

        stats = self.repo.get_student_stats(student_id)
        streak_current = int(stats.current_streak) if stats else 0
        streak_best = int(stats.max_streak) if stats else 0

        self._award_mvp_badges(student_id=student_id, mastery=mastery, streak_current=streak_current)
        badges = self.repo.list_badges(student_id)

        if persist_snapshot:
            overall = mean([float(item.get("score", 0.0)) for item in mastery]) if mastery else 0.0
            self.repo.upsert_snapshot(
                student_id=student_id,
                subject=subject,
                term=term,
                view=view,
                mastery_payload=mastery,
                overall_mastery=overall,
                source="dashboard",
            )
            self.repo.commit()

        return MasteryDashboardOut(
            subject=subject,
            view=view,
            mastery=mastery,
            streak=StreakOut(current=streak_current, best=streak_best),
            badges=badges,
            evidence_summary=evidence_summary,
        )
