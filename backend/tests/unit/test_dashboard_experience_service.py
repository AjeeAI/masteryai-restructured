from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from backend.services.dashboard_experience_service import DashboardExperienceService


def test_dashboard_bootstrap_uses_cache_and_invalidation(monkeypatch):
    student_id = uuid4()
    service = DashboardExperienceService(db=SimpleNamespace())
    profile = SimpleNamespace(
        updated_at=datetime.now(timezone.utc),
        sss_level="SSS2",
        active_term=2,
    )
    calls = {"course": 0}

    monkeypatch.setattr(
        service,
        "_profile_and_subjects",
        lambda **kwargs: (profile, ["english", "math"]),
    )
    monkeypatch.setattr(
        service.course_service,
        "latest_intervention_bootstrap",
        lambda **kwargs: None,
    )
    queued_subjects = []
    monkeypatch.setattr(
        "backend.services.dashboard_experience_service.PrewarmJobService.enqueue_course_scope",
        lambda self, **kwargs: queued_subjects.append(kwargs["subject"]) or uuid4(),
    )

    def _bootstrap(**kwargs):
        calls["course"] += 1
        return {
            "student_id": str(student_id),
            "subject": "english",
            "sss_level": "SSS2",
            "term": 2,
            "topics": [],
            "nodes": [],
            "edges": [],
            "next_step": None,
            "recent_evidence": None,
            "intervention_timeline": [],
            "recommendation_story": None,
            "map_error": None,
            "warmed_topic_ids": [],
            "cache_hit_topic_ids": [],
            "failed_topic_ids": [],
        }

    monkeypatch.setattr(service.course_service, "bootstrap", _bootstrap)

    first = service.bootstrap(student_id=student_id, subject="english")
    second = service.bootstrap(student_id=student_id, subject="english")

    assert calls["course"] == 1
    assert first.active_subject == "english"
    assert first.warmed_subjects == ["math"]
    assert second.active_subject == "english"
    assert queued_subjects == ["math"]

    DashboardExperienceService.invalidate_student_cache(student_id=student_id)
    third = service.bootstrap(student_id=student_id, subject="english")

    assert calls["course"] == 2
    assert third.active_subject == "english"
    assert third.warmed_subjects == ["math"]
    assert queued_subjects == ["math", "math"]


def test_dashboard_path_briefing_export_uses_live_course_bootstrap(monkeypatch):
    student_id = uuid4()
    service = DashboardExperienceService(db=SimpleNamespace())

    monkeypatch.setattr(
        service,
        "bootstrap",
        lambda **kwargs: SimpleNamespace(
            student_id=student_id,
            sss_level="SSS2",
            term=2,
            active_subject="english",
            course_bootstrap=SimpleNamespace(
                next_step=SimpleNamespace(
                    recommended_topic_title="Comprehension Skills",
                    recommended_concept_label="Inference",
                    reason="Your latest checkpoint shows inference is the next best move.",
                    prereq_gap_labels=["Main Idea"],
                ),
                recommendation_story=SimpleNamespace(
                    headline="Repair main idea before moving deeper into inference.",
                    supporting_reason="The graph found a prerequisite gap on Main Idea after your latest checkpoint.",
                ),
                recent_evidence=SimpleNamespace(
                    summary="Checkpoint evidence shows inference dropped after the last lesson.",
                ),
                intervention_timeline=[
                    SimpleNamespace(
                        source_label="Checkpoint",
                        summary="You missed the last inference checkpoint.",
                    )
                ],
                topics=[
                    SimpleNamespace(title="Comprehension Skills", status="ready", graph_details="Ready from graph."),
                    SimpleNamespace(title="Reading for Main Idea", status="locked", graph_details="Blocked by Main Idea."),
                ],
            ),
        ),
    )

    out = service.get_path_briefing_export(student_id=student_id, subject="english")

    assert out.export_kind == "student_path_briefing"
    assert out.subject == "english"
    assert out.title == "English learning path briefing"
    assert any(section.title == "Graph signal" for section in out.sections)
    assert "Repair main idea before moving deeper into inference." in out.markdown
