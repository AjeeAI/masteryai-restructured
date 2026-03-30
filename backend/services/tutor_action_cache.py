from __future__ import annotations

import time
from dataclasses import dataclass
from uuid import UUID

from backend.schemas.tutor_schema import TutorChatOut

CACHE_TTL_SECONDS = 600.0
_ACTION_CACHE: dict[str, tuple[float, TutorChatOut]] = {}
_NON_CACHEABLE_ACTIONS = {
    "FALLBACK_GUIDANCE_ONLY",
    "RECAP_FALLBACK",
    "DRILL_FALLBACK",
    "PREREQ_BRIDGE_FALLBACK",
    "STUDY_PLAN_FALLBACK",
}
_NON_CACHEABLE_PREFIXES = (
    "Tutor provider unavailable right now.",
    "Recap unavailable right now.",
    "Drill mode is unavailable right now.",
    "Prerequisite bridge is unavailable right now.",
    "Study-plan generation is unavailable right now.",
)


@dataclass(frozen=True)
class TutorActionCacheKey:
    action_id: str
    session_id: UUID
    topic_id: UUID
    difficulty: str | None = None

    def to_key(self) -> str:
        parts = [
            str(self.session_id),
            str(self.topic_id),
            self.action_id,
            (self.difficulty or "none"),
        ]
        return ":".join(parts)


def is_cacheable_action(payload: TutorChatOut) -> bool:
    assistant_message = str(payload.assistant_message or "").strip()
    if any(assistant_message.startswith(prefix) for prefix in _NON_CACHEABLE_PREFIXES):
        return False
    actions = {str(item).strip() for item in list(payload.actions or [])}
    if actions.intersection(_NON_CACHEABLE_ACTIONS):
        return False
    return True


def get_cached_action(key: TutorActionCacheKey) -> TutorChatOut | None:
    entry = _ACTION_CACHE.get(key.to_key())
    if entry is None:
        return None
    created_at, payload = entry
    if (time.time() - created_at) > CACHE_TTL_SECONDS:
        _ACTION_CACHE.pop(key.to_key(), None)
        return None
    if not is_cacheable_action(payload):
        _ACTION_CACHE.pop(key.to_key(), None)
        return None
    return payload


def set_cached_action(key: TutorActionCacheKey, payload: TutorChatOut) -> TutorChatOut:
    if not is_cacheable_action(payload):
        _ACTION_CACHE.pop(key.to_key(), None)
        return payload
    _ACTION_CACHE[key.to_key()] = (time.time(), payload)
    return payload
