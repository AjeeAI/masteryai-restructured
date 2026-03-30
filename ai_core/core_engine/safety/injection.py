"""Minimal prompt-injection defense (MVP)."""

from __future__ import annotations
import re

_PATTERNS = [
    r"ignore (all|previous) instructions",
    r"system prompt",
    r"developer message",
    r"reveal .*prompt",
]


def sanitize_user_text(text: str) -> str:
    out = text
    for pat in _PATTERNS:
        out = re.sub(pat, "[redacted]", out, flags=re.IGNORECASE)
    return out.strip()
