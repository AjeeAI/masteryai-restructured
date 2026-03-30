from uuid import uuid4

from backend.schemas.learning_path_schema import PathNextOut
from backend.services.lesson_graph_service import _TopicConcept, lesson_graph_service


def test_lesson_graph_context_marks_blocking_prerequisite_details(monkeypatch):
    student_id = uuid4()
    topic_id = uuid4()
    prereq_topic_id = uuid4()

    monkeypatch.setattr(
        lesson_graph_service,
        "_scoped_graph",
        lambda db, **kwargs: (
            {
                str(topic_id): ["math:sss2:t1:linear-equations"],
                str(prereq_topic_id): ["math:sss2:t1:variables"],
            },
            {
                "math:sss2:t1:linear-equations": _TopicConcept(
                    concept_id="math:sss2:t1:linear-equations",
                    label="Linear Equations",
                    topic_id=str(topic_id),
                    topic_title="Linear Equations",
                ),
                "math:sss2:t1:variables": _TopicConcept(
                    concept_id="math:sss2:t1:variables",
                    label="Variables",
                    topic_id=str(prereq_topic_id),
                    topic_title="Variables",
                ),
                "math:sss2:t1:simultaneous-equations": _TopicConcept(
                    concept_id="math:sss2:t1:simultaneous-equations",
                    label="Simultaneous Equations",
                    topic_id=str(uuid4()),
                    topic_title="Simultaneous Equations",
                ),
            },
            [
                ("math:sss2:t1:variables", "math:sss2:t1:linear-equations"),
                ("math:sss2:t1:linear-equations", "math:sss2:t1:simultaneous-equations"),
            ],
            {
                "math:sss2:t1:variables": 0.42,
                "math:sss2:t1:linear-equations": 0.55,
                "math:sss2:t1:simultaneous-equations": 0.0,
            },
        ),
    )
    monkeypatch.setattr(
        "backend.services.lesson_graph_service.learning_path_service.calculate_next_step",
        lambda **kwargs: PathNextOut(
            recommended_topic_id=str(uuid4()),
            recommended_topic_title="Simultaneous Equations",
            recommended_concept_id="math:sss2:t1:simultaneous-equations",
            recommended_concept_label="Simultaneous Equations",
            reason="Next concept on the graph path.",
            prereq_gaps=["math:sss2:t1:variables"],
            prereq_gap_labels=["Variables"],
        ),
    )

    context = lesson_graph_service.get_lesson_graph_context(
        db=object(),
        student_id=student_id,
        subject="math",
        sss_level="SSS2",
        term=1,
        topic_id=topic_id,
    )

    current = context.current_concepts[0]
    downstream = context.downstream_concepts[0]

    assert current.blocking_prerequisite_labels == ["Variables"]
    assert current.detail == "This lesson still depends on Variables."
    assert current.lock_reason == "The current lesson cluster is being slowed down by Variables."
    assert current.recommended_action_label == "Open blocking prerequisite"
    assert current.recommended_topic_title == "Variables"
    assert downstream.blocking_prerequisite_labels == ["Linear Equations"]
    assert downstream.detail == "Locked until Linear Equations is stronger."
    assert downstream.lock_reason == "Simultaneous Equations is locked because Linear Equations still needs more evidence."
    assert downstream.recommended_action_label == "Open blocking prerequisite"
    assert downstream.blocking_prerequisite_topic_title == "Linear Equations"
