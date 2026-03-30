from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.main import app
from backend.services.teacher_service import TeacherServiceConflictError, TeacherServiceUnauthorizedError


def _override_db():
    yield object()


def test_teachers_endpoints_success(monkeypatch):
    teacher_id = uuid4()
    class_id = uuid4()
    student_id = uuid4()

    def _override_user():
        return SimpleNamespace(id=teacher_id, role="teacher")

    class _TeacherService:
        def list_classes(self, *, teacher_id):
            return {
                "classes": [
                    {
                        "id": str(class_id),
                        "teacher_id": str(teacher_id),
                        "name": "SSS2 Math A",
                        "description": None,
                        "subject": "math",
                        "sss_level": "SSS2",
                        "term": 1,
                        "is_active": True,
                        "enrolled_count": 1,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
                ]
            }

        def create_class(self, *, teacher_id, payload):
            return self.list_classes(teacher_id=teacher_id)["classes"][0]

        def enroll_students(self, *, teacher_id, class_id, payload):
            return {
                "class_id": str(class_id),
                "enrolled_student_ids": [str(student_id)],
                "already_enrolled_student_ids": [],
                "total_enrolled": 1,
            }

        def remove_student_enrollment(self, *, teacher_id, class_id, student_id):
            return True

        def create_assignment(self, *, teacher_id, payload):
            return {
                "id": str(uuid4()),
                "teacher_id": str(teacher_id),
                "class_id": str(payload.class_id) if payload.class_id else None,
                "student_id": str(payload.student_id) if payload.student_id else None,
                "assignment_type": payload.assignment_type,
                "ref_id": payload.ref_id,
                "title": payload.title,
                "instructions": payload.instructions,
                "subject": payload.subject,
                "sss_level": payload.sss_level,
                "term": payload.term,
                "due_at": None,
                "status": "assigned",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

        def create_intervention(self, *, teacher_id, payload):
            return {
                "id": str(uuid4()),
                "teacher_id": str(teacher_id),
                "class_id": str(payload.class_id) if payload.class_id else None,
                "student_id": str(payload.student_id),
                "intervention_type": payload.intervention_type,
                "severity": payload.severity,
                "subject": payload.subject,
                "sss_level": payload.sss_level,
                "term": payload.term,
                "notes": payload.notes,
                "action_plan": payload.action_plan,
                "status": "open",
                "resolved_at": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

        def create_bulk_assignments(self, *, teacher_id, payload):
            return {
                "created_count": len(payload.student_ids),
                "student_ids": [str(item) for item in payload.student_ids],
                "assignment_ids": [str(uuid4()) for _ in payload.student_ids],
            }

        def create_bulk_interventions(self, *, teacher_id, payload):
            return {
                "created_count": len(payload.student_ids),
                "student_ids": [str(item) for item in payload.student_ids],
                "intervention_ids": [str(uuid4()) for _ in payload.student_ids],
            }

        def update_intervention(self, *, teacher_id, intervention_id, payload):
            return {
                "id": str(intervention_id),
                "teacher_id": str(teacher_id),
                "class_id": str(class_id),
                "student_id": str(student_id),
                "intervention_type": "note",
                "severity": "medium",
                "subject": "math",
                "sss_level": "SSS2",
                "term": 1,
                "notes": "Needs extra help",
                "action_plan": "Follow-up session",
                "status": payload.status,
                "resolved_at": datetime.now(timezone.utc).isoformat() if payload.status == "resolved" else None,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

    class _AnalyticsService:
        def get_class_dashboard(self, *, teacher_id, class_id):
            return {
                "class_id": str(class_id),
                "total_students": 1,
                "active_students_7d": 1,
                "avg_study_time_seconds_7d": 120,
                "avg_mastery_score": 0.5,
                "completion_distribution": {"completed": 1, "in_progress": 0, "no_activity": 0},
            }

        def get_class_heatmap(self, *, teacher_id, class_id):
            return {"class_id": str(class_id), "points": [{"concept_id": "c1", "avg_score": 0.5, "student_count": 1}]}

        def get_class_graph_summary(self, *, teacher_id, class_id):
            return {
                "class_id": str(class_id),
                "metrics": {
                    "mapped_concepts": 2,
                    "blocked_concepts": 1,
                    "weak_concepts": 1,
                    "mastered_concepts": 0,
                    "unassessed_concepts": 0,
                },
                "graph_signal": {
                    "status": "repair_prerequisite",
                    "headline": "Repair Number Sense before pushing Fractions.",
                    "supporting_reason": "A prerequisite barrier exists in the class graph.",
                    "focus_concept_label": "Fractions",
                    "blocking_prerequisite_label": "Number Sense",
                    "recommended_action": "Run a prerequisite bridge drill.",
                },
                "nodes": [
                    {
                        "concept_id": "math:sss2:t1:number-sense",
                        "concept_label": "Number Sense",
                        "topic_id": str(class_id),
                        "topic_title": "Number Sense",
                        "avg_score": 0.22,
                        "student_count": 1,
                        "status": "needs_attention",
                        "prerequisite_labels": [],
                        "blocking_prerequisite_labels": [],
                        "recommended_action": "Strengthen this concept cluster with guided practice.",
                    },
                    {
                        "concept_id": "math:sss2:t1:fractions",
                        "concept_label": "Fractions",
                        "topic_id": str(class_id),
                        "topic_title": "Fractions",
                        "avg_score": 0.31,
                        "student_count": 1,
                        "status": "blocked",
                        "prerequisite_labels": ["Number Sense"],
                        "blocking_prerequisite_labels": ["Number Sense"],
                        "recommended_action": "Repair the weakest prerequisite before pushing this concept.",
                    },
                ],
                "edges": [
                    {
                        "source_concept_id": "math:sss2:t1:number-sense",
                        "target_concept_id": "math:sss2:t1:fractions",
                        "status": "blocked",
                    }
                ],
                "weakest_blockers": [
                    {
                        "concept_id": "math:sss2:t1:fractions",
                        "concept_label": "Fractions",
                        "topic_id": str(class_id),
                        "topic_title": "Fractions",
                        "avg_score": 0.31,
                        "student_count": 1,
                        "status": "blocked",
                        "prerequisite_labels": ["Number Sense"],
                        "blocking_prerequisite_labels": ["Number Sense"],
                        "recommended_action": "Repair the weakest prerequisite before pushing this concept.",
                    }
                ],
                "ready_to_push": [],
            }

        def get_class_graph_playbook(self, *, teacher_id, class_id):
            return {
                "class_id": str(class_id),
                "actions": [
                    {
                        "action_type": "repair_prerequisite",
                        "title": "Repair Fractions through its blocker first",
                        "summary": "Start with Number Sense before reteaching Fractions.",
                        "severity": "high",
                        "target_concept_label": "Fractions",
                        "target_topic_id": str(class_id),
                        "target_topic_title": "Fractions",
                        "suggested_assignment_type": "revision",
                        "suggested_intervention_type": "support_plan",
                        "affected_student_count": 1,
                    }
                ],
            }

        def get_intervention_queue(self, *, teacher_id, class_id):
            return {
                "class_id": str(class_id),
                "total_items": 2,
                "urgent_items": 1,
                "student_targeted_items": 2,
                "class_scope_items": 0,
                "items": [
                    {
                        "queue_id": "repair_prerequisite:student-1:math:sss2:t1:fractions",
                        "priority": "urgent",
                        "recommendation_type": "repair_prerequisite",
                        "headline": "Repair Number Sense before reteaching Fractions for Student One.",
                        "rationale": "Repair the blocking prerequisite before reteaching this concept.",
                        "student_id": str(student_id),
                        "student_name": "Student One",
                        "concept_id": "math:sss2:t1:fractions",
                        "concept_label": "Fractions",
                        "topic_id": str(class_id),
                        "topic_title": "Fractions",
                        "blocking_prerequisite_labels": ["Number Sense"],
                        "suggested_assignment_type": "revision",
                        "suggested_intervention_type": "support_plan",
                    }
                ],
            }

        def get_next_lesson_cluster_plan(self, *, teacher_id, class_id):
            return {
                "class_id": str(class_id),
                "plan_status": "repair_first",
                "headline": "Repair Number Sense before reteaching Fractions.",
                "rationale": "The next lesson cluster is blocked by a weak prerequisite.",
                "repair_first": [
                    {
                        "concept_id": "math:sss2:t1:number-sense",
                        "concept_label": "Number Sense",
                        "topic_id": str(class_id),
                        "topic_title": "Number Sense",
                        "status": "needs_attention",
                        "avg_score": 0.22,
                        "student_count": 1,
                        "blocking_prerequisite_labels": [],
                        "recommended_action": "Strengthen this concept cluster with guided practice.",
                    }
                ],
                "teach_next": [
                    {
                        "concept_id": "math:sss2:t1:fractions",
                        "concept_label": "Fractions",
                        "topic_id": str(class_id),
                        "topic_title": "Fractions",
                        "status": "blocked",
                        "avg_score": 0.31,
                        "student_count": 1,
                        "blocking_prerequisite_labels": ["Number Sense"],
                        "recommended_action": "Repair the weakest prerequisite before pushing this concept.",
                    }
                ],
                "watchlist": [],
                "suggested_actions": [
                    {
                        "action_type": "repair_prerequisite",
                        "title": "Repair Fractions through its blocker first",
                        "summary": "Start with Number Sense before reteaching Fractions.",
                        "severity": "high",
                        "target_concept_label": "Fractions",
                        "target_topic_id": str(class_id),
                        "target_topic_title": "Fractions",
                        "suggested_assignment_type": "revision",
                        "suggested_intervention_type": "support_plan",
                        "affected_student_count": 1,
                    }
                ],
            }

        def get_next_cluster_plan_export(self, *, teacher_id, class_id):
            return {
                "export_kind": "next_cluster_plan",
                "class_id": str(class_id),
                "class_name": "SSS2 Math A",
                "subject": "math",
                "sss_level": "SSS2",
                "term": 1,
                "title": "SSS2 Math A cluster plan",
                "subtitle": "SSS2 Math A • Math • SSS2 Term 1",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "file_name": "sss2-math-a-term1-next-cluster-plan.md",
                "share_text": "Repair Number Sense before reteaching Fractions.",
                "markdown": "# SSS2 Math A cluster plan",
                "sections": [
                    {"title": "Planning headline", "items": ["Repair Number Sense before reteaching Fractions."]},
                ],
                "student_id": None,
                "student_name": None,
                "concept_id": None,
                "concept_label": None,
            }

        def get_class_briefing_export(self, *, teacher_id, class_id):
            return {
                "export_kind": "class_briefing",
                "class_id": str(class_id),
                "class_name": "SSS2 Math A",
                "subject": "math",
                "sss_level": "SSS2",
                "term": 1,
                "title": "SSS2 Math A class briefing",
                "subtitle": "SSS2 Math A • Math • SSS2 Term 1",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "file_name": "sss2-math-a-class-briefing.md",
                "share_text": "Repair Number Sense before reteaching Fractions.",
                "markdown": "# SSS2 Math A class briefing",
                "sections": [
                    {"title": "Graph signal", "items": ["Repair Number Sense before reteaching Fractions."]},
                ],
                "student_id": None,
                "student_name": None,
                "concept_id": None,
                "concept_label": None,
            }

        def get_class_presentation(self, *, teacher_id, class_id):
            return {
                "class_id": str(class_id),
                "class_name": "SSS2 Math A",
                "subject": "math",
                "sss_level": "SSS2",
                "term": 1,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "dashboard": self.get_class_dashboard(teacher_id=teacher_id, class_id=class_id),
                "graph_summary": self.get_class_graph_summary(teacher_id=teacher_id, class_id=class_id),
                "intervention_queue": self.get_intervention_queue(teacher_id=teacher_id, class_id=class_id),
                "next_cluster_plan": self.get_next_lesson_cluster_plan(teacher_id=teacher_id, class_id=class_id),
                "assignment_outcomes": self.get_assignment_outcomes(teacher_id=teacher_id, class_id=class_id),
                "intervention_outcomes": self.get_intervention_outcomes(teacher_id=teacher_id, class_id=class_id),
                "briefing": self.get_class_briefing_export(teacher_id=teacher_id, class_id=class_id),
            }

        def get_class_alerts(self, *, teacher_id, class_id):
            return {"class_id": str(class_id), "alerts": []}

        def get_intervention_outcomes(self, *, teacher_id, class_id, concept_id=None):
            return {
                "class_id": str(class_id),
                "total_interventions": 1,
                "open_interventions": 1,
                "improving_interventions": 1,
                "declining_interventions": 0,
                "no_evidence_interventions": 0,
                "avg_net_mastery_delta": 0.12,
                "outcomes": [
                    {
                        "intervention_id": str(uuid4()),
                        "student_id": str(student_id),
                        "student_name": "Student One",
                        "intervention_type": "support_plan",
                        "severity": "high",
                        "concept_id": concept_id or "math:sss2:t1:fractions",
                        "concept_label": "Fractions",
                        "status": "open",
                        "outcome_status": "improving",
                        "net_mastery_delta": 0.12,
                        "evidence_event_count": 1,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "latest_mastery_event_at": datetime.now(timezone.utc).isoformat(),
                        "notes": "Focused support on Fractions",
                        "action_plan": "Repair Number Sense first",
                    }
                ],
            }

        def get_assignment_outcomes(self, *, teacher_id, class_id, concept_id=None):
            return {
                "class_id": str(class_id),
                "total_assignments": 1,
                "open_assignments": 1,
                "improving_assignments": 1,
                "declining_assignments": 0,
                "no_evidence_assignments": 0,
                "avg_net_mastery_delta": 0.12,
                "outcomes": [
                    {
                        "assignment_id": str(uuid4()),
                        "title": "Fractions Repair Pack",
                        "assignment_type": "revision",
                        "status": "assigned",
                        "ref_id": "fractions-repair-pack",
                        "concept_id": concept_id or "math:sss2:t1:fractions",
                        "concept_label": "Fractions",
                        "target_scope": "student",
                        "student_id": str(student_id),
                        "student_name": "Student One",
                        "target_student_count": 1,
                        "engaged_student_count": 1,
                        "evidence_event_count": 1,
                        "outcome_status": "improving",
                        "net_mastery_delta": 0.12,
                        "due_at": None,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                ],
            }

        def get_repeat_risk_summary(self, *, teacher_id, class_id):
            return {
                "class_id": str(class_id),
                "at_risk_student_count": 1,
                "repeat_blocker_students": 1,
                "repeat_weakness_students": 0,
                "students": [
                    {
                        "student_id": str(student_id),
                        "student_name": "Student One",
                        "risk_status": "repeat_blocker",
                        "blocked_concept_count": 1,
                        "weak_concept_count": 2,
                        "flagged_concept_count": 3,
                        "overall_mastery_score": 0.42,
                        "recent_activity_count_7d": 2,
                        "recent_study_time_seconds_7d": 180,
                        "recommended_action": "Repair Number Sense before reteaching Fractions.",
                        "driving_concepts": [
                            {
                                "concept_id": "math:sss2:t1:fractions",
                                "concept_label": "Fractions",
                                "topic_id": str(class_id),
                                "topic_title": "Fractions",
                                "status": "blocked",
                                "concept_score": 0.31,
                                "blocking_prerequisite_labels": ["Number Sense"],
                            }
                        ],
                    }
                ],
            }

        def get_student_risk_matrix(self, *, teacher_id, class_id):
            return {
                "class_id": str(class_id),
                "concepts": [
                    {
                        "concept_id": "math:sss2:t1:fractions",
                        "concept_label": "Fractions",
                        "topic_id": str(class_id),
                        "topic_title": "Fractions",
                        "status": "blocked",
                    },
                    {
                        "concept_id": "math:sss2:t1:ratio",
                        "concept_label": "Ratio",
                        "topic_id": str(class_id),
                        "topic_title": "Ratio",
                        "status": "needs_attention",
                    },
                ],
                "students": [
                    {
                        "student_id": str(student_id),
                        "student_name": "Student One",
                        "overall_mastery_score": 0.42,
                        "blocked_concept_count": 1,
                        "weak_concept_count": 1,
                        "recent_activity_count_7d": 2,
                        "recent_study_time_seconds_7d": 180,
                        "cells": [
                            {
                                "concept_id": "math:sss2:t1:fractions",
                                "status": "blocked",
                                "concept_score": 0.31,
                                "blocking_prerequisite_labels": ["Number Sense"],
                            },
                            {
                                "concept_id": "math:sss2:t1:ratio",
                                "status": "needs_attention",
                                "concept_score": 0.38,
                                "blocking_prerequisite_labels": [],
                            },
                        ],
                    }
                ],
            }

        def get_concept_compare(self, *, teacher_id, class_id, left_concept_id, right_concept_id):
            return {
                "class_id": str(class_id),
                "left": {
                    "concept_id": left_concept_id,
                    "concept_label": "Fractions",
                    "topic_id": str(class_id),
                    "topic_title": "Fractions",
                    "status": "blocked",
                    "avg_score": 0.31,
                    "student_count": 1,
                    "blocking_prerequisite_labels": ["Number Sense"],
                },
                "right": {
                    "concept_id": right_concept_id,
                    "concept_label": "Ratio",
                    "topic_id": str(class_id),
                    "topic_title": "Ratio",
                    "status": "needs_attention",
                    "avg_score": 0.38,
                    "student_count": 1,
                    "blocking_prerequisite_labels": [],
                },
                "summary": {
                    "students_compared": 1,
                    "both_blocked_count": 0,
                    "left_weaker_count": 1,
                    "right_weaker_count": 0,
                    "both_ready_count": 0,
                    "avg_left_score": 0.31,
                    "avg_right_score": 0.38,
                    "recommended_focus_side": "left",
                    "headline": "Fractions is the stronger blocker across the class.",
                    "rationale": "More students are weaker on Fractions than on Ratio.",
                },
                "students": [
                    {
                        "student_id": str(student_id),
                        "student_name": "Student One",
                        "overall_mastery_score": 0.42,
                        "recent_activity_count_7d": 2,
                        "recent_study_time_seconds_7d": 180,
                        "stronger_side": "right",
                        "comparison_signal": "left_weaker",
                        "left": {
                            "concept_id": left_concept_id,
                            "concept_label": "Fractions",
                            "status": "blocked",
                            "concept_score": 0.31,
                            "blocking_prerequisite_labels": ["Number Sense"],
                        },
                        "right": {
                            "concept_id": right_concept_id,
                            "concept_label": "Ratio",
                            "status": "needs_attention",
                            "concept_score": 0.38,
                            "blocking_prerequisite_labels": [],
                        },
                    }
                ],
            }

        def get_concept_compare_export(self, *, teacher_id, class_id, left_concept_id, right_concept_id):
            return {
                "export_kind": "concept_compare",
                "class_id": str(class_id),
                "class_name": "SSS2 Math A",
                "subject": "math",
                "sss_level": "SSS2",
                "term": 1,
                "title": "Fractions vs Ratio",
                "subtitle": "SSS2 Math A • Fractions vs Ratio • Math SSS2 Term 1",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "file_name": "fractions-vs-ratio.md",
                "share_text": "Fractions is the stronger blocker across the class.",
                "markdown": "# Fractions vs Ratio\n\n## Comparison headline",
                "sections": [
                    {"title": "Comparison headline", "items": ["Fractions is the stronger blocker across the class."]},
                ],
                "student_id": None,
                "student_name": None,
                "concept_id": left_concept_id,
                "concept_label": "Fractions vs Ratio",
            }

        def get_concept_student_drilldown(self, *, teacher_id, class_id, concept_id):
            return {
                "class_id": str(class_id),
                "concept_id": concept_id,
                "concept_label": "Fractions",
                "topic_id": str(class_id),
                "topic_title": "Fractions",
                "students": [
                    {
                        "student_id": str(student_id),
                        "student_name": "Student One",
                        "concept_score": 0.31,
                        "overall_mastery_score": 0.42,
                        "status": "blocked",
                        "blocking_prerequisite_labels": ["Number Sense"],
                        "recent_activity_count_7d": 2,
                        "recent_study_time_seconds_7d": 180,
                        "recommended_action": "Repair the blocking prerequisite before reteaching this concept.",
                        "last_evaluated_at": datetime.now(timezone.utc).isoformat(),
                    }
                ],
            }

        def get_student_timeline(self, *, teacher_id, class_id, student_id, limit):
            return {"class_id": str(class_id), "student_id": str(student_id), "timeline": []}

        def get_student_concept_trend(self, *, teacher_id, class_id, student_id, concept_id, days):
            return {
                "class_id": str(class_id),
                "student_id": str(student_id),
                "concept_id": concept_id,
                "concept_label": "Fractions",
                "current_score": 0.31,
                "last_evaluated_at": datetime.now(timezone.utc).isoformat(),
                "status": "blocked",
                "blocking_prerequisite_labels": ["Number Sense"],
                "net_delta_30d": 0.12,
                "evidence_event_count": 1,
                "tracked_concepts": [
                    {
                        "concept_id": concept_id,
                        "concept_label": "Fractions",
                        "role": "focus",
                        "current_score": 0.31,
                        "last_evaluated_at": datetime.now(timezone.utc).isoformat(),
                    },
                    {
                        "concept_id": "math:sss2:t1:number-sense",
                        "concept_label": "Number Sense",
                        "role": "prerequisite",
                        "current_score": 0.3,
                        "last_evaluated_at": datetime.now(timezone.utc).isoformat(),
                    },
                ],
                "recent_events": [
                    {
                        "concept_id": concept_id,
                        "concept_label": "Fractions",
                        "occurred_at": datetime.now(timezone.utc).isoformat(),
                        "delta": 0.12,
                        "source": "practice",
                    }
                ],
            }

        def get_student_focus_export(self, *, teacher_id, class_id, student_id, concept_id):
            return {
                "export_kind": "student_focus",
                "class_id": str(class_id),
                "class_name": "SSS2 Math A",
                "subject": "math",
                "sss_level": "SSS2",
                "term": 1,
                "title": "Student One focus on Fractions",
                "subtitle": "Student One • Fractions • SSS2 Math A",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "file_name": "student-one-fractions-focus.md",
                "share_text": "Student One is blocked on Fractions.",
                "markdown": "# Student One focus on Fractions",
                "sections": [
                    {"title": "Focus summary", "items": ["Status: blocked"]},
                ],
                "student_id": str(student_id),
                "student_name": "Student One",
                "concept_id": concept_id,
                "concept_label": "Fractions",
            }

    monkeypatch.setattr("backend.endpoints.teachers._teacher_service", lambda db: _TeacherService())
    monkeypatch.setattr("backend.endpoints.teachers._analytics_service", lambda db: _AnalyticsService())

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    client = TestClient(app)

    list_resp = client.get("/api/v1/teachers/classes")
    create_resp = client.post(
        "/api/v1/teachers/classes",
        json={"name": "SSS2 Math A", "description": None, "subject": "math", "sss_level": "SSS2", "term": 1},
    )
    enroll_resp = client.post(
        f"/api/v1/teachers/classes/{class_id}/enroll",
        json={"student_ids": [str(student_id)]},
    )
    dashboard_resp = client.get(f"/api/v1/teachers/classes/{class_id}/dashboard")
    heatmap_resp = client.get(f"/api/v1/teachers/classes/{class_id}/heatmap")
    graph_resp = client.get(f"/api/v1/teachers/classes/{class_id}/graph-summary")
    playbook_resp = client.get(f"/api/v1/teachers/classes/{class_id}/graph-playbook")
    intervention_queue_resp = client.get(f"/api/v1/teachers/classes/{class_id}/intervention-queue")
    cluster_plan_resp = client.get(f"/api/v1/teachers/classes/{class_id}/next-cluster-plan")
    cluster_plan_export_resp = client.get(f"/api/v1/teachers/classes/{class_id}/next-cluster-plan/export")
    class_briefing_export_resp = client.get(f"/api/v1/teachers/classes/{class_id}/briefing/export")
    class_presentation_resp = client.get(f"/api/v1/teachers/classes/{class_id}/presentation")
    alerts_resp = client.get(f"/api/v1/teachers/classes/{class_id}/alerts")
    outcomes_resp = client.get(f"/api/v1/teachers/classes/{class_id}/intervention-outcomes")
    assignment_outcomes_resp = client.get(f"/api/v1/teachers/classes/{class_id}/assignment-outcomes")
    repeat_risk_resp = client.get(f"/api/v1/teachers/classes/{class_id}/repeat-risk")
    risk_matrix_resp = client.get(f"/api/v1/teachers/classes/{class_id}/risk-matrix")
    concept_compare_resp = client.get(
        f"/api/v1/teachers/classes/{class_id}/concept-compare?left_concept_id=math:sss2:t1:fractions&right_concept_id=math:sss2:t1:ratio"
    )
    concept_compare_export_resp = client.get(
        f"/api/v1/teachers/classes/{class_id}/concept-compare/export?left_concept_id=math:sss2:t1:fractions&right_concept_id=math:sss2:t1:ratio"
    )
    concept_students_resp = client.get(f"/api/v1/teachers/classes/{class_id}/concepts/math:sss2:t1:fractions/students")
    timeline_resp = client.get(f"/api/v1/teachers/classes/{class_id}/students/{student_id}/timeline")
    concept_trend_resp = client.get(f"/api/v1/teachers/classes/{class_id}/students/{student_id}/concepts/math:sss2:t1:fractions/trend")
    concept_export_resp = client.get(f"/api/v1/teachers/classes/{class_id}/students/{student_id}/concepts/math:sss2:t1:fractions/export")
    assignment_resp = client.post(
        "/api/v1/teachers/assignments",
        json={
            "class_id": str(class_id),
            "student_id": str(student_id),
            "assignment_type": "topic",
            "ref_id": "topic-1",
            "title": "Algebra Revision",
            "instructions": "Revise chapter 1",
            "subject": "math",
            "sss_level": "SSS2",
            "term": 1,
            "due_at": None,
        },
    )
    bulk_assignment_resp = client.post(
        "/api/v1/teachers/assignments/bulk",
        json={
            "class_id": str(class_id),
            "student_ids": [str(student_id)],
            "assignment_type": "revision",
            "ref_id": "fractions-repair-bulk",
            "title": "Fractions Repair Pack",
            "instructions": "Repair the prerequisite before reteaching Fractions.",
            "subject": "math",
            "sss_level": "SSS2",
            "term": 1,
            "due_at": None,
        },
    )
    intervention_resp = client.post(
        "/api/v1/teachers/interventions",
        json={
            "class_id": str(class_id),
            "student_id": str(student_id),
            "intervention_type": "note",
            "severity": "medium",
            "subject": "math",
            "sss_level": "SSS2",
            "term": 1,
            "notes": "Needs extra help",
            "action_plan": "Follow-up session",
        },
    )
    bulk_intervention_resp = client.post(
        "/api/v1/teachers/interventions/bulk",
        json={
            "class_id": str(class_id),
            "student_ids": [str(student_id)],
            "intervention_type": "support_plan",
            "severity": "high",
            "subject": "math",
            "sss_level": "SSS2",
            "term": 1,
            "notes": "Target repeated prerequisite blockers.",
            "action_plan": "Repair the blocker before reteaching the concept.",
        },
    )
    update_intervention_resp = client.patch(
        f"/api/v1/teachers/interventions/{uuid4()}",
        json={"status": "resolved"},
    )
    delete_resp = client.delete(f"/api/v1/teachers/classes/{class_id}/enroll/{student_id}")

    app.dependency_overrides.clear()

    assert list_resp.status_code == 200
    assert create_resp.status_code == 201
    assert enroll_resp.status_code == 200
    assert dashboard_resp.status_code == 200
    assert heatmap_resp.status_code == 200
    assert graph_resp.status_code == 200
    assert playbook_resp.status_code == 200
    assert intervention_queue_resp.status_code == 200
    assert cluster_plan_resp.status_code == 200
    assert cluster_plan_export_resp.status_code == 200
    assert class_briefing_export_resp.status_code == 200
    assert class_presentation_resp.status_code == 200
    assert alerts_resp.status_code == 200
    assert outcomes_resp.status_code == 200
    assert assignment_outcomes_resp.status_code == 200
    assert repeat_risk_resp.status_code == 200
    assert risk_matrix_resp.status_code == 200
    assert concept_compare_resp.status_code == 200
    assert concept_compare_export_resp.status_code == 200
    assert concept_students_resp.status_code == 200
    assert timeline_resp.status_code == 200
    assert concept_trend_resp.status_code == 200
    assert concept_export_resp.status_code == 200
    assert assignment_resp.status_code == 201
    assert bulk_assignment_resp.status_code == 201
    assert intervention_resp.status_code == 201
    assert bulk_intervention_resp.status_code == 201
    assert update_intervention_resp.status_code == 200
    assert delete_resp.status_code == 204


def test_teachers_endpoint_error_mapping(monkeypatch):
    teacher_id = uuid4()

    def _override_user():
        return SimpleNamespace(id=teacher_id, role="teacher")

    class _TeacherService:
        def create_class(self, *, teacher_id, payload):
            raise TeacherServiceConflictError("duplicate class")

        def list_classes(self, *, teacher_id):
            raise TeacherServiceUnauthorizedError("forbidden")

    class _AnalyticsService:
        pass

    monkeypatch.setattr("backend.endpoints.teachers._teacher_service", lambda db: _TeacherService())
    monkeypatch.setattr("backend.endpoints.teachers._analytics_service", lambda db: _AnalyticsService())

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    client = TestClient(app)

    list_resp = client.get("/api/v1/teachers/classes")
    create_resp = client.post(
        "/api/v1/teachers/classes",
        json={"name": "SSS1 English", "description": None, "subject": "english", "sss_level": "SSS1", "term": 1},
    )

    app.dependency_overrides.clear()
    assert list_resp.status_code == 403
    assert create_resp.status_code == 409
