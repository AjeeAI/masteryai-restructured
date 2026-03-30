from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from threading import Lock
from typing import Any

_EVENT_STATS: dict[str, dict[str, Any]] = {}
_EVENT_STATS_LOCK = Lock()


def now_ms() -> float:
    return time.perf_counter()


def log_timed_event(
    logger: logging.Logger,
    event: str,
    started_at: float,
    *,
    log_level: int = logging.INFO,
    **fields: Any,
) -> float:
    duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
    _record_timed_event(event=event, duration_ms=duration_ms, fields=fields)
    rendered_fields = " ".join(
        f"{key}={_render_value(value)}" for key, value in fields.items() if value is not None
    ).strip()
    if rendered_fields:
        logger.log(log_level, "%s duration_ms=%.2f %s", event, duration_ms, rendered_fields)
    else:
        logger.log(log_level, "%s duration_ms=%.2f", event, duration_ms)
    return duration_ms


def telemetry_snapshot() -> dict[str, Any]:
    with _EVENT_STATS_LOCK:
        events = {
            name: {
                "count": int(stats["count"]),
                "last_duration_ms": float(stats["last_duration_ms"]),
                "avg_duration_ms": round(float(stats["total_duration_ms"]) / max(int(stats["count"]), 1), 2),
                "max_duration_ms": float(stats["max_duration_ms"]),
                "last_seen_at": str(stats["last_seen_at"]),
                "last_fields": dict(stats["last_fields"]),
            }
            for name, stats in sorted(_EVENT_STATS.items())
        }
    return {
        "status": "ok",
        "event_count": len(events),
        "events": events,
    }


def reset_telemetry_snapshot() -> None:
    with _EVENT_STATS_LOCK:
        _EVENT_STATS.clear()


def _record_timed_event(*, event: str, duration_ms: float, fields: dict[str, Any]) -> None:
    serialized_fields = {
        key: _snapshot_value(value)
        for key, value in fields.items()
        if value is not None
    }
    seen_at = datetime.now(timezone.utc).isoformat()
    with _EVENT_STATS_LOCK:
        stats = _EVENT_STATS.setdefault(
            event,
            {
                "count": 0,
                "total_duration_ms": 0.0,
                "last_duration_ms": 0.0,
                "max_duration_ms": 0.0,
                "last_seen_at": seen_at,
                "last_fields": {},
            },
        )
        stats["count"] += 1
        stats["total_duration_ms"] += float(duration_ms)
        stats["last_duration_ms"] = float(duration_ms)
        stats["max_duration_ms"] = max(float(stats["max_duration_ms"]), float(duration_ms))
        stats["last_seen_at"] = seen_at
        stats["last_fields"] = serialized_fields


def _render_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.2f}"
    if isinstance(value, (list, tuple, set)):
        return "[" + ",".join(_render_value(item) for item in value) + "]"
    text = str(value).strip()
    return text.replace(" ", "_") if text else "empty"


def _snapshot_value(value: Any) -> Any:
    if isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple, set)):
        return [_snapshot_value(item) for item in list(value)]
    return str(value).strip()
