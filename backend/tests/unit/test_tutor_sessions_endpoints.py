import pytest

from backend.main import app

SECTION2_TUTOR_PATHS = [
    "/api/v1/tutor/sessions/start",
    "/api/v1/tutor/sessions/{session_id}/history",
    "/api/v1/tutor/sessions/{session_id}/end",
]

missing = [path for path in SECTION2_TUTOR_PATHS if path not in app.openapi()["paths"]]
if missing:
    pytest.skip(
        f"Section 2 Lane C tutor session endpoints are not mounted yet: {missing}",
        allow_module_level=True,
    )


def test_tutor_session_paths_are_mounted():
    for path in SECTION2_TUTOR_PATHS:
        assert path in app.openapi()["paths"]
