"""Hard constraints: SSS1-SSS3 only and Term 1-3 only."""

from __future__ import annotations

from ai_core.core_engine.config.constants import SSSLevel, Term


class CurriculumPolicyError(ValueError):
    pass


def assert_sss_level_allowed(sss_level: str) -> None:
    try:
        SSSLevel(sss_level)
    except Exception as e:
        raise CurriculumPolicyError(
            f"Unsupported SSS level: {sss_level}. Allowed: SSS1-SSS3."
        ) from e


def assert_term_allowed(term: int) -> None:
    try:
        Term(term)
    except Exception as e:
        raise CurriculumPolicyError(f"Unsupported term: {term}. Allowed: 1-3.") from e
