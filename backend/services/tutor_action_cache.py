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


import json
import redis
from backend.core.config import settings

CACHE_TTL_SECONDS = 600
_redis_client = None

def get_redis_client():
    global _redis_client
    if _redis_client is None and settings.redis_url:
        try:
            _redis_client = redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
        except Exception:
            pass
    return _redis_client

def get_cached_action(key: TutorActionCacheKey) -> TutorChatOut | None:
    client = get_redis_client()
    if not client:
        return None
    try:
        data = client.get(f"tutor_action:{key.to_key()}")
        if data:
            payload = TutorChatOut.model_validate_json(data)
            if is_cacheable_action(payload):
                return payload
            client.delete(f"tutor_action:{key.to_key()}")
    except Exception:
        pass
    return None

def set_cached_action(key: TutorActionCacheKey, payload: TutorChatOut) -> TutorChatOut:
    client = get_redis_client()
    if not client or not is_cacheable_action(payload):
        return payload
    try:
        client.setex(
            f"tutor_action:{key.to_key()}",
            CACHE_TTL_SECONDS,
            payload.model_dump_json()
        )
    except Exception:
        pass
    return payload
