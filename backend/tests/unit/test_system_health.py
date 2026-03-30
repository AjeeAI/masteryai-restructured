from backend.endpoints import system


def test_health_returns_service_snapshot(monkeypatch):
    expected = {
        "status": "ok",
        "timestamp": "2026-02-28T00:00:00Z",
        "checks": {"postgres": {"status": "ok"}},
    }
    monkeypatch.setattr(system._health_service, "snapshot", lambda: expected)
    assert system.health() == expected
