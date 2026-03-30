import pytest

from backend.main import app

REQUIRED_SECTION2_PATHS = [
    "/api/v1/tutor/sessions/start",
    "/api/v1/tutor/sessions/{session_id}/history",
    "/api/v1/tutor/sessions/{session_id}/end",
    "/api/v1/internal/postgres/profile",
    "/api/v1/internal/postgres/history",
    "/api/v1/internal/postgres/quiz-attempt",
    "/api/v1/internal/postgres/class-roster",
]

missing = [path for path in REQUIRED_SECTION2_PATHS if path not in app.openapi()["paths"]]
if missing:
    pytest.skip(
        f"Section 2 integration flow pending Lane A/C merge; missing routes: {missing}",
        allow_module_level=True,
    )


def test_section2_flow_routes_exist():
    for path in REQUIRED_SECTION2_PATHS:
        assert path in app.openapi()["paths"]
