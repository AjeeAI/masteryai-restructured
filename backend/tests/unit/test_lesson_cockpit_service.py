from uuid import uuid4

from backend.schemas.course_schema import CourseBootstrapOut, CourseBootstrapTopicOut
from backend.schemas.graph_learning_schema import GraphNextStepOut, LessonGraphContextOut
from backend.schemas.lesson_cockpit_schema import LessonCockpitBootstrapIn
from backend.schemas.lesson_schema import ContentBlockOut, TopicLessonResponse
from backend.schemas.tutor_schema import TutorSessionBootstrapOut
from backend.services.lesson_cockpit_service import LessonCockpitService, _LESSON_COCKPIT_CACHE


def _course_bootstrap(student_id, topic_id):
    return CourseBootstrapOut(
        student_id=student_id,
        subject="math",
        sss_level="SSS2",
        term=2,
        topics=[
            CourseBootstrapTopicOut(
                topic_id=str(uuid4()),
                title="Linear Inequalities",
                sss_level="SSS2",
                term=2,
                subject_id=str(uuid4()),
                status="mastered",
            ),
            CourseBootstrapTopicOut(
                topic_id=str(topic_id),
                title="Sequences and Series",
                sss_level="SSS2",
                term=2,
                subject_id=str(uuid4()),
                status="current",
            ),
            CourseBootstrapTopicOut(
                topic_id=str(uuid4()),
                title="Probability Basics",
                sss_level="SSS2",
                term=2,
                subject_id=str(uuid4()),
                status="ready",
            ),
        ],
        next_step=None,
        intervention_timeline=[],
        map_error=None,
        warmed_topic_ids=[],
        cache_hit_topic_ids=[],
        failed_topic_ids=[],
    )


def _tutor_bootstrap(student_id, topic_id):
    return TutorSessionBootstrapOut(
        session_id=uuid4(),
        session_started=True,
        greeting="Ready.",
        topic_id=topic_id,
        lesson=TopicLessonResponse(
            topic_id=str(topic_id),
            title="Lesson: Sequences and Series",
            summary="Structured lesson.",
            estimated_duration_minutes=18,
            content_blocks=[ContentBlockOut(type="text", value="Intro", url=None)],
            covered_concepts=[],
            prerequisites=[],
            weakest_concepts=[],
            next_unlock=None,
            why_this_matters="Builds later algebra.",
            assessment_ready=True,
        ),
        graph_context=LessonGraphContextOut.model_validate(
            {
                "student_id": str(student_id),
                "subject": "math",
                "sss_level": "SSS2",
                "term": 2,
                "topic_id": str(topic_id),
                "topic_title": "Sequences and Series",
                "overall_mastery": 0.42,
                "current_concepts": [],
                "prerequisite_concepts": [],
                "downstream_concepts": [],
                "weakest_concepts": [],
                "graph_nodes": [],
                "graph_edges": [],
                "next_unlock": None,
                "why_this_matters": "Builds later algebra.",
            }
        ),
        suggested_actions=[],
        pending_assessment=None,
        next_unlock=GraphNextStepOut(
            topic_id=str(uuid4()),
            topic_title="Probability Basics",
            concept_id=None,
            concept_label=None,
            reason="Next",
        ),
        why_this_topic="Builds later algebra.",
        graph_nodes=[],
        graph_edges=[],
        assessment_ready=True,
    )


def test_lesson_cockpit_bootstrap_merges_course_and_tutor_context(monkeypatch):
    student_id = uuid4()
    topic_id = uuid4()
    _LESSON_COCKPIT_CACHE.clear()

    monkeypatch.setattr(
        "backend.services.lesson_cockpit_service.CourseExperienceService.bootstrap",
        lambda self, **kwargs: _course_bootstrap(student_id, topic_id),
    )
    monkeypatch.setattr(
        "backend.services.lesson_cockpit_service.LessonExperienceService.bootstrap",
        lambda self, payload: _tutor_bootstrap(student_id, topic_id),
    )
    monkeypatch.setattr(
        "backend.services.lesson_cockpit_service.LessonExperienceService.prewarm_related_topics",
        lambda **kwargs: {"warmed_topic_ids": [str(kwargs["topic_ids"][0])], "cache_hit_topic_ids": [], "failed_topic_ids": []},
    )
    monkeypatch.setattr(
        "backend.services.lesson_cockpit_service.GraphRepository.get_mastery_map",
        lambda self, **kwargs: {},
    )
    monkeypatch.setattr(
        "backend.services.lesson_cockpit_service.PrewarmJobService.enqueue_lesson_related",
        lambda self, **kwargs: None,
    )

    payload = LessonCockpitBootstrapIn(
        student_id=student_id,
        subject="math",
        sss_level="SSS2",
        term=2,
        topic_id=topic_id,
    )

    result = LessonCockpitService(db=object()).bootstrap(payload)

    assert result.student_id == student_id
    assert len(result.topics) == 3
    assert result.tutor_bootstrap.lesson.title == "Lesson: Sequences and Series"
    assert result.why_topic_detail is not None
    assert result.why_topic_detail.explanation == "Builds later algebra."
    assert result.intervention_timeline == []
    assert result.warmed_topic_ids


def test_lesson_cockpit_bootstrap_uses_cache_and_can_invalidate(monkeypatch):
    student_id = uuid4()
    topic_id = uuid4()
    _LESSON_COCKPIT_CACHE.clear()

    call_count = {"course": 0, "lesson": 0, "prewarm": 0}

    def _course(self, **kwargs):
        call_count["course"] += 1
        return _course_bootstrap(student_id, topic_id)

    def _lesson(self, payload):
        call_count["lesson"] += 1
        return _tutor_bootstrap(student_id, topic_id)

    def _prewarm(**kwargs):
        call_count["prewarm"] += 1
        return {"warmed_topic_ids": [], "cache_hit_topic_ids": [], "failed_topic_ids": []}

    monkeypatch.setattr("backend.services.lesson_cockpit_service.CourseExperienceService.bootstrap", _course)
    monkeypatch.setattr("backend.services.lesson_cockpit_service.LessonExperienceService.bootstrap", _lesson)
    monkeypatch.setattr("backend.services.lesson_cockpit_service.LessonExperienceService.prewarm_related_topics", _prewarm)
    monkeypatch.setattr(
        "backend.services.lesson_cockpit_service.GraphRepository.get_mastery_map",
        lambda self, **kwargs: {},
    )
    monkeypatch.setattr(
        "backend.services.lesson_cockpit_service.PrewarmJobService.enqueue_lesson_related",
        lambda self, **kwargs: None,
    )

    payload = LessonCockpitBootstrapIn(
        student_id=student_id,
        subject="math",
        sss_level="SSS2",
        term=2,
        topic_id=topic_id,
    )

    service = LessonCockpitService(db=object())
    first = service.bootstrap(payload)
    second = service.bootstrap(payload)

    assert first.tutor_bootstrap.session_id == second.tutor_bootstrap.session_id
    assert call_count == {"course": 1, "lesson": 1, "prewarm": 1}

    LessonCockpitService.invalidate_scope_cache(
        student_id=student_id,
        subject="math",
        sss_level="SSS2",
        term=2,
    )

    third = service.bootstrap(payload)

    assert third.tutor_bootstrap.session_id != second.tutor_bootstrap.session_id
    assert call_count == {"course": 2, "lesson": 2, "prewarm": 2}
