import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from backend.schemas.tutor_schema import TutorAssessmentStartIn, TutorAssessmentStartOut
from backend.schemas.learning_path_schema import PathNextOut
from backend.services.tutor_assessment_service import TutorAssessmentService


def test_graph_follow_up_returns_graph_remediation(monkeypatch):
    db = MagicMock()
    service = TutorAssessmentService(db)
    service.quiz_repo.find_topic_title_for_concept = MagicMock(
        side_effect=lambda **kwargs: (
            "Electoral Process and Participation"
            if kwargs.get("concept_id") == "civic:sss1:t2:electoral-process"
            else "Constitutional Governance"
            if kwargs.get("concept_id") == "civic:sss1:t2:constitutional-governance"
            else None
        )
    )
    service.quiz_repo.get_topic_title = MagicMock(return_value="Electoral Process and Participation")

    monkeypatch.setattr(
        "backend.services.tutor_assessment_service.learning_path_service.calculate_next_step",
        lambda **kwargs: PathNextOut(
            recommended_topic_id=str(uuid4()),
            recommended_topic_title="Electoral Process and Participation",
            recommended_concept_id="civic:sss1:t2:electoral-process",
            recommended_concept_label="Electoral Process",
            reason="Return to the blocking civic participation concept before moving on.",
            prereq_gaps=["civic:sss1:t2:constitutional-governance"],
            prereq_gap_labels=["Constitutional Governance"],
            scope_warning=None,
            unmapped_topic_titles=[],
        ),
    )

    payload = SimpleNamespace(
        student_id=uuid4(),
        subject="civic",
        sss_level="SSS1",
        term=2,
    )

    prerequisite_warning, recommended_topic_id, recommended_topic_title, remediation = service._graph_follow_up(
        payload=payload,
        focus_concept_id="civic:sss1:t2:electoral-process",
        fallback_topic_id=uuid4(),
    )

    assert prerequisite_warning is not None
    assert recommended_topic_id is not None
    assert recommended_topic_title == "Electoral Process and Participation"
    assert remediation is not None
    assert remediation.focus_concept_label == "Electoral Process"
    assert remediation.blocking_prerequisite_label == "Constitutional Governance"
    assert remediation.recommended_next_concept_label == "Electoral Process"
    assert remediation.recommendation_reason == "Return to the blocking civic participation concept before moving on."


def test_start_assessment_preserves_requested_focus():
    db = MagicMock()
    service = TutorAssessmentService(db)
    stored_messages = []

    class _Repo:
        def add_message(self, *, session_id, role, content):
            stored_messages.append({"session_id": session_id, "role": role, "content": content})
            return {"id": str(uuid4())}

    async def _assessment_start(payload):
        assert payload.focus_concept_id == "civic:sss1:t2:electoral-process"
        assert payload.focus_concept_label == "Electoral Process"
        return TutorAssessmentStartOut(
            assessment_id=uuid4(),
            question="Why is electoral process important?",
            concept_id="civic:sss1:t2:electoral-process",
            concept_label="Electoral Process",
            ideal_answer="It guides fair participation and lawful voting.",
            hint="Think about participation and fairness.",
            citations=[],
            actions=["USED_GRAPH_SELECTED_FOCUS"],
        )

    service.repo = _Repo()
    service.orchestration = SimpleNamespace(assessment_start=_assessment_start)

    payload = TutorAssessmentStartIn(
        student_id=uuid4(),
        session_id=uuid4(),
        subject="civic",
        sss_level="SSS1",
        term=2,
        topic_id=uuid4(),
        focus_concept_id="civic:sss1:t2:electoral-process",
        focus_concept_label="Electoral Process",
        difficulty="medium",
    )

    out = asyncio.run(service.start_assessment(payload))

    assert out.concept_id == "civic:sss1:t2:electoral-process"
    assert out.concept_label == "Electoral Process"
    pending_state = service._decode_state(stored_messages[0]["content"])
    assert pending_state is not None
    assert pending_state["requested_focus_concept_id"] == "civic:sss1:t2:electoral-process"
    assert pending_state["requested_focus_concept_label"] == "Electoral Process"
