from uuid import uuid4

from backend.schemas.graph_learning_schema import GraphNextStepOut, LessonGraphContextOut
from backend.services.lesson_experience_service import LessonExperienceService, _TopicSnapshot


class _FakeRepo:
    def __init__(self, db):
        self.db = db

    def session_exists_for_student(self, *, session_id, student_id):
        return True

    def create_session(self, *, student_id, subject, term):
        return {"id": str(uuid4())}


class _FakeAssessmentService:
    def __init__(self, db):
        self.db = db

    def get_pending_assessment(self, *, session_id):
        return None


class _Payload:
    def __init__(self, **kwargs):
        self.student_id = kwargs["student_id"]
        self.subject = kwargs["subject"]
        self.sss_level = kwargs["sss_level"]
        self.term = kwargs["term"]
        self.topic_id = kwargs["topic_id"]
        self.session_id = kwargs.get("session_id")


def _payload(**overrides):
    base = {
        "student_id": uuid4(),
        "subject": "math",
        "sss_level": "SSS2",
        "term": 1,
        "topic_id": uuid4(),
        "session_id": None,
    }
    base.update(overrides)
    return _Payload(**base)


def _graph_context(topic_id, topic_title="Linear Equations"):
    next_unlock = GraphNextStepOut(
        topic_id=str(uuid4()),
        topic_title="Simultaneous Equations",
        concept_id="math:sss2:t1:simultaneous-equations",
        concept_label="Simultaneous Equations",
        reason="Next",
    )
    return LessonGraphContextOut.model_validate(
        {
            "student_id": str(uuid4()),
            "subject": "math",
            "sss_level": "SSS2",
            "term": 1,
            "topic_id": str(topic_id),
            "topic_title": topic_title,
            "overall_mastery": 0.42,
            "current_concepts": [
                {
                    "concept_id": "math:sss2:t1:variables",
                    "label": "Variables",
                    "topic_id": str(topic_id),
                    "topic_title": topic_title,
                    "mastery_score": 0.42,
                    "mastery_state": "needs_review",
                    "role": "current",
                    "is_unlocked": True,
                }
            ],
            "prerequisite_concepts": [],
            "downstream_concepts": [],
            "weakest_concepts": [
                {
                    "concept_id": "math:sss2:t1:variables",
                    "label": "Variables",
                    "topic_id": str(topic_id),
                    "topic_title": topic_title,
                    "mastery_score": 0.42,
                    "mastery_state": "needs_review",
                    "role": "current",
                    "is_unlocked": True,
                }
            ],
            "graph_nodes": [],
            "graph_edges": [],
            "next_unlock": next_unlock.model_dump(),
            "why_this_matters": "This unlocks simultaneous equations.",
        }
    )


def test_bootstrap_reuses_mastery_snapshot_cache(monkeypatch):
    payload = _payload(session_id=uuid4())
    build_calls = {"count": 0}

    monkeypatch.setattr("backend.services.lesson_experience_service.TutorSessionRepository", _FakeRepo)
    monkeypatch.setattr("backend.services.lesson_experience_service.TutorAssessmentService", _FakeAssessmentService)

    def _build_snapshot(cls, **kwargs):
        build_calls["count"] += 1
        graph_context = _graph_context(payload.topic_id)
        return (
            _TopicSnapshot(
                lesson={
                    "topic_id": str(payload.topic_id),
                    "title": "Lesson: Linear Equations",
                    "summary": "Understand variables and equations.",
                    "estimated_duration_minutes": 18,
                    "content_blocks": [{"type": "text", "value": "Intro"}],
                    "covered_concepts": [],
                    "prerequisites": [],
                    "weakest_concepts": [],
                    "next_unlock": None,
                    "why_this_matters": None,
                    "assessment_ready": True,
                },
                graph_context=graph_context,
                why_this_topic="This unlocks simultaneous equations.",
                next_unlock=graph_context.next_unlock,
                graph_nodes=[],
                graph_edges=[],
            ),
            "fresh",
        )

    monkeypatch.setattr(LessonExperienceService, "_build_topic_snapshot", classmethod(_build_snapshot))

    service = LessonExperienceService(db=object())
    first = service.bootstrap(payload)
    second = service.bootstrap(payload)

    assert build_calls["count"] == 1
    assert first.lesson.title == "Lesson: Linear Equations"
    assert second.why_this_topic == "This unlocks simultaneous equations."


def test_prewarm_topics_reports_cache_hits_and_failures(monkeypatch):
    student_id = uuid4()
    topic_a = uuid4()
    topic_b = uuid4()

    def _build_snapshot(cls, **kwargs):
        if kwargs["topic_id"] == topic_a:
            graph_context = _graph_context(topic_a)
            return (
                _TopicSnapshot(
                    lesson={},
                    graph_context=graph_context,
                    why_this_topic=None,
                    next_unlock=None,
                    graph_nodes=[],
                    graph_edges=[],
                ),
                "cache",
            )
        raise RuntimeError("boom")

    monkeypatch.setattr(LessonExperienceService, "_build_topic_snapshot", classmethod(_build_snapshot))

    result = LessonExperienceService.prewarm_topics(
        student_id=student_id,
        subject="math",
        sss_level="SSS2",
        term=1,
        topic_ids=[topic_a, topic_b],
    )

    assert result["cache_hit_topic_ids"] == [str(topic_a)]
    assert result["failed_topic_ids"] == [str(topic_b)]


def test_bootstrap_uses_preview_cache_before_rebuilding_snapshot(monkeypatch):
    payload = _payload(session_id=None)
    build_calls = {"count": 0}

    monkeypatch.setattr("backend.services.lesson_experience_service.TutorSessionRepository", _FakeRepo)
    monkeypatch.setattr("backend.services.lesson_experience_service.TutorAssessmentService", _FakeAssessmentService)

    def _build_snapshot(cls, **kwargs):
        build_calls["count"] += 1
        graph_context = _graph_context(payload.topic_id, topic_title="Electoral Process")
        return (
            _TopicSnapshot(
                lesson={
                    "topic_id": str(payload.topic_id),
                    "title": "Lesson: Electoral Process",
                    "summary": "Understand lawful participation and fair voting.",
                    "estimated_duration_minutes": 16,
                    "content_blocks": [{"type": "text", "value": "Intro"}],
                    "covered_concepts": [],
                    "prerequisites": [],
                    "weakest_concepts": [],
                    "next_unlock": None,
                    "why_this_matters": None,
                    "assessment_ready": True,
                },
                graph_context=graph_context,
                why_this_topic="This supports responsible civic participation.",
                next_unlock=graph_context.next_unlock,
                graph_nodes=[],
                graph_edges=[],
            ),
            "fresh",
        )

    monkeypatch.setattr(LessonExperienceService, "_build_topic_snapshot", classmethod(_build_snapshot))

    preview = LessonExperienceService.prewarm_bootstrap_preview(
        student_id=payload.student_id,
        subject=payload.subject,
        sss_level=payload.sss_level,
        term=int(payload.term),
        topic_ids=[payload.topic_id],
    )

    assert preview["warmed_topic_ids"] == [str(payload.topic_id)]

    service = LessonExperienceService(db=object())
    out = service.bootstrap(payload)

    assert build_calls["count"] == 1
    assert out.session_started is True
    assert out.lesson.title == "Lesson: Electoral Process"
