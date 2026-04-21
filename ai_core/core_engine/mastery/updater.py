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

    # --- NEW: AGENTIC MASTERY LOGIC ---
    def update_inline_mastery(
        self,
        *,
        user_id: str,
        concept_label: str,
        score_delta: float,
        reason: str
    ) -> None:
        """Process an autonomous agentic mastery update directly from the chat tutor."""
        
        # 1. Safety Check: Clamp the delta so a hallucinating LLM can't give +1000 score
        safe_delta = max(-0.2, min(0.2, float(score_delta)))
        
        print(f"🧠 [MASTERY ENGINE] Updating '{concept_label}' by {safe_delta} for {user_id}. Reason: {reason}")
        
        # 2. Call your Postgres repo to execute the actual SQL
        # Note: You may need to create this method in your PostgresRepo class!
        self.repo.upsert_concept_mastery(
            user_id=user_id,
            concept_label=concept_label,
            mastery_delta=safe_delta
        )