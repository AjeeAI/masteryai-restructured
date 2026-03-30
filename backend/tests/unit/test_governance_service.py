from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.schemas.governance_schema import HallucinationResolveRequest
from backend.services.governance_service import (
    GovernanceNotFoundError,
    GovernanceService,
    GovernanceValidationError,
)


class _FakeDB:
    def __init__(self):
        self.committed = False

    def commit(self):
        self.committed = True


def test_get_metrics_aggregates_repo_numbers(monkeypatch):
    service = GovernanceService(db=_FakeDB())
    monkeypatch.setattr(
        service.repo,
        "count_hallucinations",
        lambda status=None, severity=None: 3 if status is None else (1 if status == "open" else 0),
    )
    monkeypatch.setattr(service.repo, "tutor_cost_stats", lambda: (1.2345, 0.1234))
    monkeypatch.setattr(service.repo, "citation_rate", lambda: 0.7)
    monkeypatch.setattr(service.repo, "retrieval_coverage", lambda: 0.8)

    out = service.get_metrics()
    assert out.total_hallucination_flags == 3
    assert out.open_hallucination_flags == 1
    assert out.citation_rate == 0.7


def test_list_hallucinations_validates_limit():
    service = GovernanceService(db=_FakeDB())
    with pytest.raises(GovernanceValidationError):
        service.list_hallucinations(limit=0)


def test_resolve_hallucination_not_found(monkeypatch):
    service = GovernanceService(db=_FakeDB())
    monkeypatch.setattr(service.repo, "get_hallucination", lambda _id: None)
    with pytest.raises(GovernanceNotFoundError):
        service.resolve_hallucination(
            hallucination_id=uuid4(),
            payload=HallucinationResolveRequest(action="dismissed"),
        )


def test_resolve_hallucination_requires_note_for_resolved(monkeypatch):
    service = GovernanceService(db=_FakeDB())
    row = SimpleNamespace(id=uuid4(), status="open")
    monkeypatch.setattr(service.repo, "get_hallucination", lambda _id: row)
    with pytest.raises(GovernanceValidationError):
        service.resolve_hallucination(
            hallucination_id=row.id,
            payload=HallucinationResolveRequest(action="resolved"),
        )


def test_resolve_hallucination_commits(monkeypatch):
    db = _FakeDB()
    service = GovernanceService(db=db)
    row = SimpleNamespace(
        id=uuid4(),
        status="open",
        reviewer_id=None,
        resolved_at=datetime.now(timezone.utc),
    )
    monkeypatch.setattr(service.repo, "get_hallucination", lambda _id: row)
    monkeypatch.setattr(
        service.repo,
        "update_hallucination_status",
        lambda row, status, resolution_note, reviewer_id: SimpleNamespace(
            id=row.id,
            status=status,
            reviewer_id=reviewer_id,
            resolved_at=row.resolved_at,
        ),
    )

    out = service.resolve_hallucination(
        hallucination_id=row.id,
        payload=HallucinationResolveRequest(action="dismissed", reviewer_id=uuid4()),
    )
    assert out.status == "dismissed"
    assert db.committed is True
