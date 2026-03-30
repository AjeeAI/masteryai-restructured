import os
from itertools import product
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.config import settings
from backend.core.database import Base, get_db
from backend.main import app
from backend.models.curriculum_topic_map import CurriculumTopicMap
from backend.models.curriculum_version import CurriculumVersion
from backend.models.lesson import Lesson, LessonBlock
from backend.models.student_concept_mastery import StudentConceptMastery
from backend.models.subject import Subject
from backend.models.topic import Topic
from backend.models.user import User
from backend.repositories.diagnostic_repo import DiagnosticRepository
from backend.schemas.internal_graph_schema import ConceptUpdateIn, InternalGraphUpdateIn
from backend.schemas.tutor_schema import TutorAssessmentStartOut, TutorAssessmentSubmitOut
from backend.services.graph_client_service import graph_client_service
from backend.tests.integration.db_utils import resolve_test_database_url


TEST_DATABASE_URL = resolve_test_database_url(test_label="Section 8 graph-first integration flow")


engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
USER_EMAIL_PREFIX = "graphflow.student."


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_subjects(db):
    created_subject_ids = []
    subject_by_slug = {}
    for slug, name in [("math", "Mathematics"), ("english", "English"), ("civic", "Civic Education")]:
        subject = db.query(Subject).filter(Subject.slug == slug).first()
        if subject is None:
            subject = Subject(id=uuid4(), slug=slug, name=name)
            db.add(subject)
            db.flush()
            created_subject_ids.append(subject.id)
        subject_by_slug[slug] = subject
    return subject_by_slug, created_subject_ids


def _pick_empty_scope(db):
    subject_by_slug, created_subject_ids = _ensure_subjects(db)
    candidates = []
    for subject_slug, sss_level, term in product(("math", "english", "civic"), ("SSS1", "SSS2", "SSS3"), (1, 2, 3)):
        count = (
            db.query(Topic)
            .join(Subject, Subject.id == Topic.subject_id)
            .filter(
                Subject.slug == subject_slug,
                Topic.sss_level == sss_level,
                Topic.term == term,
                Topic.is_approved.is_(True),
            )
            .count()
        )
        candidates.append((count, subject_slug, sss_level, term))

    count, subject_slug, sss_level, term = min(candidates, key=lambda item: (item[0], item[1], item[2], item[3]))
    return {
        "subject": subject_slug,
        "sss_level": sss_level,
        "term": term,
        "subject_row": subject_by_slug[subject_slug],
        "created_subject_ids": created_subject_ids,
        "existing_approved_topic_count": count,
    }


def _register_and_login_student(client: TestClient) -> tuple[str, str]:
    email = f"{USER_EMAIL_PREFIX}{uuid4()}@example.com"
    password = "StrongPass123!"

    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "role": "student",
            "first_name": "Graph",
            "last_name": "Flow",
            "display_name": "Graph Flow",
        },
    )
    assert register_response.status_code == 201
    user_id = register_response.json()["user_id"]

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    return user_id, token


@pytest.fixture(autouse=True)
def setup_graph_first_scope(monkeypatch):
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    scope = _pick_empty_scope(db)
    subject = scope["subject"]
    sss_level = scope["sss_level"]
    term = scope["term"]
    subject_row = scope["subject_row"]
    token = uuid4().hex[:8]

    curriculum_version = CurriculumVersion(
        id=uuid4(),
        version_name=f"graph-first-{subject}-{sss_level.lower()}-t{term}-{token}",
        subject=subject,
        sss_level=sss_level,
        term=term,
        source_root="integration-test",
        source_file_count=3,
        status="published",
        metadata_payload={},
    )
    db.add(curriculum_version)
    db.flush()

    prereq_topic = Topic(
        id=uuid4(),
        subject_id=subject_row.id,
        sss_level=sss_level,
        term=term,
        title=f"Graph Prerequisite Foundations {token}",
        description="Build the prerequisite foundation for the current lesson.",
        curriculum_version_id=curriculum_version.id,
        is_approved=True,
    )
    target_topic = Topic(
        id=uuid4(),
        subject_id=subject_row.id,
        sss_level=sss_level,
        term=term,
        title=f"Graph Target Applications {token}",
        description="Apply the prerequisite idea to the main lesson target.",
        curriculum_version_id=curriculum_version.id,
        is_approved=True,
    )
    db.add_all([prereq_topic, target_topic])
    db.flush()

    prereq_concept_id = f"{subject}:{sss_level.lower()}:t{term}:graph-prerequisite"
    target_concept_id = f"{subject}:{sss_level.lower()}:t{term}:graph-target"

    db.add_all(
        [
            CurriculumTopicMap(
                id=uuid4(),
                version_id=curriculum_version.id,
                topic_id=prereq_topic.id,
                concept_id=prereq_concept_id,
                prereq_concept_ids=[],
                confidence=0.98,
                is_manual_override=False,
                created_by=None,
            ),
            CurriculumTopicMap(
                id=uuid4(),
                version_id=curriculum_version.id,
                topic_id=target_topic.id,
                concept_id=target_concept_id,
                prereq_concept_ids=[prereq_concept_id],
                confidence=0.99,
                is_manual_override=False,
                created_by=None,
            ),
        ]
    )
    db.flush()

    prereq_lesson = Lesson(
        id=uuid4(),
        topic_id=prereq_topic.id,
        title=f"Lesson: {prereq_topic.title}",
        summary="A structured prerequisite lesson used for graph-first integration coverage.",
        estimated_duration_minutes=14,
    )
    target_lesson = Lesson(
        id=uuid4(),
        topic_id=target_topic.id,
        title=f"Lesson: {target_topic.title}",
        summary="A structured target lesson used for graph-first integration coverage.",
        estimated_duration_minutes=18,
    )
    db.add_all([prereq_lesson, target_lesson])
    db.flush()
    db.add_all(
        [
            LessonBlock(
                id=uuid4(),
                lesson_id=prereq_lesson.id,
                block_type="text",
                order_index=1,
                content={"text": "State the prerequisite rule clearly and show one short example."},
            ),
            LessonBlock(
                id=uuid4(),
                lesson_id=target_lesson.id,
                block_type="text",
                order_index=1,
                content={"text": "Use the prerequisite rule to solve the target application step by step."},
            ),
            LessonBlock(
                id=uuid4(),
                lesson_id=target_lesson.id,
                block_type="example",
                order_index=2,
                content={
                    "prompt": "Apply the prerequisite idea in a short worked example.",
                    "solution": "Show the rule, substitute values, and verify the final answer.",
                },
            ),
        ]
    )
    db.commit()
    prereq_topic_id = prereq_topic.id
    prereq_topic_title = prereq_topic.title
    target_topic_id = target_topic.id
    target_topic_title = target_topic.title
    curriculum_version_id = curriculum_version.id
    prereq_lesson_id = prereq_lesson.id
    target_lesson_id = target_lesson.id
    db.close()

    original_get_scope_topics = DiagnosticRepository.get_scope_topics
    original_get_scope_rows = DiagnosticRepository.get_scope_topic_concept_rows

    async def _fake_generate_quiz_questions(**kwargs):
        question_id = uuid4()
        return [
            {
                "id": question_id,
                "text": "Which option best applies the target concept after the prerequisite has been mastered?",
                "options": [
                    "Ignore the prerequisite and guess the answer",
                    "Use the prerequisite idea to justify the target step",
                    "Skip directly to a final answer without explanation",
                    "Change the topic entirely",
                ],
                "correct_answer": "B",
                "concept_id": target_concept_id,
                "difficulty": kwargs["difficulty"],
            }
        ]

    async def _fake_generate_quiz_insights(quiz_id, attempt_id):
        return ["You used the prerequisite correctly and pushed the target concept forward."]

    async def _fake_quiz_graph_update(self, student_id, quiz_id, attempt_id, subject, sss_level, term, source, concept_breakdown):
        graph_client_service.push_mastery_update(
            self.db,
            payload=InternalGraphUpdateIn(
                student_id=student_id,
                quiz_id=quiz_id,
                attempt_id=attempt_id,
                subject=subject,
                sss_level=sss_level,
                term=term,
                timestamp=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
                source=source,
                concept_breakdown=[
                    ConceptUpdateIn(
                        concept_id=item.concept_id,
                        is_correct=item.is_correct,
                        weight_change=item.weight_change,
                    )
                    for item in concept_breakdown
                ],
            ),
        )
        return True

    async def _fake_assessment_start(self, payload):
        return TutorAssessmentStartOut(
            assessment_id=UUID("00000000-0000-0000-0000-000000000000"),
            question="Explain the prerequisite rule in one or two sentences and give a short example.",
            concept_id=payload.focus_concept_id or prereq_concept_id,
            concept_label=payload.focus_concept_label or "Graph Prerequisite",
            ideal_answer="State the prerequisite rule clearly and show one valid example.",
            hint="State the rule first, then give one example.",
            citations=[],
            actions=["ASSESSMENT_READY"],
        )

    async def _fake_assessment_submit(self, payload, *, question, concept_id, concept_label, ideal_answer):
        return TutorAssessmentSubmitOut(
            assessment_id=payload.assessment_id,
            is_correct=True,
            score=0.95,
            feedback="You demonstrated the prerequisite clearly and correctly.",
            ideal_answer=ideal_answer,
            concept_id=concept_id,
            concept_label=concept_label,
            mastery_updated=False,
            new_mastery=None,
            actions=["ASSESSMENT_EVALUATED"],
        )

    def _fake_prewarm_related_topics(*args, **kwargs):
        return {
            "warmed_topic_ids": [],
            "cache_hit_topic_ids": [],
            "failed_topic_ids": [],
        }

    def _fake_prewarm_scope(*args, **kwargs):
        return None

    def _fake_dashboard_prewarm(*args, **kwargs):
        return None

    def _filtered_scope_topics(self, *, subject: str, sss_level: str, term: int):
        topics = original_get_scope_topics(self, subject=subject, sss_level=sss_level, term=term)
        if subject == setup_subject and sss_level == setup_sss_level and int(term) == int(setup_term):
            allowed = {prereq_topic_id, target_topic_id}
            return [topic for topic in topics if topic.id in allowed]
        return topics

    def _filtered_scope_rows(self, *, subject: str, sss_level: str, term: int):
        rows = original_get_scope_rows(self, subject=subject, sss_level=sss_level, term=term)
        if subject == setup_subject and sss_level == setup_sss_level and int(term) == int(setup_term):
            allowed = {str(prereq_topic_id), str(target_topic_id)}
            return [row for row in rows if str(row.get("topic_id")) in allowed]
        return rows

    setup_subject = subject
    setup_sss_level = sss_level
    setup_term = term

    monkeypatch.setattr(settings, "ai_core_base_url", "")
    monkeypatch.setattr(settings, "ai_core_allow_fallback", True)
    monkeypatch.setattr(settings, "use_neo4j_graph", False)
    monkeypatch.setattr(settings, "prewarm_queue_enabled", False)
    monkeypatch.setattr(settings, "prewarm_worker_enabled", False)
    monkeypatch.setattr("backend.services.quiz_generate_service.generate_quiz_questions", _fake_generate_quiz_questions)
    monkeypatch.setattr("backend.services.quiz_results_service.generate_quiz_insights", _fake_generate_quiz_insights)
    monkeypatch.setattr("backend.services.graph_mastery_update_service.GraphMasteryUpdateService.send_update", _fake_quiz_graph_update)
    monkeypatch.setattr(
        "backend.services.tutor_orchestration_service.TutorOrchestrationService.assessment_start",
        _fake_assessment_start,
    )
    monkeypatch.setattr(
        "backend.services.tutor_orchestration_service.TutorOrchestrationService.assessment_submit",
        _fake_assessment_submit,
    )
    monkeypatch.setattr(
        "backend.services.lesson_experience_service.LessonExperienceService.prewarm_related_topics",
        classmethod(lambda cls, **kwargs: _fake_prewarm_related_topics()),
    )
    monkeypatch.setattr(
        "backend.services.lesson_experience_service.LessonExperienceService.prewarm_bootstrap_preview",
        classmethod(lambda cls, **kwargs: _fake_prewarm_related_topics()),
    )
    monkeypatch.setattr(
        "backend.services.course_experience_service.CourseExperienceService.prewarm_scope",
        classmethod(lambda cls, **kwargs: _fake_prewarm_scope()),
    )
    monkeypatch.setattr(
        "backend.services.dashboard_experience_service.DashboardExperienceService.prewarm",
        classmethod(lambda cls, **kwargs: _fake_dashboard_prewarm()),
    )
    monkeypatch.setattr(
        "backend.repositories.diagnostic_repo.DiagnosticRepository.get_scope_topics",
        _filtered_scope_topics,
    )
    monkeypatch.setattr(
        "backend.repositories.diagnostic_repo.DiagnosticRepository.get_scope_topic_concept_rows",
        _filtered_scope_rows,
    )
    app.dependency_overrides[get_db] = override_get_db

    yield {
        "subject": subject,
        "sss_level": sss_level,
        "term": term,
        "prereq_topic_id": prereq_topic_id,
        "prereq_topic_title": prereq_topic_title,
        "target_topic_id": target_topic_id,
        "target_topic_title": target_topic_title,
        "prereq_concept_id": prereq_concept_id,
        "target_concept_id": target_concept_id,
        "created_subject_ids": scope["created_subject_ids"],
        "curriculum_version_id": curriculum_version_id,
    }

    cleanup = TestingSessionLocal()
    created_users = cleanup.query(User).filter(User.email.like(f"{USER_EMAIL_PREFIX}%")).all()
    created_user_ids = [row.id for row in created_users]
    if created_user_ids:
        cleanup.query(User).filter(User.id.in_(created_user_ids)).delete(synchronize_session=False)
    cleanup.query(CurriculumTopicMap).filter(
        CurriculumTopicMap.version_id == curriculum_version_id
    ).delete(synchronize_session=False)
    cleanup.query(LessonBlock).filter(
        LessonBlock.lesson_id.in_([prereq_lesson_id, target_lesson_id])
    ).delete(synchronize_session=False)
    cleanup.query(Lesson).filter(
        Lesson.id.in_([prereq_lesson_id, target_lesson_id])
    ).delete(synchronize_session=False)
    cleanup.query(Topic).filter(
        Topic.id.in_([prereq_topic.id, target_topic.id])
    ).delete(synchronize_session=False)
    cleanup.query(CurriculumVersion).filter(
        CurriculumVersion.id == curriculum_version_id
    ).delete(synchronize_session=False)
    if scope["created_subject_ids"]:
        cleanup.query(Subject).filter(Subject.id.in_(scope["created_subject_ids"])).delete(synchronize_session=False)
    cleanup.commit()
    cleanup.close()
    app.dependency_overrides.clear()


def test_section8_graph_first_learning_flow(setup_graph_first_scope):
    client = TestClient(app)
    user_id, token = _register_and_login_student(client)
    headers = {"Authorization": f"Bearer {token}"}

    subject = setup_graph_first_scope["subject"]
    sss_level = setup_graph_first_scope["sss_level"]
    term = setup_graph_first_scope["term"]
    prereq_topic_id = setup_graph_first_scope["prereq_topic_id"]
    target_topic_id = setup_graph_first_scope["target_topic_id"]
    prereq_topic_title = setup_graph_first_scope["prereq_topic_title"]
    target_topic_title = setup_graph_first_scope["target_topic_title"]
    prereq_concept_id = setup_graph_first_scope["prereq_concept_id"]
    target_concept_id = setup_graph_first_scope["target_concept_id"]

    profile_response = client.post(
        "/api/v1/students/profile/setup",
        json={
            "student_id": user_id,
            "sss_level": sss_level,
            "subjects": [subject],
            "term": term,
        },
        headers=headers,
    )
    assert profile_response.status_code == 200

    seed_db = TestingSessionLocal()
    seed_db.add(
        StudentConceptMastery(
            student_id=UUID(user_id),
            subject=subject,
            sss_level=sss_level,
            term=term,
            concept_id=prereq_concept_id,
            mastery_score=0.68,
            source="diagnostic",
        )
    )
    seed_db.commit()
    seed_db.close()

    graph_context = client.get(
        "/api/v1/learning/graph/lesson-context",
        params={
            "student_id": user_id,
            "subject": subject,
            "sss_level": sss_level,
            "term": term,
            "topic_id": str(target_topic_id),
        },
        headers=headers,
    )
    assert graph_context.status_code == 200
    graph_context_json = graph_context.json()
    assert graph_context_json["topic_id"] == str(target_topic_id)
    prerequisite_node_before = next(
        node for node in graph_context_json["prerequisite_concepts"] if node["concept_id"] == prereq_concept_id
    )
    assert float(prerequisite_node_before["mastery_score"]) == pytest.approx(0.68, abs=0.001)
    assert prerequisite_node_before["recommended_topic_id"] == str(prereq_topic_id)

    session_bootstrap = client.post(
        "/api/v1/tutor/session/bootstrap",
        json={
            "student_id": user_id,
            "subject": subject,
            "sss_level": sss_level,
            "term": term,
            "topic_id": str(target_topic_id),
        },
        headers=headers,
    )
    assert session_bootstrap.status_code == 200, session_bootstrap.text
    session_bootstrap_json = session_bootstrap.json()
    session_id = session_bootstrap_json["session_id"]
    assert session_bootstrap_json["topic_id"] == str(target_topic_id)
    assert session_bootstrap_json["graph_context"]["topic_title"] == target_topic_title

    lesson_cockpit = client.post(
        "/api/v1/learning/lesson/cockpit",
        json={
            "student_id": user_id,
            "subject": subject,
            "sss_level": sss_level,
            "term": term,
            "topic_id": str(target_topic_id),
            "session_id": session_id,
        },
        headers=headers,
    )
    assert lesson_cockpit.status_code == 200
    lesson_cockpit_json = lesson_cockpit.json()
    assert lesson_cockpit_json["tutor_bootstrap"]["session_id"] == session_id
    assert lesson_cockpit_json["why_topic_detail"]["topic_id"] == str(target_topic_id)

    assessment_start = client.post(
        "/api/v1/tutor/assessment/start",
        json={
            "student_id": user_id,
            "session_id": session_id,
            "subject": subject,
            "sss_level": sss_level,
            "term": term,
            "topic_id": str(target_topic_id),
            "focus_concept_id": prereq_concept_id,
            "focus_concept_label": "Graph Prerequisite",
            "difficulty": "medium",
        },
        headers=headers,
    )
    assert assessment_start.status_code == 200
    assessment_start_json = assessment_start.json()
    assert assessment_start_json["concept_id"] == prereq_concept_id
    assessment_id = assessment_start_json["assessment_id"]

    assessment_submit = client.post(
        "/api/v1/tutor/assessment/submit",
        json={
            "student_id": user_id,
            "session_id": session_id,
            "assessment_id": assessment_id,
            "subject": subject,
            "sss_level": sss_level,
            "term": term,
            "topic_id": str(target_topic_id),
            "answer": "The prerequisite rule explains the foundation and one short example shows how to use it.",
        },
        headers=headers,
    )
    assert assessment_submit.status_code == 200
    assessment_submit_json = assessment_submit.json()
    assert assessment_submit_json["mastery_updated"] is True
    assert float(assessment_submit_json["new_mastery"]) >= 0.8
    assert assessment_submit_json["graph_remediation"]["focus_concept_id"] == prereq_concept_id

    graph_context_after_assessment = client.get(
        "/api/v1/learning/graph/lesson-context",
        params={
            "student_id": user_id,
            "subject": subject,
            "sss_level": sss_level,
            "term": term,
            "topic_id": str(target_topic_id),
        },
        headers=headers,
    )
    assert graph_context_after_assessment.status_code == 200
    graph_context_after_json = graph_context_after_assessment.json()
    prerequisite_node_after = next(
        node for node in graph_context_after_json["prerequisite_concepts"] if node["concept_id"] == prereq_concept_id
    )
    assert float(prerequisite_node_after["mastery_score"]) >= 0.8
    current_target_node = next(
        node for node in graph_context_after_json["current_concepts"] if node["concept_id"] == target_concept_id
    )
    assert not current_target_node["blocking_prerequisite_labels"]

    generate_quiz = client.post(
        "/api/v1/learning/quizzes/generate",
        json={
            "student_id": user_id,
            "subject": subject,
            "sss_level": sss_level,
            "term": term,
            "topic_id": str(target_topic_id),
            "purpose": "practice",
            "difficulty": "medium",
            "num_questions": 1,
        },
        headers=headers,
    )
    assert generate_quiz.status_code == 200
    quiz_json = generate_quiz.json()
    quiz_id = quiz_json["quiz_id"]
    assert quiz_json["questions"][0]["concept_id"] == target_concept_id

    submit_quiz = client.post(
        f"/api/v1/learning/quizzes/{quiz_id}/submit",
        json={
            "student_id": user_id,
            "answers": [{"question_id": quiz_json["questions"][0]["id"], "answer": "B"}],
            "time_taken_seconds": 75,
        },
        headers=headers,
    )
    assert submit_quiz.status_code == 200
    attempt_id = submit_quiz.json()["attempt_id"]

    quiz_results = client.get(
        f"/api/v1/learning/quizzes/{quiz_id}/results",
        params={"student_id": user_id, "attempt_id": attempt_id},
        headers=headers,
    )
    assert quiz_results.status_code == 200
    quiz_results_json = quiz_results.json()
    assert quiz_results_json["concept_breakdown"][0]["concept_id"] == target_concept_id
    assert quiz_results_json["concept_breakdown"][0]["concept_label"]
    assert quiz_results_json["insights"]

    latest_intervention = client.get(
        "/api/v1/learning/course/latest-intervention",
        params={"student_id": user_id},
        headers=headers,
    )
    assert latest_intervention.status_code == 200
    latest_intervention_json = latest_intervention.json()
    assert latest_intervention_json["subject"] == subject
    assert len(latest_intervention_json["intervention_timeline"]) >= 2
    assert latest_intervention_json["recent_evidence"]["source"] == "practice"

    course_after = client.get(
        "/api/v1/learning/course/bootstrap",
        params={"student_id": user_id, "subject": subject, "term": term},
        headers=headers,
    )
    assert course_after.status_code == 200
    course_after_json = course_after.json()
    assert course_after_json["recent_evidence"]["source"] == "practice"
    assert len(course_after_json["intervention_timeline"]) >= 2

    dashboard_after = client.get(
        "/api/v1/learning/dashboard/bootstrap",
        params={"student_id": user_id, "subject": subject},
        headers=headers,
    )
    assert dashboard_after.status_code == 200
    dashboard_after_json = dashboard_after.json()
    assert dashboard_after_json["course_bootstrap"]["recent_evidence"]["source"] == "practice"
    assert len(dashboard_after_json["course_bootstrap"]["intervention_timeline"]) >= 2

    history = client.get(
        f"/api/v1/tutor/sessions/{session_id}/history",
        params={"student_id": user_id},
        headers=headers,
    )
    assert history.status_code == 200
    history_json = history.json()
    assert len(history_json["messages"]) >= 4
    assert any(item["role"] == "system" for item in history_json["messages"])
    assert any(item["role"] == "assistant" for item in history_json["messages"])
