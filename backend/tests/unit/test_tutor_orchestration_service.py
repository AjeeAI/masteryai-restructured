from uuid import uuid4

import pytest

from backend.core.config import settings
from backend.schemas.tutor_schema import (
    TutorAssessmentStartIn,
    TutorChatIn,
    TutorExplainMistakeIn,
    TutorHintIn,
)
from backend.services.tutor_orchestration_service import (
    TutorOrchestrationService,
    TutorProviderUnavailableError,
)


@pytest.mark.anyio
async def test_chat_fallback_when_provider_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "ai_core_base_url", "")
    monkeypatch.setattr(settings, "ai_core_allow_fallback", True)

    service = TutorOrchestrationService()
    out = await service.chat(
        TutorChatIn(
            student_id=uuid4(),
            session_id=uuid4(),
            subject="math",
            sss_level="SSS2",
            term=1,
            topic_id=uuid4(),
            message="Explain linear equations",
        )
    )

    assert out.assistant_message
    assert "FALLBACK_GUIDANCE_ONLY" in out.actions
    assert "UPDATED_MASTERY_BASIC" not in out.actions


@pytest.mark.anyio
async def test_provider_unavailable_raises_without_fallback(monkeypatch):
    monkeypatch.setattr(settings, "ai_core_base_url", "")
    monkeypatch.setattr(settings, "ai_core_allow_fallback", False)

    service = TutorOrchestrationService()
    with pytest.raises(TutorProviderUnavailableError):
        await service.hint(
            TutorHintIn(
                student_id=uuid4(),
                session_id=None,
                quiz_id=uuid4(),
                question_id="q1",
                subject="english",
                sss_level="SSS1",
                term=1,
                topic_id=None,
                message="help",
            )
        )


@pytest.mark.anyio
async def test_explain_mistake_fallback_response(monkeypatch):
    monkeypatch.setattr(settings, "ai_core_base_url", "")
    monkeypatch.setattr(settings, "ai_core_allow_fallback", True)

    service = TutorOrchestrationService()
    out = await service.explain_mistake(
        TutorExplainMistakeIn(
            student_id=uuid4(),
            session_id=None,
            subject="civic",
            sss_level="SSS3",
            term=2,
            topic_id=None,
            question="Which arm makes laws?",
            student_answer="Judiciary",
            correct_answer="Legislature",
        )
    )

    assert "expected answer" in out.explanation.lower()
    assert out.improvement_tip


@pytest.mark.anyio
async def test_assessment_start_fallback_requires_graph_focus(monkeypatch):
    monkeypatch.setattr(settings, "ai_core_base_url", "")
    monkeypatch.setattr(settings, "ai_core_allow_fallback", True)

    service = TutorOrchestrationService()

    with pytest.raises(
        TutorProviderUnavailableError,
        match="concrete graph-selected focus concept",
    ):
        await service.assessment_start(
            TutorAssessmentStartIn(
                student_id=uuid4(),
                session_id=uuid4(),
                subject="math",
                sss_level="SSS2",
                term=1,
                topic_id=uuid4(),
                difficulty="medium",
            )
        )
