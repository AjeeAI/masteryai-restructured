from pathlib import Path

from backend.scripts import reset_and_reseed_curriculum as reseed
from backend.scripts import seed_lessons


def test_build_seed_candidates_prefers_json_topics(tmp_path: Path):
    topic_file = tmp_path / "civic" / "our-values.json"
    topic_file.parent.mkdir(parents=True, exist_ok=True)
    topic_file.write_text(
        """
        {
          "subject": "civic",
          "sss_level": "SSS1",
          "term": 1,
          "week": 2,
          "topic_title": "Our Values",
          "sections": [{"heading": "Meaning of Values", "content": "Values are important to us."}]
        }
        """,
        encoding="utf-8",
    )

    candidates = seed_lessons._build_seed_candidates(tmp_path)

    match = next(
        (
            candidate
            for candidate in candidates
            if candidate.subject == "civic"
            and candidate.sss_level == "SSS1"
            and candidate.term == 1
            and candidate.title == "Our Values"
        ),
        None,
    )
    assert match is not None
    assert match.source_file == "our-values.json"
    assert "Values are important to us." in match.text


def test_reset_default_source_root_prefers_canonical_json(monkeypatch, tmp_path: Path):
    canonical_root = tmp_path / "docs" / "Curriculum_in_json"
    legacy_root = tmp_path / "docs" / "SSS_NOTES_2026"
    canonical_root.mkdir(parents=True, exist_ok=True)
    legacy_root.mkdir(parents=True, exist_ok=True)
    (canonical_root / "topic.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(reseed, "CANONICAL_CURRICULUM_ROOT", canonical_root)
    monkeypatch.setattr(reseed, "LEGACY_CURRICULUM_ROOT", legacy_root)

    assert reseed._default_source_root() == str(canonical_root)
