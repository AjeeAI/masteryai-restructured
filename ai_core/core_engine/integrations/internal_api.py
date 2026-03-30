"""Helpers for authenticated ai-core -> backend internal HTTP calls."""

from __future__ import annotations

import os

INTERNAL_SERVICE_HEADER = "X-Internal-Service-Key"


def internal_service_headers() -> dict[str, str]:
    key = str(os.getenv("INTERNAL_SERVICE_KEY") or "").strip()
    if not key:
        return {}
    return {INTERNAL_SERVICE_HEADER: key}


def internal_service_key_configured() -> bool:
    return bool(str(os.getenv("INTERNAL_SERVICE_KEY") or "").strip())
