from backend.services import system_health_service
from backend.services.system_health_service import SystemHealthService


def test_snapshot_includes_runtime_telemetry_and_cache_state(monkeypatch):
    service = SystemHealthService()

    monkeypatch.setattr(service, "_check_postgres", lambda: {"status": "ok"})
    monkeypatch.setattr(service, "_check_schema", lambda: {"status": "ok"})
    monkeypatch.setattr(service, "_check_redis", lambda: {"status": "not_configured"})
    monkeypatch.setattr(service, "_check_neo4j", lambda: {"status": "not_configured"})
    monkeypatch.setattr(service, "_check_vector_db", lambda: {"status": "ok"})
    monkeypatch.setattr(service, "_check_llm_api", lambda: {"status": "configured"})
    monkeypatch.setattr(
        system_health_service,
        "telemetry_snapshot",
        lambda: {
            "status": "ok",
            "event_count": 1,
            "events": {
                "lesson.cockpit.bootstrap": {
                    "count": 2,
                    "last_duration_ms": 44.1,
                    "avg_duration_ms": 41.2,
                    "max_duration_ms": 44.1,
                    "last_seen_at": "2026-03-13T10:00:00+00:00",
                    "last_fields": {"cache_hit": False},
                }
            },
        },
    )
    monkeypatch.setattr(
        system_health_service.LessonExperienceService,
        "cache_snapshot",
        classmethod(
            lambda cls: {
                "status": "ok",
                "bootstrap_cache": {"entries": 3, "preview_entries": 1, "ttl_seconds": 30.0},
                "topic_snapshot_cache": {"entries": 5, "ttl_seconds": 180.0},
            }
        ),
    )
    monkeypatch.setattr(
        system_health_service.LessonCockpitService,
        "cache_snapshot",
        classmethod(lambda cls: {"status": "ok", "bootstrap_cache": {"entries": 2, "ttl_seconds": 30.0}}),
    )
    monkeypatch.setattr(
        system_health_service.CourseExperienceService,
        "cache_snapshot",
        classmethod(lambda cls: {"status": "ok", "bootstrap_cache": {"entries": 4, "ttl_seconds": 30.0}}),
    )
    monkeypatch.setattr(
        system_health_service.DashboardExperienceService,
        "cache_snapshot",
        classmethod(lambda cls: {"status": "ok", "bootstrap_cache": {"entries": 1, "ttl_seconds": 30.0}}),
    )
    monkeypatch.setattr(
        system_health_service.PrewarmJobService,
        "snapshot",
        classmethod(
            lambda cls: {
                "status": "ok",
                "worker_enabled": True,
                "worker_alive": True,
                "poll_seconds": 5.0,
                "batch_size": 4,
                "counts": {"queued": 1, "running": 0, "failed": 0},
            }
        ),
    )

    snapshot = service.snapshot()

    assert snapshot["status"] == "ok"
    assert snapshot["checks"]["prewarm_queue"]["worker_alive"] is True
    assert snapshot["runtime"]["telemetry"]["event_count"] == 1
    assert snapshot["runtime"]["caches"]["lesson_experience"]["bootstrap_cache"]["entries"] == 3
    assert snapshot["runtime"]["caches"]["course_experience"]["bootstrap_cache"]["entries"] == 4


def test_snapshot_degrades_when_schema_is_missing(monkeypatch):
    service = SystemHealthService()

    monkeypatch.setattr(service, "_check_postgres", lambda: {"status": "ok"})
    monkeypatch.setattr(
        service,
        "_check_schema",
        lambda: {"status": "error", "missing_tables": ["personalized_lessons"], "detail": "Critical graph-first tables are missing."},
    )
    monkeypatch.setattr(service, "_check_redis", lambda: {"status": "not_configured"})
    monkeypatch.setattr(service, "_check_neo4j", lambda: {"status": "not_configured"})
    monkeypatch.setattr(service, "_check_vector_db", lambda: {"status": "ok"})
    monkeypatch.setattr(service, "_check_llm_api", lambda: {"status": "configured"})
    monkeypatch.setattr(system_health_service, "telemetry_snapshot", lambda: {"status": "ok", "event_count": 0, "events": {}})
    monkeypatch.setattr(
        system_health_service.LessonExperienceService,
        "cache_snapshot",
        classmethod(lambda cls: {"status": "ok", "bootstrap_cache": {"entries": 0, "preview_entries": 0, "ttl_seconds": 30.0}, "topic_snapshot_cache": {"entries": 0, "ttl_seconds": 180.0}}),
    )
    monkeypatch.setattr(
        system_health_service.LessonCockpitService,
        "cache_snapshot",
        classmethod(lambda cls: {"status": "ok", "bootstrap_cache": {"entries": 0, "ttl_seconds": 30.0}}),
    )
    monkeypatch.setattr(
        system_health_service.CourseExperienceService,
        "cache_snapshot",
        classmethod(lambda cls: {"status": "ok", "bootstrap_cache": {"entries": 0, "ttl_seconds": 30.0}}),
    )
    monkeypatch.setattr(
        system_health_service.DashboardExperienceService,
        "cache_snapshot",
        classmethod(lambda cls: {"status": "ok", "bootstrap_cache": {"entries": 0, "ttl_seconds": 30.0}}),
    )
    monkeypatch.setattr(
        system_health_service.PrewarmJobService,
        "snapshot",
        classmethod(lambda cls: {"status": "ok", "worker_enabled": True, "worker_alive": True, "poll_seconds": 5.0, "batch_size": 4, "counts": {"queued": 0, "running": 0, "failed": 0}}),
    )

    snapshot = service.snapshot()

    assert snapshot["status"] == "degraded"
    assert snapshot["checks"]["schema"]["missing_tables"] == ["personalized_lessons"]
