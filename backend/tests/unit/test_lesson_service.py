import types
import uuid

import pytest

from backend.services import lesson_service as svc


def _obj(**kwargs):
    return types.SimpleNamespace(**kwargs)


def test_fetch_topic_lesson_success(monkeypatch):
    student_profile_id = uuid.uuid4()
    student_id = uuid.uuid4()
    topic_id = uuid.uuid4()
    subject_id = uuid.uuid4()

    monkeypatch.setattr(
        svc,
        "get_student_profile",
        lambda db, sid: _obj(id=student_profile_id, student_id=sid, sss_level="SSS1", active_term=1),
    )
    monkeypatch.setattr(
        svc,
        "get_topic_with_subject",
        lambda db, tid: (
            _obj(
                id=tid,
                subject_id=subject_id,
                is_approved=True,
                sss_level="SSS1",
                term=1,
                title="Linear Equations",
                curriculum_version_id=uuid.uuid4(),
            ),
            _obj(slug="math"),
        ),
    )
    monkeypatch.setattr(svc, "student_enrolled_in_subject", lambda db, spid, sid: True)
    monkeypatch.setattr(
        svc,
        "get_lesson_with_blocks",
        lambda db, tid: _obj(
            id=uuid.uuid4(),
            title="Lesson: Linear Equations",
            blocks=[
                _obj(block_type="text", content={"text": "Intro"}, order_index=1),
                _obj(block_type="video", content={"url": "https://example.com/v1"}, order_index=2),
            ],
        ),
    )

    response = svc.fetch_topic_lesson(db=None, topic_id=topic_id, student_id=student_id)

    assert response["topic_id"] == str(topic_id)
    assert response["title"] == "Lesson: Linear Equations"
    assert response["content_blocks"][0] == {"type": "text", "value": "Intro"}
    assert response["content_blocks"][1] == {"type": "video", "url": "https://example.com/v1"}


def test_fetch_topic_lesson_forbidden_when_profile_missing(monkeypatch):
    monkeypatch.setattr(svc, "get_student_profile", lambda db, sid: None)

    with pytest.raises(svc.ForbiddenLessonAccess, match="Student profile not found"):
        svc.fetch_topic_lesson(db=None, topic_id=uuid.uuid4(), student_id=uuid.uuid4())


def test_fetch_topic_lesson_forbidden_when_out_of_scope(monkeypatch):
    topic_id = uuid.uuid4()

    monkeypatch.setattr(
        svc,
        "get_student_profile",
        lambda db, sid: _obj(id=uuid.uuid4(), student_id=sid, sss_level="SSS2", active_term=1),
    )
    monkeypatch.setattr(
        svc,
        "get_topic_with_subject",
        lambda db, tid: (
            _obj(id=tid, subject_id=uuid.uuid4(), is_approved=True, sss_level="SSS1", term=1, title="t"),
            _obj(slug="math"),
        ),
    )

    with pytest.raises(svc.ForbiddenLessonAccess, match="Topic level out of scope"):
        svc.fetch_topic_lesson(db=None, topic_id=topic_id, student_id=uuid.uuid4())


def test_fetch_topic_lesson_not_found_when_lesson_missing(monkeypatch):
    topic_id = uuid.uuid4()
    subject_id = uuid.uuid4()

    monkeypatch.setattr(
        svc,
        "get_student_profile",
        lambda db, sid: _obj(id=uuid.uuid4(), student_id=sid, sss_level="SSS1", active_term=1),
    )
    monkeypatch.setattr(
        svc,
        "get_topic_with_subject",
        lambda db, tid: (
            _obj(id=tid, subject_id=subject_id, is_approved=True, sss_level="SSS1", term=1, title="t"),
            _obj(slug="math"),
        ),
    )
    monkeypatch.setattr(svc, "student_enrolled_in_subject", lambda db, spid, sid: True)
    monkeypatch.setattr(svc, "get_lesson_with_blocks", lambda db, tid: None)

    with pytest.raises(
        svc.LessonGenerationError,
        match="No approved curriculum version mapped for this topic",
    ):
        svc.fetch_topic_lesson(db=None, topic_id=topic_id, student_id=uuid.uuid4())


def test_fetch_topic_lesson_uses_structured_curriculum_lesson_before_rag(monkeypatch):
    student_profile_id = uuid.uuid4()
    student_id = uuid.uuid4()
    topic_id = uuid.uuid4()
    subject_id = uuid.uuid4()

    monkeypatch.setattr(
        svc,
        "get_student_profile",
        lambda db, sid: _obj(id=student_profile_id, student_id=sid, sss_level="SSS1", active_term=1),
    )
    monkeypatch.setattr(
        svc,
        "get_topic_with_subject",
        lambda db, tid: (
            _obj(
                id=tid,
                subject_id=subject_id,
                is_approved=True,
                sss_level="SSS1",
                term=1,
                title="Our Values",
                curriculum_version_id=uuid.uuid4(),
            ),
            _obj(slug="civic"),
        ),
    )
    monkeypatch.setattr(svc, "student_enrolled_in_subject", lambda db, spid, sid: True)
    monkeypatch.setattr(
        svc,
        "get_lesson_with_blocks",
        lambda db, tid: _obj(
            id=uuid.uuid4(),
            title="Lesson: Our Values",
            summary="Define values; State the importance of values.",
            estimated_duration_minutes=14,
            blocks=[
                _obj(block_type="text", content={"heading": "Learning Objectives", "text": "- Define values"}, order_index=1),
                _obj(block_type="text", content={"heading": "Meaning of Values", "text": "Values are important."}, order_index=2),
            ],
        ),
    )
    monkeypatch.setattr(svc, "ensure_personalized_lessons_table", lambda db: None)
    monkeypatch.setattr(svc, "_get_mastery_rows", lambda *args, **kwargs: [])
    monkeypatch.setattr(svc, "_mastery_signature", lambda rows: "sig")
    monkeypatch.setattr(svc, "get_personalized_lesson", lambda *args, **kwargs: None)

    def _should_not_generate(**kwargs):
        raise AssertionError("Structured curriculum lesson should be served before RAG generation.")

    monkeypatch.setattr(svc, "_generate_personalized_lesson", _should_not_generate)

    response = svc.fetch_topic_lesson(db=None, topic_id=topic_id, student_id=student_id)

    assert response["title"] == "Lesson: Our Values"
    assert response["summary"] == "Define values; State the importance of values."
    assert response["estimated_duration_minutes"] == 14
    assert response["content_blocks"][0]["value"] == "Learning Objectives\n\n- Define values"
    assert response["content_blocks"][1]["value"] == "Meaning of Values\n\nValues are important."


def test_lesson_response_from_blocks_serializes_graph_models():
    topic_id = uuid.uuid4()
    graph_context = _obj(
        current_concepts=[
            _obj(
                concept_id="math:sss1:t1:current-skill",
                label="Current Skill",
                mastery_score=0.45,
                mastery_state="needs_review",
            )
        ],
        prerequisite_concepts=[
            _obj(
                concept_id="math:sss1:t1:prereq-skill",
                label="Prereq Skill",
                mastery_score=0.82,
                mastery_state="demonstrated",
            )
        ],
        weakest_concepts=[
            _obj(
                concept_id="math:sss1:t1:current-skill",
                label="Current Skill",
                mastery_score=0.45,
                mastery_state="needs_review",
            )
        ],
        next_unlock=_obj(
            concept_id="math:sss1:t1:next-skill",
            concept_label="Next Skill",
            topic_id=str(topic_id),
            topic_title="Next Topic",
            reason="Master the current skill first.",
        ),
        why_this_matters="This skill unlocks the next lesson.",
    )

    response = svc._lesson_response_from_blocks(
        topic=_obj(id=topic_id),
        title="Lesson: Current Skill",
        summary="A focused lesson summary.",
        estimated_duration_minutes=12,
        content_blocks=[{"type": "text", "value": "Intro"}],
        graph_context=graph_context,
    )

    assert response["covered_concepts"][0]["label"] == "Current Skill"
    assert response["prerequisites"][0]["label"] == "Prereq Skill"
    assert response["weakest_concepts"][0]["label"] == "Current Skill"
    assert response["next_unlock"]["concept_label"] == "Next Skill"
    assert response["next_unlock"]["topic_id"] == str(topic_id)
