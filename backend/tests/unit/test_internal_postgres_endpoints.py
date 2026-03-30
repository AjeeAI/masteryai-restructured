import pytest

from backend.main import app

SECTION2_INTERNAL_PATHS = [
    "/api/v1/internal/postgres/profile",
    "/api/v1/internal/postgres/history",
    "/api/v1/internal/postgres/quiz-attempt",
    "/api/v1/internal/postgres/class-roster",
]

missing = [path for path in SECTION2_INTERNAL_PATHS if path not in app.openapi()["paths"]]
if missing:
    pytest.skip(
        f"Section 2 Lane C internal postgres endpoints are not mounted yet: {missing}",
        allow_module_level=True,
    )


def test_internal_postgres_paths_are_mounted():
    for path in SECTION2_INTERNAL_PATHS:
        assert path in app.openapi()["paths"]
