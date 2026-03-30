"""Basic moderation/refusal checks (MVP)."""

from __future__ import annotations
import re


class ModerationError(ValueError):
    pass


_DISALLOWED = [
    r"how to make a bomb",
    r"how to build a gun",
    r"suicide",
]


def basic_moderate(text: str) -> None:
    t = text.lower()
    for pat in _DISALLOWED:
        if re.search(pat, t):
            raise ModerationError("Request refused due to safety constraints.")
