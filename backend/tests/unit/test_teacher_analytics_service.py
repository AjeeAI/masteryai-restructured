from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from backend.services.teacher_analytics_service import TeacherAnalyticsService


class FakeTeacherAnalyticsRepo:
    def __init__(self):
        self.teacher_id = uuid4()
        self.class_id = uuid4()
        self.student_a = uuid4()
        self.student_b = uuid4()
        self.users = {
            self.teacher_id: SimpleNamespace(id=self.teacher_id, role="teacher", is_active=True, display_name="Teacher", first_name="Teach", last_name="Er", email="teacher@example.com"),
            self.student_a: SimpleNamespace(id=self.student_a, role="student", is_active=True, display_name="Ada James", first_name="Ada", last_name="James", email="ada@example.com"),
            self.student_b: SimpleNamespace(id=self.student_b, role="student", is_active=True, display_name="Bola Musa", first_name="Bola", last_name="Musa", email="bola@example.com"),
        }
        self.teacher_class = SimpleNamespace(
            id=self.class_id,
            teacher_id=self.teacher_id,
            name="SSS2 Math A",
            subject="math",
            sss_level="SSS2",
            term=1,
        )
        self.intervention_id = uuid4()
        self.assignment_id = uuid4()

    def get_user(self, user_id):
        return self.users.get(user_id)

    def get_users_by_ids(self, user_ids):
        return {user_id: self.users[user_id] for user_id in user_ids if user_id in self.users}

    def get_teacher_class(self, *, teacher_id, class_id):
        if teacher_id == self.teacher_id and class_id == self.class_id:
            return self.teacher_class
        return None

    def get_active_student_ids(self, *, class_id):
        return [self.student_a, self.student_b]

    def get_recent_activity_stats(self, *, class_id, subject, term, since):
        return {
            self.student_a: {
                "event_count": 3,
                "duration_seconds": 300,
                "quiz_submitted_count": 1,
                "lesson_viewed_count": 2,
            },
            self.student_b: {
                "event_count": 0,
                "duration_seconds": 0,
                "quiz_submitted_count": 0,
                "lesson_viewed_count": 0,
            },
        }

    def get_avg_mastery_by_student(self, *, class_id, subject, term):
        return {self.student_a: 0.8, self.student_b: 0.25}

    def get_heatmap_points(self, *, class_id, subject, term):
        return [
            {"concept_id": "math:sss2:t1:fractions", "avg_score": 0.2, "student_count": 2},
            {"concept_id": "math:sss2:t1:ratio", "avg_score": 0.7, "student_count": 1},
        ]

    def get_scope_concept_rows(self, *, subject, sss_level, term):
        return [
            {
                "concept_id": "math:sss2:t1:fractions",
                "prereq_concept_ids": ["math:sss2:t1:number-sense"],
                "topic_id": uuid4(),
                "topic_title": "Fractions",
            },
            {
                "concept_id": "math:sss2:t1:number-sense",
                "prereq_concept_ids": [],
                "topic_id": uuid4(),
                "topic_title": "Number Sense",
            },
            {
                "concept_id": "math:sss2:t1:ratio",
                "prereq_concept_ids": [],
                "topic_id": uuid4(),
                "topic_title": "Ratio",
            },
        ]

    def get_student_concept_rows(self, *, class_id, subject, term, concept_ids):
        rows = [
            {
                "student_id": self.student_a,
                "concept_id": "math:sss2:t1:fractions",
                "mastery_score": 0.25,
                "last_evaluated_at": datetime.now(timezone.utc) - timedelta(days=1),
            },
            {
                "student_id": self.student_a,
                "concept_id": "math:sss2:t1:number-sense",
                "mastery_score": 0.3,
                "last_evaluated_at": datetime.now(timezone.utc) - timedelta(days=1),
            },
            {
                "student_id": self.student_a,
                "concept_id": "math:sss2:t1:ratio",
                "mastery_score": 0.35,
                "last_evaluated_at": datetime.now(timezone.utc) - timedelta(days=1),
            },
            {
                "student_id": self.student_b,
                "concept_id": "math:sss2:t1:fractions",
                "mastery_score": 0.78,
                "last_evaluated_at": datetime.now(timezone.utc) - timedelta(days=2),
            },
            {
                "student_id": self.student_b,
                "concept_id": "math:sss2:t1:number-sense",
                "mastery_score": 0.82,
                "last_evaluated_at": datetime.now(timezone.utc) - timedelta(days=2),
            },
            {
                "student_id": self.student_b,
                "concept_id": "math:sss2:t1:ratio",
                "mastery_score": 0.76,
                "last_evaluated_at": datetime.now(timezone.utc) - timedelta(days=2),
            },
        ]
        return [row for row in rows if row["concept_id"] in concept_ids]

    def get_negative_mastery_delta_by_student(self, *, class_id, subject, term, since):
        return {self.student_a: -0.12}

    def get_low_mastery_students(self, *, class_id, subject, term, threshold):
        return {self.student_b: 0.25}

    def get_student_timeline(self, *, class_id, student_id, limit):
        now = datetime.now(timezone.utc)
        return [
            {
                "event_type": "activity",
                "occurred_at": now - timedelta(hours=1),
                "details": {"activity_type": "lesson_viewed"},
            },
            {
                "event_type": "mastery_update",
                "occurred_at": now - timedelta(hours=2),
                "details": {"source": "practice", "updated_concepts": 2},
            },
        ]

    def get_class_interventions(self, *, class_id, subject, term, limit=50):
        now = datetime.now(timezone.utc)
        return [
            SimpleNamespace(
                id=self.intervention_id,
                student_id=self.student_a,
                intervention_type="support_plan",
                concept_id="math:sss2:t1:fractions",
                concept_label="Fractions",
                severity="high",
                status="open",
                created_at=now - timedelta(days=3),
                notes="Focused support on Fractions",
                action_plan="Repair Number Sense first",
            )
        ]

    def get_class_assignments(self, *, class_id, subject, term, limit=50):
        now = datetime.now(timezone.utc)
        return [
            SimpleNamespace(
                id=self.assignment_id,
                class_id=self.class_id,
                student_id=self.student_a,
                assignment_type="revision",
                concept_id="math:sss2:t1:fractions",
                concept_label="Fractions",
                ref_id="fractions-repair-pack",
                title="Fractions Repair Pack",
                status="assigned",
                due_at=None,
                created_at=now - timedelta(days=3),
            )
        ]

    def get_mastery_events_for_students_since(self, *, student_ids, subject, term, since):
        now = datetime.now(timezone.utc)
        return [
            SimpleNamespace(
                student_id=self.student_a,
                created_at=now - timedelta(days=1),
                source="practice",
                new_mastery=[{"concept_id": "math:sss2:t1:fractions", "delta": 0.12}],
            )
        ]

    def get_activity_rows_for_students_since(self, *, student_ids, subject, term, since):
        now = datetime.now(timezone.utc)
        return [
            SimpleNamespace(
                student_id=self.student_a,
                created_at=now - timedelta(days=1),
                event_type="lesson_viewed",
                duration_seconds=420,
                ref_id="fractions-repair-pack",
            )
        ]


def test_teacher_analytics_dashboard_metrics():
    repo = FakeTeacherAnalyticsRepo()
    service = TeacherAnalyticsService(repo)

    out = service.get_class_dashboard(teacher_id=repo.teacher_id, class_id=repo.class_id)
    assert out.total_students == 2
    assert out.active_students_7d == 1
    assert out.avg_study_time_seconds_7d == 150
    assert out.avg_mastery_score == 0.525
    assert out.completion_distribution.completed == 1
    assert out.completion_distribution.no_activity == 1


def test_teacher_analytics_heatmap_points():
    repo = FakeTeacherAnalyticsRepo()
    service = TeacherAnalyticsService(repo)

    out = service.get_class_heatmap(teacher_id=repo.teacher_id, class_id=repo.class_id)
    assert out.class_id == repo.class_id
    assert len(out.points) == 2
    assert out.points[0].concept_id == "math:sss2:t1:fractions"


def test_teacher_analytics_graph_summary_prioritises_blockers():
    repo = FakeTeacherAnalyticsRepo()
    service = TeacherAnalyticsService(repo)

    out = service.get_class_graph_summary(teacher_id=repo.teacher_id, class_id=repo.class_id)

    assert out.class_id == repo.class_id
    assert out.metrics.mapped_concepts == 3
    assert out.metrics.blocked_concepts >= 1
    assert out.graph_signal.status == "repair_prerequisite"
    assert len(out.nodes) == 3
    assert any(edge.target_concept_id == "math:sss2:t1:fractions" for edge in out.edges)
    assert out.weakest_blockers[0].concept_label in {"Fractions", "Number Sense"}


def test_teacher_analytics_alerts_include_expected_types():
    repo = FakeTeacherAnalyticsRepo()
    service = TeacherAnalyticsService(repo)

    out = service.get_class_alerts(teacher_id=repo.teacher_id, class_id=repo.class_id)
    kinds = {alert.alert_type for alert in out.alerts}
    assert "inactivity" in kinds
    assert "rapid_decline" in kinds
    assert "prereq_failure" in kinds


def test_teacher_analytics_graph_playbook_returns_actionable_steps():
    repo = FakeTeacherAnalyticsRepo()
    service = TeacherAnalyticsService(repo)

    out = service.get_class_graph_playbook(teacher_id=repo.teacher_id, class_id=repo.class_id)

    assert out.class_id == repo.class_id
    assert len(out.actions) >= 2
    assert out.actions[0].action_type in {"repair_prerequisite", "run_checkpoint"}
    assert any(action.action_type == "support_students" for action in out.actions)


def test_teacher_intervention_queue_prioritises_student_level_graph_repairs():
    repo = FakeTeacherAnalyticsRepo()
    service = TeacherAnalyticsService(repo)

    out = service.get_intervention_queue(teacher_id=repo.teacher_id, class_id=repo.class_id)

    assert out.class_id == repo.class_id
    assert out.total_items >= 1
    assert out.urgent_items >= 1
    assert out.student_targeted_items >= 1
    assert out.items[0].recommendation_type in {"repair_prerequisite", "repeat_risk_support"}
    assert out.items[0].student_id in {repo.student_a, repo.student_b}


def test_teacher_next_cluster_plan_repairs_prerequisite_before_reteach():
    repo = FakeTeacherAnalyticsRepo()
    service = TeacherAnalyticsService(repo)

    out = service.get_next_lesson_cluster_plan(teacher_id=repo.teacher_id, class_id=repo.class_id)

    assert out.class_id == repo.class_id
    assert out.plan_status == "repair_first"
    assert out.repair_first[0].concept_label == "Number Sense"
    assert out.teach_next[0].concept_label == "Fractions"
    assert any(action.action_type == "repair_prerequisite" for action in out.suggested_actions)


def test_teacher_analytics_concept_student_drilldown_orders_students_by_risk():
    repo = FakeTeacherAnalyticsRepo()
    service = TeacherAnalyticsService(repo)

    out = service.get_concept_student_drilldown(
        teacher_id=repo.teacher_id,
        class_id=repo.class_id,
        concept_id="math:sss2:t1:fractions",
    )

    assert out.class_id == repo.class_id
    assert out.concept_label == "Fractions"
    assert len(out.students) == 2
    assert out.students[0].status == "blocked"
    assert "Number Sense" in out.students[0].blocking_prerequisite_labels


def test_teacher_analytics_intervention_outcomes_show_real_follow_through():
    repo = FakeTeacherAnalyticsRepo()
    service = TeacherAnalyticsService(repo)

    out = service.get_intervention_outcomes(teacher_id=repo.teacher_id, class_id=repo.class_id)

    assert out.class_id == repo.class_id
    assert out.total_interventions == 1
    assert out.improving_interventions == 1
    assert out.outcomes[0].outcome_status == "improving"
    assert out.outcomes[0].concept_id == "math:sss2:t1:fractions"
    assert out.outcomes[0].concept_label == "Fractions"
    assert out.outcomes[0].net_mastery_delta > 0


def test_teacher_repeat_risk_identifies_multi_concept_student():
    repo = FakeTeacherAnalyticsRepo()
    service = TeacherAnalyticsService(repo)

    out = service.get_repeat_risk_summary(teacher_id=repo.teacher_id, class_id=repo.class_id)

    assert out.class_id == repo.class_id
    assert out.at_risk_student_count == 1
    assert out.repeat_blocker_students == 1
    assert out.students[0].student_id == repo.student_a
    assert out.students[0].blocked_concept_count >= 1
    assert out.students[0].flagged_concept_count >= 2
    assert out.students[0].driving_concepts[0].concept_label in {"Fractions", "Number Sense", "Ratio"}


def test_teacher_assignment_outcomes_show_real_follow_through():
    repo = FakeTeacherAnalyticsRepo()
    service = TeacherAnalyticsService(repo)

    out = service.get_assignment_outcomes(teacher_id=repo.teacher_id, class_id=repo.class_id)

    assert out.class_id == repo.class_id
    assert out.total_assignments == 1
    assert out.improving_assignments == 1
    assert out.outcomes[0].assignment_id == repo.assignment_id
    assert out.outcomes[0].student_id == repo.student_a
    assert out.outcomes[0].student_name == "Ada James"
    assert out.outcomes[0].concept_id == "math:sss2:t1:fractions"
    assert out.outcomes[0].concept_label == "Fractions"
    assert out.outcomes[0].engaged_student_count == 1
    assert out.outcomes[0].net_mastery_delta > 0


def test_teacher_assignment_outcomes_can_filter_by_exact_concept_tag():
    repo = FakeTeacherAnalyticsRepo()
    service = TeacherAnalyticsService(repo)

    out = service.get_assignment_outcomes(
        teacher_id=repo.teacher_id,
        class_id=repo.class_id,
        concept_id="math:sss2:t1:fractions",
    )

    assert len(out.outcomes) == 1
    assert out.outcomes[0].concept_id == "math:sss2:t1:fractions"


def test_teacher_risk_matrix_returns_student_vs_concept_view():
    repo = FakeTeacherAnalyticsRepo()
    service = TeacherAnalyticsService(repo)

    out = service.get_student_risk_matrix(teacher_id=repo.teacher_id, class_id=repo.class_id)

    assert out.class_id == repo.class_id
    assert len(out.concepts) >= 1
    assert len(out.students) >= 1
    assert out.students[0].blocked_concept_count >= 1
    assert any(cell.status in {"blocked", "needs_attention"} for cell in out.students[0].cells)


def test_teacher_concept_compare_surfaces_the_stronger_blocker():
    repo = FakeTeacherAnalyticsRepo()
    service = TeacherAnalyticsService(repo)

    out = service.get_concept_compare(
        teacher_id=repo.teacher_id,
        class_id=repo.class_id,
        left_concept_id="math:sss2:t1:fractions",
        right_concept_id="math:sss2:t1:ratio",
    )

    assert out.class_id == repo.class_id
    assert out.left.concept_label == "Fractions"
    assert out.right.concept_label == "Ratio"
    assert out.summary.students_compared == 2
    assert out.summary.recommended_focus_side == "left"
    assert out.students[0].comparison_signal in {"both_blocked", "left_weaker"}


def test_teacher_analytics_student_timeline_mapping():
    repo = FakeTeacherAnalyticsRepo()
    service = TeacherAnalyticsService(repo)

    out = service.get_student_timeline(
        teacher_id=repo.teacher_id,
        class_id=repo.class_id,
        student_id=repo.student_a,
        limit=20,
    )
    assert out.student_id == repo.student_a
    assert len(out.timeline) == 2
    assert out.timeline[0].event_type in {"activity", "mastery_update"}


def test_teacher_student_concept_trend_returns_current_scores_and_recent_deltas():
    repo = FakeTeacherAnalyticsRepo()
    service = TeacherAnalyticsService(repo)

    out = service.get_student_concept_trend(
        teacher_id=repo.teacher_id,
        class_id=repo.class_id,
        student_id=repo.student_a,
        concept_id="math:sss2:t1:fractions",
        days=30,
    )

    assert out.class_id == repo.class_id
    assert out.student_id == repo.student_a
    assert out.concept_label == "Fractions"
    assert out.status == "blocked"
    assert out.net_delta_30d == 0.12
    assert out.evidence_event_count == 1
    assert out.tracked_concepts[0].role == "focus"
    assert any(item.role == "prerequisite" and item.concept_label == "Number Sense" for item in out.tracked_concepts)
    assert out.recent_events[0].source == "practice"


def test_teacher_next_cluster_plan_export_contains_teacher_ready_markdown():
    repo = FakeTeacherAnalyticsRepo()
    service = TeacherAnalyticsService(repo)

    out = service.get_next_cluster_plan_export(teacher_id=repo.teacher_id, class_id=repo.class_id)

    assert out.export_kind == "next_cluster_plan"
    assert out.class_id == repo.class_id
    assert out.subject == "math"
    assert out.file_name.endswith(".md")
    assert "Repair" in out.share_text
    assert "Planning headline" in out.markdown
    assert any(section.title == "Teach next" for section in out.sections)


def test_teacher_class_briefing_export_combines_graph_and_outcome_story():
    repo = FakeTeacherAnalyticsRepo()
    service = TeacherAnalyticsService(repo)

    out = service.get_class_briefing_export(teacher_id=repo.teacher_id, class_id=repo.class_id)

    assert out.export_kind == "class_briefing"
    assert out.class_id == repo.class_id
    assert "class briefing" in out.title.lower()
    assert "students are currently driving repeated graph risk" in out.share_text
    assert any(section.title == "Outcome snapshot" for section in out.sections)


def test_teacher_presentation_aggregates_graph_queue_and_outcomes():
    repo = FakeTeacherAnalyticsRepo()
    service = TeacherAnalyticsService(repo)

    out = service.get_class_presentation(teacher_id=repo.teacher_id, class_id=repo.class_id)

    assert out.class_id == repo.class_id
    assert out.class_name == repo.teacher_class.name
    assert out.graph_summary.graph_signal.status == "repair_prerequisite"
    assert out.intervention_queue.total_items >= 1
    assert out.assignment_outcomes.total_assignments == 1
    assert out.intervention_outcomes.total_interventions == 1
    assert out.briefing.export_kind == "class_briefing"


def test_teacher_student_focus_export_contains_student_and_concept_evidence():
    repo = FakeTeacherAnalyticsRepo()
    service = TeacherAnalyticsService(repo)

    out = service.get_student_focus_export(
        teacher_id=repo.teacher_id,
        class_id=repo.class_id,
        student_id=repo.student_a,
        concept_id="math:sss2:t1:fractions",
    )

    assert out.export_kind == "student_focus"
    assert out.student_id == repo.student_a
    assert out.concept_label == "Fractions"
    assert out.file_name.endswith(".md")
    assert "Ada James" in out.share_text
    assert "Focus summary" in out.markdown
    assert any(section.title == "Blocking prerequisites" for section in out.sections)


def test_teacher_concept_compare_export_contains_teacher_ready_story():
    repo = FakeTeacherAnalyticsRepo()
    service = TeacherAnalyticsService(repo)

    out = service.get_concept_compare_export(
        teacher_id=repo.teacher_id,
        class_id=repo.class_id,
        left_concept_id="math:sss2:t1:fractions",
        right_concept_id="math:sss2:t1:ratio",
    )

    assert out.export_kind == "concept_compare"
    assert out.class_id == repo.class_id
    assert "Fractions vs Ratio" in out.title
    assert "Comparison headline" in out.markdown
    assert any(section.title == "Students driving the difference" for section in out.sections)
