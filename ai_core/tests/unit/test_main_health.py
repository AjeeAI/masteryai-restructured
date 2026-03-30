from fastapi.testclient import TestClient

from ai_core.main import app


def test_health_reports_internal_service_key_configuration(monkeypatch):
    monkeypatch.setenv("INTERNAL_SERVICE_KEY", "secret-key")
    monkeypatch.setattr(
        "ai_core.main.telemetry_snapshot",
        lambda: {
            "status": "ok",
            "event_count": 1,
            "events": {
                "tutor.chat": {
                    "count": 1,
                    "last_duration_ms": 12.5,
                    "avg_duration_ms": 12.5,
                    "max_duration_ms": 12.5,
                    "last_seen_at": "2026-03-13T10:00:00+00:00",
                    "last_fields": {"mode": "teach"},
                }
            },
        },
    )
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["checks"]["internal_service_key"] == "configured"
    assert response.json()["runtime"]["telemetry"]["event_count"] == 1
