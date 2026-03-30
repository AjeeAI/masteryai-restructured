from uuid import uuid4

from backend.models.mastery_update_event import MasteryUpdateEvent
from backend.schemas.course_schema import CourseBootstrapOut, CourseBootstrapTopicOut
from backend.services.course_experience_service import CourseExperienceService, _COURSE_BOOTSTRAP_CACHE


def test_course_bootstrap_cache_invalidation_is_scope_specific():
    _COURSE_BOOTSTRAP_CACHE.clear()
    student_id = uuid4()

    scoped_key = CourseExperienceService._cache_key(
        student_id=student_id,
        subject="math",
        sss_level="SSS2",
        term=2,
        mastery_signature="abc123",
    )
    other_key = CourseExperienceService._cache_key(
        student_id=student_id,
        subject="math",
        sss_level="SSS2",
        term=3,
        mastery_signature="def456",
    )

    payload = CourseBootstrapOut(
        student_id=student_id,
        subject="math",
        sss_level="SSS2",
        term=2,
        topics=[],
        next_step=None,
        recent_evidence=None,
        recommendation_story=None,
        map_error=None,
        warmed_topic_ids=[],
        cache_hit_topic_ids=[],
        failed_topic_ids=[],
    )
    CourseExperienceService._write_cached_bootstrap(cache_key=scoped_key, payload=payload)
    CourseExperienceService._write_cached_bootstrap(
        cache_key=other_key,
        payload=payload.model_copy(update={"term": 3}),
    )

    CourseExperienceService.invalidate_scope_cache(
        student_id=student_id,
        subject="math",
        sss_level="SSS2",
        term=2,
    )

    assert scoped_key not in _COURSE_BOOTSTRAP_CACHE
    assert other_key in _COURSE_BOOTSTRAP_CACHE
    _COURSE_BOOTSTRAP_CACHE.clear()


def test_candidate_prewarm_topic_ids_prefers_recommended_current_and_ready_topics():
    recommended_topic_id = uuid4()
    current_topic_id = uuid4()
    ready_topic_id = uuid4()
    locked_topic_id = uuid4()

    topics = [
        CourseBootstrapTopicOut(
            topic_id=str(current_topic_id),
            title="Current Topic",
            sss_level="SSS2",
            term=2,
            subject_id=str(uuid4()),
            lesson_ready=True,
            status="current",
        ),
        CourseBootstrapTopicOut(
            topic_id=str(ready_topic_id),
            title="Ready Topic",
            sss_level="SSS2",
            term=2,
            subject_id=str(uuid4()),
            lesson_ready=True,
            status="ready",
        ),
        CourseBootstrapTopicOut(
            topic_id=str(locked_topic_id),
            title="Locked Topic",
            sss_level="SSS2",
            term=2,
            subject_id=str(uuid4()),
            lesson_ready=False,
            status="locked",
        ),
    ]
    next_step = type("NextStep", (), {"recommended_topic_id": str(recommended_topic_id)})()

    candidate_ids = CourseExperienceService._candidate_prewarm_topic_ids(
        topics=topics,
        next_step=next_step,
    )

    assert candidate_ids == [recommended_topic_id, current_topic_id, ready_topic_id]


def test_scope_intervention_timeline_uses_real_mastery_event_labels():
    student_id = uuid4()
    service = CourseExperienceService(db=None)  # type: ignore[arg-type]
    event = MasteryUpdateEvent(
        student_id=student_id,
        quiz_id=uuid4(),
        attempt_id=None,
        subject="math",
        sss_level="SSS2",
        term=2,
        source="practice",
        concept_breakdown=[],
        new_mastery=[
            {
                "concept_id": "math:sss2:t2:arithmetic-progression",
                "previous_score": 0.32,
                "new_score": 0.61,
                "delta": 0.29,
            },
            {
                "concept_id": "math:sss2:t2:simple-interest",
                "previous_score": 0.58,
                "new_score": 0.42,
                "delta": -0.16,
            },
        ],
    )
    event.created_at = None

    service._recent_scope_events = lambda **kwargs: [event]  # type: ignore[method-assign]
    timeline = service._scope_intervention_timeline(
        student_id=student_id,
        subject="math",
        sss_level="SSS2",
        term=2,
    )

    assert len(timeline) == 1
    assert timeline[0].kind == "quiz"
    assert timeline[0].source_label == "Quiz result"
    assert timeline[0].focus_concept_label == "Simple Interest"
    assert timeline[0].strongest_gain_concept_label == "Arithmetic Progression"
    assert timeline[0].strongest_drop_concept_label == "Simple Interest"
    assert timeline[0].action_label == "Review weak concept"


def test_latest_intervention_bootstrap_uses_latest_scope(monkeypatch):
    student_id = uuid4()
    event = MasteryUpdateEvent(
        student_id=student_id,
        quiz_id=uuid4(),
        attempt_id=None,
        subject="english",
        sss_level="SSS2",
        term=3,
        source="practice",
        concept_breakdown=[],
        new_mastery=[],
    )

    class _Query:
        def filter(self, *args, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
            return self

        def first(self):
            return event

    class _DB:
        def query(self, *args, **kwargs):
            return _Query()

    captured = {}

    def _bootstrap(self, *, student_id, subject, term):
        captured["student_id"] = student_id
        captured["subject"] = subject
        captured["term"] = term
        return "ok"

    service = CourseExperienceService(db=_DB())
    monkeypatch.setattr(CourseExperienceService, "bootstrap", _bootstrap)

    result = service.latest_intervention_bootstrap(student_id=student_id)

    assert result == "ok"
    assert captured == {"student_id": student_id, "subject": "english", "term": 3}
