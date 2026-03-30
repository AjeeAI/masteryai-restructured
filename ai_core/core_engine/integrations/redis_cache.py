"""Optional Redis caching (MVP)."""

from __future__ import annotations
import json
from typing import Any, Optional


class RedisCache:
    def __init__(self, url: str):
        self.url = url
        if not self.url:
            raise ValueError("Redis URL is required.")
        try:
            import redis
        except ModuleNotFoundError as exc:
            raise RuntimeError("redis dependency missing in ai-core environment.") from exc

        self._client = redis.from_url(self.url, decode_responses=True)

    def get_json(self, key: str) -> Optional[Any]:
        raw = self._client.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def set_json(self, key: str, value: Any, ttl_seconds: int = 600) -> None:
        payload = json.dumps(value, ensure_ascii=True)
        self._client.setex(key, ttl_seconds, payload)
