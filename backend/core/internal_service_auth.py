"""Shared authentication for backend internal service routes."""

from __future__ import annotations

from hmac import compare_digest

from fastapi import Header, HTTPException, status

from backend.core.config import settings

INTERNAL_SERVICE_HEADER = "X-Internal-Service-Key"


def require_internal_service_key(
    x_internal_service_key: str | None = Header(default=None, alias=INTERNAL_SERVICE_HEADER),
) -> None:
    expected = str(settings.internal_service_key or "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal service authentication is not configured.",
        )

    provided = str(x_internal_service_key or "").strip()
    if not provided or not compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal service credentials.",
        )
