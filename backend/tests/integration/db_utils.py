from __future__ import annotations

import os

import pytest


def _is_truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def resolve_test_database_url(*, test_label: str, allow_dev_env: str = "E2E_ALLOW_DEV_DB") -> str:
    """Return a PostgreSQL test database URL or skip the test module.

    Prefer TEST_DATABASE_URL. Allow DATABASE_URL only when explicitly opted in.
    """
    test_url = os.getenv("TEST_DATABASE_URL", "").strip()
    if test_url:
        if not test_url.startswith("postgresql"):
            pytest.skip(
                f"{test_label} requires PostgreSQL TEST_DATABASE_URL.",
                allow_module_level=True,
            )
        return test_url

    if not _is_truthy(os.getenv(allow_dev_env)):
        pytest.skip(
            f"{test_label} requires TEST_DATABASE_URL (PostgreSQL). "
            f"Set {allow_dev_env}=1 to reuse DATABASE_URL.",
            allow_module_level=True,
        )

    dev_url = os.getenv("DATABASE_URL", "").strip()
    if not dev_url:
        pytest.skip(
            f"{test_label} requires DATABASE_URL when {allow_dev_env}=1 is set.",
            allow_module_level=True,
        )
    if not dev_url.startswith("postgresql"):
        pytest.skip(
            f"{test_label} requires PostgreSQL DATABASE_URL.",
            allow_module_level=True,
        )
    return dev_url
