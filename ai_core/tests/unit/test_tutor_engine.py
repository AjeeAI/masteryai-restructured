import pytest

from ai_core.core_engine.api_contracts.schemas import (
    TutorAssessmentStartRequest,
    TutorAssessmentSubmitRequest,
    TutorChatRequest,
    TutorExplainMistakeRequest,
    TutorHintRequest,
    TutorRecapRequest,
)
from ai_core.core_engine.orchestration.tutor_engine import (
    _internal_rag_retrieve,
    run_tutor_assessment_start,
    run_tutor_assessment_submit,
    run_tutor_chat,
    run_tutor_explain_mistake,
    run_tutor_hint,
    run_tutor_recap,
)


def test_run_tutor_chat_contract(monkeypatch):
    monkeypatch.setattr(
        "ai_core.core_engine.orchestration.tutor_engine._internal_profile_context",
        lambda request: {
            "student_id": request.student_id,
            "profile_id": "profile-1",
            "sss_level": request.sss_level,
            "term": request.term,
            "subjects": [request.subject],
            "preferences": {"explanation_depth": "standard", "examples_first": True, "pace": "normal"},
        },
    )
    monkeypatch.setattr(
        "ai_core.core_engine.orchestration.tutor_engine._internal_history_context",
        lambda request: {"messages": [{"role": "student", "content": "Earlier question"}]},
    )
    monkeypatch.setattr(
        "ai_core.core_engine.orchestration.tutor_engine._internal_lesson_context",
        lambda request: {
            "student_id": request.student_id,
            "topic_id": request.topic_id,
            "title": "Lesson: Algebra Basics",
            "summary": "Focus on variables and simple equations.",
            "context_source": "structured",
            "content_blocks": [{"type": "text", "value": "A variable represents an unknown quantity."}],
            "source_chunk_ids": ["chunk-1"],
            "generation_metadata": {"generator_version": "rag_mastery_v1"},
        },
    )
    monkeypatch.setattr(
        "ai_core.core_engine.orchestration.tutor_engine._internal_graph_context",
        lambda request: {
            "mastery": [{"concept_id": "math:sss2:t1:linear-equations", "score": 0.42}],
            "prereqs": [
                {
                    "prerequisite_concept_id": "math:sss2:t1:variables",
                    "concept_id": "math:sss2:t1:linear-equations",
                }
            ],
            "unlocked_nodes": ["math:sss2:t1:variables"],
            "overall_mastery": 0.42,
        },
    )
    monkeypatch.setattr(
        "ai_core.core_engine.orchestration.tutor_engine._internal_rag_retrieve",
        lambda request: [],
    )
    monkeypatch.setattr(
        "ai_core.core_engine.orchestration.tutor_engine._llm_generate",
        lambda prompt: "This is a scoped tutor response.",
    )
    out = run_tutor_chat(
        TutorChatRequest(
            student_id="user-1",
            session_id="session-1",
            subject="math",
            sss_level="SSS2",
            term=1,
            topic_id="topic-1",
            message="Explain algebra basics",
        )
    )
    assert out.assistant_message
    assert isinstance(out.actions, list)
    assert isinstance(out.recommendations, list)
    assert "USED_LESSON_CONTEXT" in out.actions
    assert "USED_STRUCTURED_LESSON_CONTEXT" in out.actions
    assert "NO_MASTERY_WRITE_NO_EVIDENCE" in out.actions


def test_run_tutor_chat_aborts_when_no_lesson_or_rag_context(monkeypatch):
    monkeypatch.setattr(
        "ai_core.core_engine.orchestration.tutor_engine._internal_profile_context",
        lambda request: {},
    )
    monkeypatch.setattr(
        "ai_core.core_engine.orchestration.tutor_engine._internal_history_context",
        lambda request: {"messages": []},
    )
    monkeypatch.setattr(
        "ai_core.core_engine.orchestration.tutor_engine._internal_lesson_context",
        lambda request: None,
    )
    monkeypatch.setattr(
        "ai_core.core_engine.orchestration.tutor_engine._internal_graph_context",
        lambda request: {},
    )
    monkeypatch.setattr(
        "ai_core.core_engine.orchestration.tutor_engine._internal_rag_retrieve",
        lambda request: [],
    )

    out = run_tutor_chat(
        TutorChatRequest(
            student_id="user-1",
            session_id="session-1",
            subject="math",
            sss_level="SSS2",
            term=1,
            topic_id="topic-1",
            message="Explain algebra basics",
        )
    )

    assert "no lesson-aware context found" in out.assistant_message.lower()
    assert "NO_CONTEXT_ABORTED" in out.actions
    assert "NO_MASTERY_WRITE_NO_EVIDENCE" in out.actions


def test_run_tutor_recap_uses_fast_lesson_grounded_path(monkeypatch):
    monkeypatch.setattr(
        "ai_core.core_engine.orchestration.tutor_engine._internal_lesson_context",
        lambda request: {
            "student_id": request.student_id,
            "topic_id": request.topic_id,
            "title": "Lesson: Capitalist Democracy",
            "summary": "Define democracy; Mention six characteristics of democracy.",
            "context_source": "structured",
            "content_blocks": [
                {"type": "text", "value": "Capitalist democracy combines private ownership with representative government."},
                {"type": "text", "value": "The constitution is supreme and elections allow citizens to choose leaders periodically."},
            ],
        },
    )
    monkeypatch.setattr(
        "ai_core.core_engine.orchestration.tutor_engine._internal_graph_context",
        lambda request: {
            "mastery": [{"concept_id": "civic:sss2:t1:capitalist-democracy", "score": 0.15}],
            "next_unlock": {"topic_title": "Political party", "reason": "This lesson unlocks later civic structures."},
        },
    )
    monkeypatch.setattr(
        "ai_core.core_engine.orchestration.tutor_engine._llm_generate",
        lambda prompt: (_ for _ in ()).throw(AssertionError("recap should not call llm")),
    )

    out = run_tutor_recap(
        TutorRecapRequest(
            student_id="user-1",
            session_id="session-1",
            subject="civic",
            sss_level="SSS2",
            term=1,
            topic_id="topic-1",
        )
    )

    assert "Capitalist Democracy" in out.assistant_message
    assert out.mode == "recap"
    assert "FAST_RECAP_PATH" in out.actions
    assert "SKIPPED_LLM_RECAP" in out.actions
    assert out.key_points


def test_run_tutor_hint_contract(monkeypatch):
    monkeypatch.setattr(
        "ai_core.core_engine.orchestration.tutor_engine._llm_generate",
        lambda prompt: "Start by identifying the main rule.",
    )
    out = run_tutor_hint(
        TutorHintRequest(
            student_id="user-1",
            session_id="session-1",
            quiz_id="quiz-1",
            question_id="q1",
            subject="english",
            sss_level="SSS1",
            term=1,
            topic_id=None,
            message="Need hint",
        )
    )
    assert out.hint
    assert out.strategy == "guided_hint"


def test_run_tutor_explain_mistake_contract(monkeypatch):
    monkeypatch.setattr(
        "ai_core.core_engine.orchestration.tutor_engine._llm_generate",
        lambda prompt: "You mixed up the branches of government.",
    )
    out = run_tutor_explain_mistake(
        TutorExplainMistakeRequest(
            student_id="user-1",
            session_id="session-1",
            subject="civic",
            sss_level="SSS3",
            term=2,
            topic_id=None,
            question="Who makes laws?",
            student_answer="Judiciary",
            correct_answer="Legislature",
        )
    )
    assert out.explanation
    assert out.improvement_tip


def test_run_tutor_assessment_start_contract(monkeypatch):
    monkeypatch.setattr(
        "ai_core.core_engine.orchestration.tutor_engine._internal_profile_context",
        lambda request: {"preferences": {"pace": "normal"}},
    )
    monkeypatch.setattr(
        "ai_core.core_engine.orchestration.tutor_engine._internal_lesson_context",
        lambda request: {
            "title": "Lesson: Algebra Basics",
            "summary": "Variables and simple equations.",
            "content_blocks": [{"type": "text", "value": "A variable represents an unknown number."}],
            "covered_concept_ids": ["math:sss2:t1:variables"],
            "covered_concept_labels": {"math:sss2:t1:variables": "variables"},
        },
    )
    monkeypatch.setattr(
        "ai_core.core_engine.orchestration.tutor_engine._internal_graph_context",
        lambda request: {
            "mastery": [{"concept_id": "math:sss2:t1:variables", "score": 0.3}],
            "prereqs": [],
            "unlocked_nodes": ["math:sss2:t1:variables"],
            "overall_mastery": 0.3,
        },
    )
    monkeypatch.setattr(
        "ai_core.core_engine.orchestration.tutor_engine._internal_rag_retrieve_for_prompt",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        "ai_core.core_engine.orchestration.tutor_engine._llm_generate",
        lambda prompt: """
        {
          "question": "What is a variable in algebra?",
          "ideal_answer": "A variable is a letter or symbol that represents an unknown value.",
          "hint": "Think about what letters stand for in algebra."
        }
        """,
    )

    out = run_tutor_assessment_start(
        TutorAssessmentStartRequest(
            student_id="user-1",
            session_id="session-1",
            subject="math",
            sss_level="SSS2",
            term=1,
            topic_id="topic-1",
            difficulty="medium",
        )
    )
    assert out.question
    assert out.ideal_answer
    assert out.concept_id == "math:sss2:t1:variables"
    assert "ASSESSMENT_TARGET_CONCEPT" in out.actions


def test_run_tutor_assessment_start_prefers_explicit_graph_focus(monkeypatch):
    monkeypatch.setattr(
        "ai_core.core_engine.orchestration.tutor_engine._internal_profile_context",
        lambda request: {"preferences": {"pace": "normal"}},
    )
    monkeypatch.setattr(
        "ai_core.core_engine.orchestration.tutor_engine._internal_lesson_context",
        lambda request: {
            "title": "Lesson: Electoral Process",
            "summary": "Voting systems and constitutional governance.",
            "content_blocks": [{"type": "text", "value": "The electoral process depends on lawful participation and institutional rules."}],
            "covered_concept_ids": [
                "civic:sss1:t2:constitutional-governance",
                "civic:sss1:t2:electoral-process",
            ],
            "covered_concept_labels": {
                "civic:sss1:t2:constitutional-governance": "Constitutional Governance",
                "civic:sss1:t2:electoral-process": "Electoral Process",
            },
        },
    )
    monkeypatch.setattr(
        "ai_core.core_engine.orchestration.tutor_engine._internal_graph_context",
        lambda request: {
            "mastery": [
                {"concept_id": "civic:sss1:t2:constitutional-governance", "score": 0.1},
                {"concept_id": "civic:sss1:t2:electoral-process", "score": 0.4},
            ],
            "current_concepts": [
                {"concept_id": "civic:sss1:t2:electoral-process", "label": "Electoral Process"},
            ],
            "prerequisite_concepts": [
                {"concept_id": "civic:sss1:t2:constitutional-governance", "label": "Constitutional Governance"},
            ],
            "downstream_concepts": [],
        },
    )
    monkeypatch.setattr(
        "ai_core.core_engine.orchestration.tutor_engine._internal_rag_retrieve_for_prompt",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        "ai_core.core_engine.orchestration.tutor_engine._llm_generate",
        lambda prompt: """
        {
          "question": "Explain one way the electoral process supports fair participation.",
          "ideal_answer": "It sets lawful procedures that help citizens participate fairly in choosing leaders.",
          "hint": "Think about fairness and lawful participation."
        }
        """,
    )

    out = run_tutor_assessment_start(
        TutorAssessmentStartRequest(
            student_id="user-1",
            session_id="session-1",
            subject="civic",
            sss_level="SSS1",
            term=2,
            topic_id="topic-1",
            focus_concept_id="civic:sss1:t2:electoral-process",
            focus_concept_label="Electoral Process",
            difficulty="medium",
        )
    )
    assert out.concept_id == "civic:sss1:t2:electoral-process"
    assert out.concept_label == "Electoral Process"
    assert "USED_GRAPH_SELECTED_FOCUS" in out.actions


def test_run_tutor_assessment_submit_contract(monkeypatch):
    monkeypatch.setattr(
        "ai_core.core_engine.orchestration.tutor_engine._internal_lesson_context",
        lambda request: {
            "title": "Lesson: Algebra Basics",
            "summary": "Variables and simple equations.",
            "content_blocks": [{"type": "text", "value": "A variable represents an unknown number."}],
            "covered_concept_ids": ["math:sss2:t1:variables"],
            "covered_concept_labels": {"math:sss2:t1:variables": "variables"},
        },
    )
    monkeypatch.setattr(
        "ai_core.core_engine.orchestration.tutor_engine._internal_graph_context",
        lambda request: {
            "mastery": [{"concept_id": "math:sss2:t1:variables", "score": 0.3}],
            "prereqs": [],
            "unlocked_nodes": ["math:sss2:t1:variables"],
            "overall_mastery": 0.3,
        },
    )
    monkeypatch.setattr(
        "ai_core.core_engine.orchestration.tutor_engine._internal_rag_retrieve_for_prompt",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        "ai_core.core_engine.orchestration.tutor_engine._llm_generate",
        lambda prompt: """
        {
          "score": 0.9,
          "feedback": "Correct. You identified that a variable stands for an unknown value.",
          "ideal_answer": "A variable is a letter or symbol that represents an unknown value."
        }
        """,
    )

    out = run_tutor_assessment_submit(
        TutorAssessmentSubmitRequest(
            student_id="user-1",
            session_id="session-1",
            assessment_id="assessment-1",
            subject="math",
            sss_level="SSS2",
            term=1,
            topic_id="topic-1",
            answer="It is a symbol for an unknown value.",
            question="What is a variable in algebra?",
            concept_id="math:sss2:t1:variables",
            concept_label="variables",
            ideal_answer="A variable is a letter or symbol that represents an unknown value.",
        )
    )
    assert out.is_correct is True
    assert out.score == 0.9
    assert out.feedback


def test_internal_rag_retrieve_requires_internal_service_key(monkeypatch):
    monkeypatch.delenv("INTERNAL_SERVICE_KEY", raising=False)

    with pytest.raises(RuntimeError, match="INTERNAL_SERVICE_KEY"):
        _internal_rag_retrieve(
            TutorChatRequest(
                student_id="user-1",
                session_id="session-1",
                subject="math",
                sss_level="SSS2",
                term=1,
                topic_id="11111111-1111-1111-1111-111111111111",
                message="Explain algebra basics",
            )
        )
