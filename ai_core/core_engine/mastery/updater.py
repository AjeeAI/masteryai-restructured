"""Basic mastery update heuristics (MVP)."""

from __future__ import annotations
from typing import Any, Dict, Optional
from ai_core.core_engine.integrations.postgres_repo import PostgresRepo


class MasteryUpdater:
    def __init__(self, repo: PostgresRepo):
        self.repo = repo

    def update_from_interaction(
        self,
        *,
        user_id: str,
        subject_id: str,
        topic_id: Optional[str],
        interaction_type: str,
        signal: Dict[str, Any],
    ) -> None:
        """Update mastery score based on interaction signals (stub)."""
        if not topic_id:
            return
        self.repo.upsert_topic_mastery(user_id=user_id, subject_id=subject_id, topic_id=topic_id, mastery_delta=0.02)
