import pytest

from ai_core.core_engine.curriculum.policies import (
    CurriculumPolicyError,
    assert_sss_level_allowed,
    assert_term_allowed,
)


def test_sss_allowed():
    for lvl in ["SSS1", "SSS2", "SSS3"]:
        assert_sss_level_allowed(lvl)


def test_sss_reject():
    with pytest.raises(CurriculumPolicyError):
        assert_sss_level_allowed("SS1")


def test_term_allowed():
    for t in [1, 2, 3]:
        assert_term_allowed(t)


def test_term_reject():
    with pytest.raises(CurriculumPolicyError):
        assert_term_allowed(4)
