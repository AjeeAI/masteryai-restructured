from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.schemas.admin_curriculum_schema import (
    CurriculumBulkIngestRequest,
    CurriculumUploadRequest,
    CurriculumUploadResponse,
)
from backend.services.admin_curriculum_service import (
    AdminCurriculumService,
    AdminCurriculumValidationError,
)


def test_upload_curriculum_rejects_invalid_source_root():
    service = AdminCurriculumService(db=object())
    payload = CurriculumUploadRequest(
        subject="math",
        sss_level="SSS1",
        term=1,
        source_root="Z:/path/that/does/not/exist",
    )
    with pytest.raises(AdminCurriculumValidationError):
        service.upload_curriculum(payload=payload, actor_user_id=uuid4())


def test_collect_supported_files_handles_docx_and_txt(tmp_path: Path):
    (tmp_path / "one.docx").write_bytes(b"fake")
    (tmp_path / "two.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "three.pdf").write_bytes(b"fake")

    supported, skipped = AdminCurriculumService._collect_supported_files(tmp_path)
    supported_names = sorted(path.name for path in supported)
    skipped_names = sorted(path.name for path in skipped)

    assert supported_names == ["one.docx", "two.txt"]
    assert skipped_names == ["three.pdf"]


def test_extract_document_chunks_builds_scoped_concepts(tmp_path: Path):
    topic_id = uuid4()
    topic = SimpleNamespace(id=topic_id, title="Linear Equations")

    text_file = tmp_path / "linear_equations_notes.txt"
    text_file.write_text(
        "LINEAR EQUATIONS\n"
        "Definition and examples.\n"
        "\n"
        "SIMULTANEOUS EQUATIONS\n"
        "Elimination and substitution methods.\n",
        encoding="utf-8",
    )

    service = AdminCurriculumService(db=object())
    parsed = service._extract_document_chunks(
        file_path=text_file,
        scope_topics=[topic],
        subject="math",
        sss_level="SSS1",
        term=1,
    )

    assert parsed is not None
    assert parsed.topic_id == topic_id
    assert parsed.concept_sections
    assert all(section.concept_id.startswith("math:sss1:t1:") for section in parsed.concept_sections)
    assert all(section.chunks for section in parsed.concept_sections)


def test_build_structured_lesson_from_json(tmp_path: Path):
    json_file = tmp_path / "our-values.json"
    json_file.write_text(
        """
        {
          "subject": "civic",
          "sss_level": "SSS1",
          "term": 1,
          "week": 2,
          "topic_title": "Our Values",
          "topic_slug": "our-values",
          "source_title": "First Term SS1 Civic Education",
          "learning_objectives": ["Define values", "State the importance of values"],
          "sections": [
            {"heading": "Meaning of Values", "content": "Values are things that are important to us."},
            {"heading": "Importance of Values", "content": "Values guide behaviour and choices."}
          ],
          "keywords": ["values", "importance"]
        }
        """,
        encoding="utf-8",
    )

    lesson = AdminCurriculumService._build_structured_lesson_from_json(json_file)

    assert lesson["title"] == "Lesson: Our Values"
    assert lesson["summary"] == "Define values; State the importance of values."
    assert lesson["content_blocks"][0]["heading"] == "Learning Objectives"
    assert lesson["content_blocks"][1]["heading"] == "Meaning of Values"
    assert lesson["content_blocks"][-1]["heading"] == "Key Terms"
    assert lesson["estimated_duration_minutes"] >= 10


def test_infer_scope_from_json_payload_even_when_path_is_unhelpful(tmp_path: Path):
    json_file = tmp_path / "incoming" / "topic.json"
    json_file.parent.mkdir(parents=True, exist_ok=True)
    json_file.write_text(
        """
        {
          "subject": "math",
          "sss_level": "SSS2",
          "term": 3,
          "week": 1,
          "topic_title": "Trigonometric Ratios",
          "sections": [{"heading": "Intro", "content": "Angles and ratios."}]
        }
        """,
        encoding="utf-8",
    )

    inferred = AdminCurriculumService._infer_scope_from_file(root=tmp_path, file_path=json_file)

    assert inferred == ("math", "SSS2", 3)


def test_get_ingestion_status_maps_repository_rows(monkeypatch):
    service = AdminCurriculumService(db=object())
    now = datetime.now(timezone.utc)
    fake_job = SimpleNamespace(
        id=uuid4(),
        version_id=uuid4(),
        status="completed",
        progress_percent=100,
        current_stage="completed",
        processed_files_count=3,
        processed_chunks_count=42,
        error_message=None,
        created_at=now,
        updated_at=now,
    )
    monkeypatch.setattr(service.repo, "list_ingestion_jobs", lambda job_id=None: [fake_job])

    out = service.get_ingestion_status()
    assert len(out.jobs) == 1
    assert out.jobs[0].status == "completed"
    assert out.jobs[0].processed_chunks_count == 42


@pytest.mark.parametrize(
    ("path_text", "expected"),
    [
        ("SS1 FIRST TERM/FIRST TERM SS1 ENGLISH LANGUAGE.docx", ("english", "SSS1", 1)),
        ("SS2 SECOND TERM/SECOND TERM SS2 MATHEMATICS.docx", ("math", "SSS2", 2)),
        ("SS3 THIRD TERM/THIRD TERM SS3 CIVIC EDUCATION.docx", ("civic", "SSS3", 3)),
        ("misc/unknown_file.docx", None),
    ],
)
def test_infer_scope_from_file(path_text: str, expected):
    service = AdminCurriculumService(db=object())
    root = Path("docs")
    inferred = service._infer_scope_from_file(root=root, file_path=root / path_text)
    assert inferred == expected


def test_ingest_all_from_source_root_returns_approve_ready_versions(tmp_path: Path, monkeypatch):
    english_file = tmp_path / "SS1 FIRST TERM" / "FIRST TERM SS1 ENGLISH LANGUAGE.docx"
    math_file = tmp_path / "SS1 FIRST TERM" / "FIRST TERM SS1 MATHEMATICS.docx"
    english_file.parent.mkdir(parents=True, exist_ok=True)
    english_file.write_bytes(b"fake")
    math_file.write_bytes(b"fake")

    service = AdminCurriculumService(db=object())

    def _fake_upload(payload, actor_user_id):
        return CurriculumUploadResponse(
            version_id=uuid4(),
            job_id=uuid4(),
            status="pending_approval",
            discovered_files=1,
            skipped_files=0,
            processed_chunks=10,
        )

    monkeypatch.setattr(service, "upload_curriculum", _fake_upload)

    out = service.ingest_all_from_source_root(
        payload=CurriculumBulkIngestRequest(source_root=str(tmp_path)),
        actor_user_id=uuid4(),
    )
    assert out.discovered_scopes == 2
    assert out.failed_scopes == 0
    assert len(out.approve_ready_version_ids) == 2
