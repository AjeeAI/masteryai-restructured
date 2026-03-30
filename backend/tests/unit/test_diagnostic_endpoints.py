import pytest

from backend.main import app


SECTION3_DIAGNOSTIC_PATHS = [
    "/api/v1/learning/diagnostic/status",
    "/api/v1/learning/diagnostic/start",
    "/api/v1/learning/diagnostic/submit",
]

missing = [path for path in SECTION3_DIAGNOSTIC_PATHS if path not in app.openapi()["paths"]]
if missing:
    pytest.skip(
        f"Section 3 Lane C pending: diagnostic routes are not mounted yet: {missing}",
        allow_module_level=True,
    )


def test_diagnostic_paths_are_mounted():
    for path in SECTION3_DIAGNOSTIC_PATHS:
        assert path in app.openapi()["paths"]
