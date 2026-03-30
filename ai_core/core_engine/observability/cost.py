"""Simple token/cost counters (MVP)."""

from __future__ import annotations
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict, Iterator


@dataclass
class CostTracker:
    counters: Dict[str, float] = field(default_factory=lambda: {"tokens_in": 0.0, "tokens_out": 0.0, "cost_usd": 0.0})

    @contextmanager
    def track(self, request_id: str) -> Iterator[None]:
        # Hook provider usage here (stub for MVP)
        yield

    def snapshot(self) -> Dict[str, float]:
        return dict(self.counters)
