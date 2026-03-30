import importlib
import importlib.util
import inspect
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import MagicMock

import pytest


if importlib.util.find_spec("backend.services.diagnostic_service") is None:
    pytest.skip(
        "Section 3 Lane B pending: backend.services.diagnostic_service is not created yet.",
        allow_module_level=True,
    )


diagnostic_service_module = importlib.import_module("backend.services.diagnostic_service")
DiagnosticStartIn = importlib.import_module("backend.schemas.diagnostic_schema").DiagnosticStartIn


def test_diagnostic_service_contract_is_exposed():
    assert hasattr(diagnostic_service_module, "diagnostic_service")

    service = diagnostic_service_module.diagnostic_service
    assert callable(getattr(service, "create_diagnostic_session", None))
    assert callable(getattr(service, "process_diagnostic_submission", None))


def test_diagnostic_service_method_signatures_include_db_and_payload():
    service = diagnostic_service_module.diagnostic_service

    start_params = inspect.signature(service.create_diagnostic_session).parameters
    submit_params = inspect.signature(service.process_diagnostic_submission).parameters

    assert "db" in start_params and "payload" in start_params
    assert "db" in submit_params and "payload" in submit_params


def test_create_diagnostic_session_requires_mapped_curriculum_concepts(monkeypatch):
    repo = MagicMock()
    repo.validate_student_scope.return_value = True
    repo.get_scope_topics.return_value = [SimpleNamespace(id=uuid4(), title="Our Values")]
    repo.get_scope_topic_concept_rows.return_value = []
    repo.get_in_progress_diagnostic.return_value = None

    monkeypatch.setattr(diagnostic_service_module, "DiagnosticRepository", lambda db: repo)

    payload = DiagnosticStartIn(
        student_id=uuid4(),
        subject="civic",
        sss_level="SSS1",
        term=1,
    )

    with pytest.raises(diagnostic_service_module.DiagnosticValidationError):
        diagnostic_service_module.diagnostic_service.create_diagnostic_session(db=object(), payload=payload)


def test_create_diagnostic_session_uses_real_concept_labels(monkeypatch):
    topic_id = uuid4()
    repo = MagicMock()
    repo.validate_student_scope.return_value = True
    repo.get_scope_topics.return_value = [SimpleNamespace(id=topic_id, title="Our Values")]
    repo.get_scope_topic_concept_rows.return_value = [
        {
            "topic_id": str(topic_id),
            "topic_title": "Our Values",
            "concept_id": "civic:sss1:t1:individualistic-values",
            "prereq_concept_ids": [],
        },
        {
            "topic_id": str(topic_id),
            "topic_title": "Our Values",
            "concept_id": "civic:sss1:t1:family-values",
            "prereq_concept_ids": [],
        },
        {
            "topic_id": str(topic_id),
            "topic_title": "Our Values",
            "concept_id": "civic:sss1:t1:professional-values",
            "prereq_concept_ids": [],
        },
        {
            "topic_id": str(topic_id),
            "topic_title": "Our Values",
            "concept_id": "civic:sss1:t1:national-values",
            "prereq_concept_ids": [],
        },
    ]
    repo.get_in_progress_diagnostic.return_value = None
    repo.create_diagnostic.side_effect = lambda **kwargs: SimpleNamespace(id=uuid4(), **kwargs)

    monkeypatch.setattr(diagnostic_service_module, "DiagnosticRepository", lambda db: repo)

    payload = DiagnosticStartIn(
        student_id=uuid4(),
        subject="civic",
        sss_level="SSS1",
        term=1,
    )

    result = diagnostic_service_module.diagnostic_service.create_diagnostic_session(db=MagicMock(), payload=payload)

    question_by_concept = {question.concept_id: question for question in result.questions}
    assert "civic:sss1:t1:individualistic-values" in question_by_concept
    assert question_by_concept["civic:sss1:t1:individualistic-values"].concept_label == "Individualistic values"
    assert question_by_concept["civic:sss1:t1:individualistic-values"].topic_title == "Our values"
    assert len(question_by_concept["civic:sss1:t1:individualistic-values"].option_details) == 4


def test_create_diagnostic_session_respects_question_count_and_shuffles_answers(monkeypatch):
    topic_id = uuid4()
    student_id = uuid4()
    repo = MagicMock()
    repo.validate_student_scope.return_value = True
    repo.get_in_progress_diagnostic.return_value = None
    repo.get_scope_topic_concept_rows.return_value = [
        {
            "topic_id": str(topic_id),
            "topic_title": "Our Values",
            "concept_id": "civic:sss1:t1:individualistic-values",
            "prereq_concept_ids": [],
        },
        {
            "topic_id": str(topic_id),
            "topic_title": "Our Values",
            "concept_id": "civic:sss1:t1:family-values",
            "prereq_concept_ids": [],
        },
        {
            "topic_id": str(topic_id),
            "topic_title": "Our Values",
            "concept_id": "civic:sss1:t1:professional-values",
            "prereq_concept_ids": [],
        },
        {
            "topic_id": str(topic_id),
            "topic_title": "Our Values",
            "concept_id": "civic:sss1:t1:national-values",
            "prereq_concept_ids": [],
        },
    ]
    repo.create_diagnostic.side_effect = lambda **kwargs: SimpleNamespace(id=uuid4(), **kwargs)

    monkeypatch.setattr(diagnostic_service_module, "DiagnosticRepository", lambda db: repo)

    payload = DiagnosticStartIn(
        student_id=student_id,
        subject="civic",
        sss_level="SSS1",
        term=1,
        num_questions=10,
    )

    result = diagnostic_service_module.diagnostic_service.create_diagnostic_session(db=MagicMock(), payload=payload)

    assert result.question_count == 10
    assert len(result.questions) == 10
    assert len({question.concept_id for question in result.questions}) == 4

    created_questions = repo.create_diagnostic.call_args.kwargs["questions"]
    correct_answers = {question["correct_answer"] for question in created_questions}
    assert correct_answers.issubset({"A", "B", "C", "D"})
    assert len(correct_answers) > 1


def test_build_options_prefers_same_topic_distractors_before_scope_fallback():
    rng = diagnostic_service_module.random.Random(42)
    current_row = {
        "topic_id": "topic-a",
        "topic_title": "Poverty and its Effects",
        "concept_id": "civic:sss2:t1:poverty-and-its-effects",
        "concept_label": "Poverty and its effects",
        "prereq_concept_ids": [],
    }
    all_rows = [
        current_row,
        {
            "topic_id": "topic-a",
            "topic_title": "Poverty and its Effects",
            "concept_id": "civic:sss2:t1:effects-of-poverty",
            "concept_label": "Effects of poverty",
            "prereq_concept_ids": [],
        },
        {
            "topic_id": "topic-a",
            "topic_title": "Poverty and its Effects",
            "concept_id": "civic:sss2:t1:importance-of-employment",
            "concept_label": "Importance of employment",
            "prereq_concept_ids": [],
        },
        {
            "topic_id": "topic-a",
            "topic_title": "Poverty and its Effects",
            "concept_id": "civic:sss2:t1:poverty-alleviation-programmes",
            "concept_label": "Poverty alleviation programmes in Nigeria",
            "prereq_concept_ids": [],
        },
        {
            "topic_id": "topic-b",
            "topic_title": "Political Apathy",
            "concept_id": "civic:sss2:t1:forms-of-political-apathy",
            "concept_label": "Forms of political apathy",
            "prereq_concept_ids": [],
        },
    ]

    options, correct_answer = diagnostic_service_module.diagnostic_service._build_options(
        current_row,
        all_rows,
        rng=rng,
    )

    assert correct_answer in {"A", "B", "C", "D"}
    assert "Poverty and its effects" in options
    assert "Effects of poverty" in options
    assert "Importance of employment" in options
    assert "Poverty alleviation programmes in Nigeria" in options


def test_create_diagnostic_session_filters_topic_surrogates_from_student_options(monkeypatch):
    topic_id = uuid4()
    repo = MagicMock()
    repo.validate_student_scope.return_value = True
    repo.get_in_progress_diagnostic.return_value = None
    repo.get_scope_topic_concept_rows.return_value = [
        {
            "topic_id": str(topic_id),
            "topic_title": "Citizenship Education and Importance of Citizenship Education",
            "concept_id": "civic:sss2:t1:citizenship-education",
            "prereq_concept_ids": [],
        },
        {
            "topic_id": str(topic_id),
            "topic_title": "Citizenship Education and Importance of Citizenship Education",
            "concept_id": "civic:sss2:t1:importance-of-citizenship-education",
            "prereq_concept_ids": [],
        },
        {
            "topic_id": str(topic_id),
            "topic_title": "Citizenship Education and Importance of Citizenship Education",
            "concept_id": "civic:sss2:t1:topic-citizenship-education-and-importance-of-ci",
            "prereq_concept_ids": [],
        },
        {
            "topic_id": str(topic_id),
            "topic_title": "Political Party",
            "concept_id": "civic:sss2:t1:functions-of-political-parties",
            "prereq_concept_ids": [],
        },
        {
            "topic_id": str(topic_id),
            "topic_title": "Poverty and its Effects",
            "concept_id": "civic:sss2:t1:importance-of-employment",
            "prereq_concept_ids": [],
        },
    ]
    repo.create_diagnostic.side_effect = lambda **kwargs: SimpleNamespace(id=uuid4(), **kwargs)

    monkeypatch.setattr(diagnostic_service_module, "DiagnosticRepository", lambda db: repo)

    payload = DiagnosticStartIn(
        student_id=uuid4(),
        subject="civic",
        sss_level="SSS2",
        term=1,
        num_questions=4,
    )

    result = diagnostic_service_module.diagnostic_service.create_diagnostic_session(db=MagicMock(), payload=payload)

    rendered_options = [option for question in result.questions for option in question.options]
    assert all(not option.lower().startswith("topic ") for option in rendered_options)
    assert "Citizenship education and importance of citizenship education" not in rendered_options
    assert "Functions of political parties" in rendered_options
    details = result.questions[0].option_details
    assert any(detail.label == "Functions of political parties" and detail.context_title == "Political party" for detail in details)


def test_resume_diagnostic_session_normalizes_existing_prompt_and_options(monkeypatch):
    student_id = uuid4()
    diagnostic_id = uuid4()
    topic_id = uuid4()
    existing = SimpleNamespace(
        id=diagnostic_id,
        subject="civic",
        sss_level="SSS2",
        term=1,
        questions=[
            {
                "question_id": str(uuid4()),
                "concept_id": "civic:sss2:t1:why-leaders-fail-to-protect-the-interest-of-thei",
                "concept_label": "Why Leaders Fail To Protect The Interest Of Thei",
                "topic_id": str(topic_id),
                "topic_title": "WHY LEADERS FAIL TO PROTECT THE INTEREST OF THEIR FOLLOWERS",
                "prompt": "Which concept is most central to understanding 'WHY LEADERS FAIL TO PROTECT THE INTEREST OF THEIR FOLLOWERS'?",
                "options": [
                    "Functions Of Political Parties",
                    "Topic Citizenship Education And Importance Of Ci",
                    "Why Leaders Fail To Protect The Interest Of Thei",
                    "Importance Of Employment",
                ],
                "correct_answer": "C",
            }
        ],
    )
    repo = MagicMock()
    repo.validate_student_scope.return_value = True
    repo.get_in_progress_diagnostic.return_value = existing
    repo.get_scope_topic_concept_rows.return_value = [
        {
            "topic_id": str(uuid4()),
            "topic_title": "Political Party",
            "concept_id": "civic:sss2:t1:functions-of-political-parties",
            "prereq_concept_ids": [],
        },
        {
            "topic_id": str(uuid4()),
            "topic_title": "Citizenship Education and Importance of Citizenship Education",
            "concept_id": "civic:sss2:t1:topic-citizenship-education-and-importance-of-ci",
            "prereq_concept_ids": [],
        },
        {
            "topic_id": str(topic_id),
            "topic_title": "WHY LEADERS FAIL TO PROTECT THE INTEREST OF THEIR FOLLOWERS",
            "concept_id": "civic:sss2:t1:why-leaders-fail-to-protect-the-interest-of-thei",
            "prereq_concept_ids": [],
        },
        {
            "topic_id": str(uuid4()),
            "topic_title": "Poverty and its Effects",
            "concept_id": "civic:sss2:t1:importance-of-employment",
            "prereq_concept_ids": [],
        },
    ]

    monkeypatch.setattr(diagnostic_service_module, "DiagnosticRepository", lambda db: repo)

    payload = DiagnosticStartIn(
        student_id=student_id,
        subject="civic",
        sss_level="SSS2",
        term=1,
        num_questions=10,
    )

    result = diagnostic_service_module.diagnostic_service.create_diagnostic_session(db=MagicMock(), payload=payload)

    question = result.questions[0]
    assert question.topic_title == "Why leaders fail to protect the interest of their followers"
    assert question.concept_label == "Why leaders fail to protect the interest of their followers"
    assert "WHY LEADERS FAIL" not in question.prompt
    assert "Functions of political parties" in question.options
    assert "Citizenship education and importance of citizenship education" in question.options
    assert any(detail.label == "Functions of political parties" and detail.context_title == "Political party" for detail in question.option_details)
