from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from uuid import UUID

from backend.repositories.teacher_repo import TeacherRepository
from backend.schemas.teacher_schema import (
    CompletionDistributionOut,
    TeacherAlertOut,
    TeacherAlertsOut,
    TeacherAssignmentOutcomeOut,
    TeacherAssignmentOutcomeSummaryOut,
    TeacherClassDashboardOut,
    TeacherConceptStudentDrilldownOut,
    TeacherConceptStudentOut,
    TeacherConceptCompareOut,
    TeacherConceptCompareSelectionOut,
    TeacherConceptCompareStudentOut,
    TeacherConceptCompareStudentSideOut,
    TeacherConceptCompareSummaryOut,
    TeacherConceptTrendEventOut,
    TeacherConceptTrendSnapshotOut,
    TeacherExportOut,
    TeacherExportSectionOut,
    TeacherClassGraphOut,
    TeacherGraphEdgeOut,
    TeacherInterventionOutcomeOut,
    TeacherInterventionOutcomeSummaryOut,
    TeacherGraphPlaybookActionOut,
    TeacherGraphPlaybookOut,
    TeacherClassHeatmapOut,
    TeacherGraphConceptNodeOut,
    TeacherGraphMetricsOut,
    TeacherNextLessonClusterConceptOut,
    TeacherNextLessonClusterPlanOut,
    TeacherGraphSignalOut,
    TeacherInterventionQueueItemOut,
    TeacherInterventionQueueOut,
    TeacherHeatmapPointOut,
    TeacherRepeatRiskConceptOut,
    TeacherRepeatRiskStudentOut,
    TeacherRepeatRiskSummaryOut,
    TeacherPresentationOut,
    TeacherRiskMatrixCellOut,
    TeacherRiskMatrixConceptOut,
    TeacherRiskMatrixOut,
    TeacherRiskMatrixStudentOut,
    TeacherStudentTimelineOut,
    TeacherStudentConceptTrendOut,
    TeacherTimelineEventOut,
)
from backend.services.teacher_service import (
    TeacherServiceNotFoundError,
    TeacherServiceUnauthorizedError,
    TeacherServiceValidationError,
)


INACTIVITY_DAYS = 7
RAPID_DECLINE_DAYS = 14
RAPID_DECLINE_HIGH_THRESHOLD = -0.2
RAPID_DECLINE_MEDIUM_THRESHOLD = -0.1
LOW_MASTERY_THRESHOLD = 0.4
LOW_MASTERY_HIGH_SEVERITY = 0.3
GRAPH_MASTERY_THRESHOLD = 0.7
GRAPH_WEAK_THRESHOLD = 0.5
INTERVENTION_OUTCOME_WINDOW_DAYS = 21


class TeacherAnalyticsService:
    def __init__(self, repo: TeacherRepository):
        self.repo = repo

    @staticmethod
    def _readable_concept_label(concept_id: str | None, *, fallback: str | None = None) -> str:
        value = str(concept_id or "").strip()
        if not value:
            return str(fallback or "Concept").strip()
        token = value.rsplit(":", 1)[-1].strip()
        token = re.sub(r"-(\d+)$", "", token)
        token = re.sub(r"[_-]+", " ", token)
        token = re.sub(r"\s+", " ", token).strip()
        return token.title() if token else str(fallback or "Concept").strip()

    @staticmethod
    def _display_name(user, *, fallback_id: UUID) -> str:
        return (
            str(getattr(user, "display_name", "") or "").strip()
            or " ".join(
                part
                for part in [
                    str(getattr(user, "first_name", "") or "").strip(),
                    str(getattr(user, "last_name", "") or "").strip(),
                ]
                if part
            ).strip()
            or str(getattr(user, "email", "") or "").strip()
            or f"Student {str(fallback_id)[:8]}"
        )

    def _classify_concept_status(
        self,
        *,
        concept_score: float | None,
        blocking_prerequisite_labels: list[str],
    ) -> tuple[str, str]:
        if concept_score is None:
            return "unassessed", "Give this student a checkpoint on the selected concept."
        if blocking_prerequisite_labels:
            return "blocked", "Repair the blocking prerequisite before reteaching this concept."
        if concept_score < GRAPH_MASTERY_THRESHOLD:
            return "needs_attention", "Assign focused practice and a short checkpoint on this concept."
        return "mastered", "Use this student as a readiness signal for advancing the class."

    @staticmethod
    def _to_cluster_concept(node: TeacherGraphConceptNodeOut) -> TeacherNextLessonClusterConceptOut:
        return TeacherNextLessonClusterConceptOut(
            concept_id=node.concept_id,
            concept_label=node.concept_label,
            topic_id=node.topic_id,
            topic_title=node.topic_title,
            status=node.status,
            avg_score=node.avg_score,
            student_count=node.student_count,
            blocking_prerequisite_labels=list(node.blocking_prerequisite_labels or []),
            recommended_action=node.recommended_action,
        )

    @staticmethod
    def _slugify(value: str | None, *, fallback: str = "export") -> str:
        token = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
        return token or fallback

    @staticmethod
    def _format_percentage(value: float | None) -> str:
        if value is None:
            return "Unassessed"
        return f"{round(float(value) * 100)}%"

    @staticmethod
    def _build_markdown(*, title: str, subtitle: str, sections: list[TeacherExportSectionOut]) -> str:
        lines = [f"# {title}", "", subtitle]
        for section in sections:
            lines.extend(["", f"## {section.title}"])
            if not section.items:
                lines.append("- No data available.")
                continue
            lines.extend([f"- {item}" for item in section.items])
        return "\n".join(lines).strip()

    def _require_teacher_user(self, teacher_id: UUID):
        user = self.repo.get_user(teacher_id)
        if not user:
            raise TeacherServiceNotFoundError("Teacher user not found.")
        if not user.is_active:
            raise TeacherServiceUnauthorizedError("Teacher account is inactive.")
        if user.role not in {"teacher", "admin"}:
            raise TeacherServiceUnauthorizedError("Only teacher/admin role can access teacher analytics.")
        return user

    def _require_teacher_class(self, *, teacher_id: UUID, class_id: UUID):
        row = self.repo.get_teacher_class(teacher_id=teacher_id, class_id=class_id)
        if not row:
            raise TeacherServiceNotFoundError("Class not found for this teacher.")
        return row

    def get_class_dashboard(self, *, teacher_id: UUID, class_id: UUID) -> TeacherClassDashboardOut:
        self._require_teacher_user(teacher_id)
        teacher_class = self._require_teacher_class(teacher_id=teacher_id, class_id=class_id)

        student_ids = self.repo.get_active_student_ids(class_id=class_id)
        total_students = len(student_ids)
        if total_students == 0:
            return TeacherClassDashboardOut(
                class_id=class_id,
                total_students=0,
                active_students_7d=0,
                avg_study_time_seconds_7d=0,
                avg_mastery_score=0.0,
                completion_distribution=CompletionDistributionOut(
                    completed=0,
                    in_progress=0,
                    no_activity=0,
                ),
            )

        since = datetime.now(timezone.utc) - timedelta(days=INACTIVITY_DAYS)
        activity_stats = self.repo.get_recent_activity_stats(
            class_id=class_id,
            subject=teacher_class.subject,
            term=teacher_class.term,
            since=since,
        )

        active_students_7d = sum(1 for student_id in student_ids if activity_stats.get(student_id, {}).get("event_count", 0) > 0)
        total_duration = sum(activity_stats.get(student_id, {}).get("duration_seconds", 0) for student_id in student_ids)
        avg_study_time = int(total_duration / total_students) if total_students else 0

        mastery_map = self.repo.get_avg_mastery_by_student(
            class_id=class_id,
            subject=teacher_class.subject,
            term=teacher_class.term,
        )
        avg_mastery_score = round(sum(mastery_map.values()) / len(mastery_map), 4) if mastery_map else 0.0

        completed = 0
        in_progress = 0
        no_activity = 0
        for student_id in student_ids:
            stats = activity_stats.get(student_id)
            if not stats or stats["event_count"] == 0:
                no_activity += 1
                continue
            if stats["quiz_submitted_count"] > 0 and stats["lesson_viewed_count"] > 0:
                completed += 1
            else:
                in_progress += 1

        return TeacherClassDashboardOut(
            class_id=class_id,
            total_students=total_students,
            active_students_7d=active_students_7d,
            avg_study_time_seconds_7d=avg_study_time,
            avg_mastery_score=avg_mastery_score,
            completion_distribution=CompletionDistributionOut(
                completed=completed,
                in_progress=in_progress,
                no_activity=no_activity,
            ),
        )

    def get_class_heatmap(self, *, teacher_id: UUID, class_id: UUID) -> TeacherClassHeatmapOut:
        self._require_teacher_user(teacher_id)
        teacher_class = self._require_teacher_class(teacher_id=teacher_id, class_id=class_id)

        points = self.repo.get_heatmap_points(
            class_id=class_id,
            subject=teacher_class.subject,
            term=teacher_class.term,
        )
        return TeacherClassHeatmapOut(
            class_id=class_id,
            points=[
                TeacherHeatmapPointOut(
                    concept_id=row["concept_id"],
                    avg_score=round(float(row["avg_score"]), 4),
                    student_count=int(row["student_count"]),
                )
                for row in points
            ],
        )

    def get_class_graph_summary(self, *, teacher_id: UUID, class_id: UUID) -> TeacherClassGraphOut:
        self._require_teacher_user(teacher_id)
        teacher_class = self._require_teacher_class(teacher_id=teacher_id, class_id=class_id)

        heatmap_rows = self.repo.get_heatmap_points(
            class_id=class_id,
            subject=teacher_class.subject,
            term=teacher_class.term,
        )
        scope_rows = self.repo.get_scope_concept_rows(
            subject=teacher_class.subject,
            sss_level=teacher_class.sss_level,
            term=teacher_class.term,
        )

        heatmap_map = {
            str(row["concept_id"]): {
                "avg_score": float(row["avg_score"]),
                "student_count": int(row["student_count"]),
            }
            for row in heatmap_rows
        }
        concept_rows_by_id = {
            str(row["concept_id"]): row
            for row in scope_rows
            if str(row.get("concept_id") or "").strip()
        }

        nodes: list[TeacherGraphConceptNodeOut] = []
        edges: list[TeacherGraphEdgeOut] = []
        for concept_id, row in concept_rows_by_id.items():
            stat = heatmap_map.get(concept_id, {"avg_score": 0.0, "student_count": 0})
            prereq_ids = [item for item in list(row.get("prereq_concept_ids") or []) if item]
            blocking_prereqs = [
                prereq_id
                for prereq_id in prereq_ids
                if float(heatmap_map.get(prereq_id, {"avg_score": 0.0})["avg_score"]) < GRAPH_MASTERY_THRESHOLD
            ]
            avg_score = float(stat["avg_score"])
            student_count = int(stat["student_count"])

            if student_count <= 0:
                status = "unassessed"
                recommended_action = "Assign a checkpoint or quiz so this concept enters the graph."
            elif blocking_prereqs:
                status = "blocked"
                recommended_action = "Repair the weakest prerequisite before pushing this concept."
            elif avg_score < GRAPH_MASTERY_THRESHOLD:
                status = "needs_attention"
                recommended_action = "Strengthen this concept cluster with guided practice."
            else:
                status = "mastered"
                recommended_action = "Use this concept to unlock the next cluster."

            nodes.append(
                TeacherGraphConceptNodeOut(
                    concept_id=concept_id,
                    concept_label=self._readable_concept_label(concept_id, fallback=row.get("topic_title")),
                    topic_id=row.get("topic_id"),
                    topic_title=row.get("topic_title"),
                    avg_score=round(avg_score, 4),
                    student_count=student_count,
                    status=status,
                    prerequisite_labels=[
                        self._readable_concept_label(prereq_id, fallback=concept_rows_by_id.get(prereq_id, {}).get("topic_title"))
                        for prereq_id in prereq_ids
                    ],
                    blocking_prerequisite_labels=[
                        self._readable_concept_label(prereq_id, fallback=concept_rows_by_id.get(prereq_id, {}).get("topic_title"))
                        for prereq_id in blocking_prereqs
                    ],
                    recommended_action=recommended_action,
                )
            )
            for prereq_id in prereq_ids:
                if prereq_id not in concept_rows_by_id:
                    continue
                edges.append(
                    TeacherGraphEdgeOut(
                        source_concept_id=prereq_id,
                        target_concept_id=concept_id,
                        status="blocked" if prereq_id in blocking_prereqs else "ready",
                    )
                )

        blocked_nodes = sorted(
            [node for node in nodes if node.status == "blocked"],
            key=lambda item: (item.avg_score, item.concept_label),
        )
        weak_nodes = sorted(
            [node for node in nodes if node.status == "needs_attention"],
            key=lambda item: (item.avg_score, item.concept_label),
        )
        mastered_nodes = sorted(
            [node for node in nodes if node.status == "mastered"],
            key=lambda item: (-item.avg_score, item.concept_label),
        )
        unassessed_nodes = sorted(
            [node for node in nodes if node.status == "unassessed"],
            key=lambda item: (item.concept_label, item.topic_title or ""),
        )

        metrics = TeacherGraphMetricsOut(
            mapped_concepts=len(nodes),
            blocked_concepts=len(blocked_nodes),
            weak_concepts=len(weak_nodes),
            mastered_concepts=len(mastered_nodes),
            unassessed_concepts=len(unassessed_nodes),
        )

        if blocked_nodes:
            focus = blocked_nodes[0]
            graph_signal = TeacherGraphSignalOut(
                status="repair_prerequisite",
                headline=f"Repair {focus.blocking_prerequisite_labels[0]} before pushing {focus.concept_label}.",
                supporting_reason="The class is hitting a prerequisite barrier in the current graph scope.",
                focus_concept_label=focus.concept_label,
                blocking_prerequisite_label=focus.blocking_prerequisite_labels[0] if focus.blocking_prerequisite_labels else None,
                recommended_action="Revisit the blocker and assign a prerequisite-focused drill.",
            )
        elif weak_nodes:
            focus = weak_nodes[0]
            graph_signal = TeacherGraphSignalOut(
                status="strengthen_cluster",
                headline=f"Strengthen {focus.concept_label} before unlocking the next concept cluster.",
                supporting_reason="Prerequisites are mostly in place, but the active concept cluster is still below mastery.",
                focus_concept_label=focus.concept_label,
                blocking_prerequisite_label=None,
                recommended_action="Run a focused checkpoint or quiz on this concept.",
            )
        elif mastered_nodes:
            focus = mastered_nodes[0]
            graph_signal = TeacherGraphSignalOut(
                status="advance_class",
                headline=f"The class is ready to push beyond {focus.concept_label}.",
                supporting_reason="Current concept mastery is healthy enough to unlock the next lesson cluster.",
                focus_concept_label=focus.concept_label,
                blocking_prerequisite_label=None,
                recommended_action="Advance the class to the next mapped lesson and monitor the new weak node.",
            )
        else:
            graph_signal = TeacherGraphSignalOut(
                status="insufficient_data",
                headline="The class graph is still sparse.",
                supporting_reason="There is not enough mastery evidence yet to recommend the next graph move confidently.",
                focus_concept_label=None,
                blocking_prerequisite_label=None,
                recommended_action="Collect more quiz or tutor checkpoint evidence for this scope.",
            )

        return TeacherClassGraphOut(
            class_id=class_id,
            metrics=metrics,
            graph_signal=graph_signal,
            nodes=(blocked_nodes + weak_nodes + mastered_nodes + unassessed_nodes),
            edges=sorted(edges, key=lambda item: (item.status, item.target_concept_id, item.source_concept_id)),
            weakest_blockers=(blocked_nodes[:6] or weak_nodes[:6] or unassessed_nodes[:6]),
            ready_to_push=mastered_nodes[:6],
        )

    def get_class_alerts(self, *, teacher_id: UUID, class_id: UUID) -> TeacherAlertsOut:
        self._require_teacher_user(teacher_id)
        teacher_class = self._require_teacher_class(teacher_id=teacher_id, class_id=class_id)
        now = datetime.now(timezone.utc)

        student_ids = self.repo.get_active_student_ids(class_id=class_id)
        if not student_ids:
            return TeacherAlertsOut(class_id=class_id, alerts=[])

        alerts: dict[tuple[str, UUID], TeacherAlertOut] = {}

        inactivity_since = now - timedelta(days=INACTIVITY_DAYS)
        activity_stats = self.repo.get_recent_activity_stats(
            class_id=class_id,
            subject=teacher_class.subject,
            term=teacher_class.term,
            since=inactivity_since,
        )
        for student_id in student_ids:
            if activity_stats.get(student_id, {}).get("event_count", 0) == 0:
                alerts[("inactivity", student_id)] = TeacherAlertOut(
                    alert_type="inactivity",
                    severity="medium",
                    student_id=student_id,
                    message=f"No learning activity in the last {INACTIVITY_DAYS} days.",
                    generated_at=now,
                )

        decline_since = now - timedelta(days=RAPID_DECLINE_DAYS)
        decline_totals = self.repo.get_negative_mastery_delta_by_student(
            class_id=class_id,
            subject=teacher_class.subject,
            term=teacher_class.term,
            since=decline_since,
        )
        for student_id, total_delta in decline_totals.items():
            if total_delta <= RAPID_DECLINE_HIGH_THRESHOLD:
                severity = "high"
            elif total_delta <= RAPID_DECLINE_MEDIUM_THRESHOLD:
                severity = "medium"
            else:
                continue
            alerts[("rapid_decline", student_id)] = TeacherAlertOut(
                alert_type="rapid_decline",
                severity=severity,
                student_id=student_id,
                message=f"Mastery trend declined by {round(total_delta, 3)} in the last {RAPID_DECLINE_DAYS} days.",
                generated_at=now,
            )

        low_mastery = self.repo.get_low_mastery_students(
            class_id=class_id,
            subject=teacher_class.subject,
            term=teacher_class.term,
            threshold=LOW_MASTERY_THRESHOLD,
        )
        for student_id, avg_score in low_mastery.items():
            severity = "high" if avg_score < LOW_MASTERY_HIGH_SEVERITY else "medium"
            alerts[("prereq_failure", student_id)] = TeacherAlertOut(
                alert_type="prereq_failure",
                severity=severity,
                student_id=student_id,
                message=f"Low foundational mastery detected (avg score {round(avg_score, 3)}).",
                generated_at=now,
            )

        sorted_alerts = sorted(
            alerts.values(),
            key=lambda row: (row.severity == "high", row.generated_at),
            reverse=True,
        )
        return TeacherAlertsOut(class_id=class_id, alerts=sorted_alerts)

    def get_class_graph_playbook(self, *, teacher_id: UUID, class_id: UUID) -> TeacherGraphPlaybookOut:
        graph = self.get_class_graph_summary(teacher_id=teacher_id, class_id=class_id)
        alerts = self.get_class_alerts(teacher_id=teacher_id, class_id=class_id)

        actions: list[TeacherGraphPlaybookActionOut] = []
        focus_blocker = graph.weakest_blockers[0] if graph.weakest_blockers else None
        if focus_blocker:
            actions.append(
                TeacherGraphPlaybookActionOut(
                    action_type="repair_prerequisite",
                    title=f"Repair {focus_blocker.concept_label} through its blocker first",
                    summary=(
                        f"Start with {focus_blocker.blocking_prerequisite_labels[0]} before reteaching {focus_blocker.concept_label}."
                        if focus_blocker.blocking_prerequisite_labels
                        else f"Reinforce the prerequisite path feeding into {focus_blocker.concept_label}."
                    ),
                    severity="high" if focus_blocker.status == "blocked" else "medium",
                    target_concept_id=focus_blocker.concept_id,
                    target_concept_label=focus_blocker.concept_label,
                    target_topic_id=focus_blocker.topic_id,
                    target_topic_title=focus_blocker.topic_title,
                    suggested_assignment_type="revision",
                    suggested_intervention_type="support_plan",
                    affected_student_count=focus_blocker.student_count,
                )
            )

        weak_focus = next((node for node in graph.nodes if node.status == "needs_attention"), None)
        if weak_focus:
            actions.append(
                TeacherGraphPlaybookActionOut(
                    action_type="run_checkpoint",
                    title=f"Run a focused checkpoint on {weak_focus.concept_label}",
                    summary="The class has the prerequisites, but mastery on this concept cluster is still below target.",
                    severity="medium",
                    target_concept_id=weak_focus.concept_id,
                    target_concept_label=weak_focus.concept_label,
                    target_topic_id=weak_focus.topic_id,
                    target_topic_title=weak_focus.topic_title,
                    suggested_assignment_type="quiz",
                    suggested_intervention_type="note",
                    affected_student_count=weak_focus.student_count,
                )
            )

        advance_focus = graph.ready_to_push[0] if graph.ready_to_push else None
        if advance_focus:
            actions.append(
                TeacherGraphPlaybookActionOut(
                    action_type="advance_cluster",
                    title=f"Advance from {advance_focus.concept_label} into the next lesson cluster",
                    summary="This concept is strong enough to anchor the next class move without overloading weak prerequisites.",
                    severity="low",
                    target_concept_id=advance_focus.concept_id,
                    target_concept_label=advance_focus.concept_label,
                    target_topic_id=advance_focus.topic_id,
                    target_topic_title=advance_focus.topic_title,
                    suggested_assignment_type="topic",
                    suggested_intervention_type="note",
                    affected_student_count=advance_focus.student_count,
                )
            )

        if alerts.alerts:
            high_count = sum(1 for alert in alerts.alerts if alert.severity == "high")
            medium_count = sum(1 for alert in alerts.alerts if alert.severity == "medium")
            focus_node = next(
                (node for node in graph.nodes if node.concept_label == graph.graph_signal.focus_concept_label),
                None,
            )
            actions.append(
                TeacherGraphPlaybookActionOut(
                    action_type="support_students",
                    title="Open targeted support for at-risk students",
                    summary=f"{high_count} high-severity and {medium_count} medium-severity alerts are active in this class.",
                    severity="high" if high_count > 0 else "medium",
                    target_concept_id=focus_node.concept_id if focus_node else None,
                    target_concept_label=graph.graph_signal.focus_concept_label,
                    suggested_assignment_type="revision",
                    suggested_intervention_type="support_plan",
                    affected_student_count=len({alert.student_id for alert in alerts.alerts}),
                )
            )

        return TeacherGraphPlaybookOut(class_id=class_id, actions=actions)

    def get_intervention_queue(self, *, teacher_id: UUID, class_id: UUID) -> TeacherInterventionQueueOut:
        graph = self.get_class_graph_summary(teacher_id=teacher_id, class_id=class_id)
        repeat_risk = self.get_repeat_risk_summary(teacher_id=teacher_id, class_id=class_id)

        items: list[TeacherInterventionQueueItemOut] = []
        seen: set[tuple[str, str | None, str | None]] = set()

        def _append_item(item: TeacherInterventionQueueItemOut) -> None:
            key = (item.recommendation_type, str(item.student_id) if item.student_id else None, str(item.concept_id or ""))
            if key in seen:
                return
            seen.add(key)
            items.append(item)

        for node in graph.weakest_blockers[:3]:
            drilldown = self.get_concept_student_drilldown(
                teacher_id=teacher_id,
                class_id=class_id,
                concept_id=node.concept_id,
            )
            for student in drilldown.students[:2]:
                if student.status not in {"blocked", "needs_attention"}:
                    continue
                recommendation_type = "repair_prerequisite" if student.status == "blocked" else "reteach_concept"
                priority = "urgent" if student.status == "blocked" else "high"
                headline = (
                    f"Repair {student.blocking_prerequisite_labels[0]} before reteaching {drilldown.concept_label} for {student.student_name}."
                    if student.blocking_prerequisite_labels
                    else f"Reteach {drilldown.concept_label} for {student.student_name} with a short checkpoint."
                )
                _append_item(
                    TeacherInterventionQueueItemOut(
                        queue_id=f"{recommendation_type}:{student.student_id}:{drilldown.concept_id}",
                        priority=priority,
                        recommendation_type=recommendation_type,
                        headline=headline,
                        rationale=student.recommended_action,
                        student_id=student.student_id,
                        student_name=student.student_name,
                        concept_id=drilldown.concept_id,
                        concept_label=drilldown.concept_label,
                        topic_id=drilldown.topic_id,
                        topic_title=drilldown.topic_title,
                        blocking_prerequisite_labels=list(student.blocking_prerequisite_labels or []),
                        suggested_assignment_type="revision",
                        suggested_intervention_type="support_plan",
                    )
                )

        for student in repeat_risk.students[:4]:
            focus_concept = student.driving_concepts[0] if student.driving_concepts else None
            if not focus_concept:
                continue
            _append_item(
                TeacherInterventionQueueItemOut(
                    queue_id=f"repeat_risk:{student.student_id}:{focus_concept.concept_id}",
                    priority="urgent" if student.risk_status == "repeat_blocker" else "high",
                    recommendation_type="repeat_risk_support",
                    headline=f"Stabilize {focus_concept.concept_label} for {student.student_name} before the weakness spreads further.",
                    rationale=student.recommended_action,
                    student_id=student.student_id,
                    student_name=student.student_name,
                    concept_id=focus_concept.concept_id,
                    concept_label=focus_concept.concept_label,
                    topic_id=focus_concept.topic_id,
                    topic_title=focus_concept.topic_title,
                    blocking_prerequisite_labels=list(focus_concept.blocking_prerequisite_labels or []),
                    suggested_assignment_type="revision",
                    suggested_intervention_type="support_plan",
                )
            )

        if not items:
            focus = graph.weakest_blockers[0] if graph.weakest_blockers else (graph.nodes[0] if graph.nodes else None)
            if focus:
                _append_item(
                    TeacherInterventionQueueItemOut(
                        queue_id=f"collect_evidence::{focus.concept_id}",
                        priority="medium",
                        recommendation_type="collect_evidence",
                        headline=f"Collect stronger evidence on {focus.concept_label} before choosing a narrower intervention.",
                        rationale=focus.recommended_action,
                        concept_id=focus.concept_id,
                        concept_label=focus.concept_label,
                        topic_id=focus.topic_id,
                        topic_title=focus.topic_title,
                        blocking_prerequisite_labels=list(focus.blocking_prerequisite_labels or []),
                        suggested_assignment_type="quiz",
                        suggested_intervention_type=None,
                    )
                )

        items.sort(
            key=lambda item: (
                {"urgent": 0, "high": 1, "medium": 2}[item.priority],
                item.student_name or "",
                item.concept_label or "",
            )
        )

        return TeacherInterventionQueueOut(
            class_id=class_id,
            total_items=len(items),
            urgent_items=sum(1 for item in items if item.priority == "urgent"),
            student_targeted_items=sum(1 for item in items if item.student_id is not None),
            class_scope_items=sum(1 for item in items if item.student_id is None),
            items=items[:10],
        )

    def get_next_lesson_cluster_plan(self, *, teacher_id: UUID, class_id: UUID) -> TeacherNextLessonClusterPlanOut:
        graph = self.get_class_graph_summary(teacher_id=teacher_id, class_id=class_id)
        playbook = self.get_class_graph_playbook(teacher_id=teacher_id, class_id=class_id)

        nodes_by_id = {node.concept_id: node for node in graph.nodes}
        inbound_edges: dict[str, list[TeacherGraphEdgeOut]] = {}
        for edge in graph.edges:
            inbound_edges.setdefault(edge.target_concept_id, []).append(edge)

        blocked_nodes = [node for node in graph.nodes if node.status == "blocked"]
        weak_nodes = [node for node in graph.nodes if node.status == "needs_attention"]
        mastered_nodes = [node for node in graph.nodes if node.status == "mastered"]
        unassessed_nodes = [node for node in graph.nodes if node.status == "unassessed"]

        if blocked_nodes:
            repair_nodes: list[TeacherGraphConceptNodeOut] = []
            seen_ids: set[str] = set()
            for blocker in blocked_nodes[:3]:
                for edge in inbound_edges.get(blocker.concept_id, []):
                    if edge.status != "blocked":
                        continue
                    source = nodes_by_id.get(edge.source_concept_id)
                    if not source or source.concept_id in seen_ids:
                        continue
                    repair_nodes.append(source)
                    seen_ids.add(source.concept_id)

            repair_first = [self._to_cluster_concept(node) for node in repair_nodes[:3]]
            teach_next = [self._to_cluster_concept(node) for node in blocked_nodes[:3]]
            watchlist = [self._to_cluster_concept(node) for node in weak_nodes[:3]]
            top_blocker = blocked_nodes[0]
            repair_label = (
                repair_first[0].concept_label
                if repair_first
                else (top_blocker.blocking_prerequisite_labels[0] if top_blocker.blocking_prerequisite_labels else "the prerequisite path")
            )
            return TeacherNextLessonClusterPlanOut(
                class_id=class_id,
                plan_status="repair_first",
                headline=f"Repair {repair_label} before reteaching {top_blocker.concept_label}.",
                rationale="The next lesson cluster is not teachable yet because prerequisite mastery is still blocking the class graph.",
                repair_first=repair_first,
                teach_next=teach_next,
                watchlist=watchlist,
                suggested_actions=[
                    action
                    for action in playbook.actions
                    if action.action_type in {"repair_prerequisite", "run_checkpoint", "support_students"}
                ][:3],
            )

        if weak_nodes:
            watchlist: list[TeacherNextLessonClusterConceptOut] = []
            for node in unassessed_nodes:
                incoming = inbound_edges.get(node.concept_id, [])
                if incoming and any(edge.status == "blocked" for edge in incoming):
                    continue
                watchlist.append(self._to_cluster_concept(node))
                if len(watchlist) >= 3:
                    break
            focus = weak_nodes[0]
            return TeacherNextLessonClusterPlanOut(
                class_id=class_id,
                plan_status="stabilize_cluster",
                headline=f"Stabilize {focus.concept_label} before moving the class forward.",
                rationale="Prerequisites are mostly in place, but the current concept cluster is still below the mastery bar for a confident advance.",
                repair_first=[],
                teach_next=[self._to_cluster_concept(node) for node in weak_nodes[:3]],
                watchlist=watchlist,
                suggested_actions=[
                    action
                    for action in playbook.actions
                    if action.action_type in {"run_checkpoint", "support_students", "advance_cluster"}
                ][:3],
            )

        unlocked_next: list[TeacherGraphConceptNodeOut] = []
        for node in unassessed_nodes:
            incoming = inbound_edges.get(node.concept_id, [])
            if any(edge.status == "blocked" for edge in incoming):
                continue
            unlocked_next.append(node)

        if unlocked_next or mastered_nodes:
            teach_next_nodes = unlocked_next[:3] or mastered_nodes[:1]
            watchlist_nodes = unlocked_next[3:6] or weak_nodes[:3]
            focus = teach_next_nodes[0]
            return TeacherNextLessonClusterPlanOut(
                class_id=class_id,
                plan_status="advance_cluster",
                headline=f"Advance into {focus.concept_label} as the next lesson cluster.",
                rationale="The class graph shows enough readiness on the current prerequisite chain to move into the next mapped lesson cluster.",
                repair_first=[],
                teach_next=[self._to_cluster_concept(node) for node in teach_next_nodes],
                watchlist=[self._to_cluster_concept(node) for node in watchlist_nodes],
                suggested_actions=[
                    action
                    for action in playbook.actions
                    if action.action_type in {"advance_cluster", "run_checkpoint", "support_students"}
                ][:3],
            )

        return TeacherNextLessonClusterPlanOut(
            class_id=class_id,
            plan_status="collect_evidence",
            headline="Collect more evidence before locking the next lesson cluster.",
            rationale="The class graph is still too sparse to recommend the next cluster confidently. More checkpoints or quiz evidence are needed first.",
            repair_first=[],
            teach_next=[],
            watchlist=[],
            suggested_actions=playbook.actions[:2],
        )

    def get_next_cluster_plan_export(self, *, teacher_id: UUID, class_id: UUID) -> TeacherExportOut:
        teacher_class = self._require_teacher_class(teacher_id=teacher_id, class_id=class_id)
        plan = self.get_next_lesson_cluster_plan(teacher_id=teacher_id, class_id=class_id)
        graph = self.get_class_graph_summary(teacher_id=teacher_id, class_id=class_id)

        sections = [
            TeacherExportSectionOut(
                title="Planning headline",
                items=[
                    plan.headline,
                    plan.rationale,
                    f"Graph signal: {graph.graph_signal.headline}",
                ],
            ),
            TeacherExportSectionOut(
                title="Repair first",
                items=[
                    f"{item.concept_label} ({item.topic_title or 'Mapped concept node'}): {item.recommended_action}"
                    for item in plan.repair_first
                ],
            ),
            TeacherExportSectionOut(
                title="Teach next",
                items=[
                    f"{item.concept_label} ({item.topic_title or 'Mapped concept node'}): {item.recommended_action}"
                    for item in plan.teach_next
                ],
            ),
            TeacherExportSectionOut(
                title="Watchlist",
                items=[
                    f"{item.concept_label} ({item.topic_title or 'Mapped concept node'}): {item.recommended_action}"
                    for item in plan.watchlist
                ],
            ),
            TeacherExportSectionOut(
                title="Suggested actions",
                items=[
                    f"{action.title}: {action.summary}"
                    for action in plan.suggested_actions
                ],
            ),
        ]
        subtitle = (
            f"{teacher_class.name} • {teacher_class.subject.title()} • {teacher_class.sss_level} Term {teacher_class.term}. "
            f"Plan status: {plan.plan_status.replace('_', ' ')}."
        )
        return TeacherExportOut(
            export_kind="next_cluster_plan",
            class_id=class_id,
            class_name=teacher_class.name,
            subject=teacher_class.subject,
            sss_level=teacher_class.sss_level,
            term=teacher_class.term,
            title=f"{teacher_class.name} cluster plan",
            subtitle=subtitle,
            generated_at=datetime.now(timezone.utc),
            file_name=(
                f"{self._slugify(teacher_class.name, fallback='class')}-"
                f"term{teacher_class.term}-next-cluster-plan.md"
            ),
            share_text=f"{plan.headline} {plan.rationale}",
            markdown=self._build_markdown(
                title=f"{teacher_class.name} cluster plan",
                subtitle=subtitle,
                sections=sections,
            ),
            sections=sections,
        )

    def get_class_briefing_export(self, *, teacher_id: UUID, class_id: UUID) -> TeacherExportOut:
        teacher_class = self._require_teacher_class(teacher_id=teacher_id, class_id=class_id)
        graph = self.get_class_graph_summary(teacher_id=teacher_id, class_id=class_id)
        plan = self.get_next_lesson_cluster_plan(teacher_id=teacher_id, class_id=class_id)
        repeat_risk = self.get_repeat_risk_summary(teacher_id=teacher_id, class_id=class_id)
        assignment_outcomes = self.get_assignment_outcomes(teacher_id=teacher_id, class_id=class_id)
        intervention_outcomes = self.get_intervention_outcomes(teacher_id=teacher_id, class_id=class_id)
        alerts = self.get_class_alerts(teacher_id=teacher_id, class_id=class_id)

        sections = [
            TeacherExportSectionOut(
                title="Graph signal",
                items=[
                    graph.graph_signal.headline,
                    graph.graph_signal.supporting_reason,
                    f"Recommended action: {graph.graph_signal.recommended_action}",
                ],
            ),
            TeacherExportSectionOut(
                title="Top blockers",
                items=[
                    f"{node.concept_label}: {node.recommended_action}"
                    for node in graph.weakest_blockers[:4]
                ],
            ),
            TeacherExportSectionOut(
                title="Next lesson cluster plan",
                items=[
                    plan.headline,
                    plan.rationale,
                    *[
                        f"Teach next: {item.concept_label} - {item.recommended_action}"
                        for item in plan.teach_next[:3]
                    ],
                ],
            ),
            TeacherExportSectionOut(
                title="At-risk students",
                items=[
                    f"{student.student_name}: {student.recommended_action}"
                    for student in repeat_risk.students[:5]
                ],
            ),
            TeacherExportSectionOut(
                title="Outcome snapshot",
                items=[
                    (
                        f"Assignments - improving: {assignment_outcomes.improving_assignments}, "
                        f"declining: {assignment_outcomes.declining_assignments}, "
                        f"no evidence: {assignment_outcomes.no_evidence_assignments}"
                    ),
                    (
                        f"Interventions - improving: {intervention_outcomes.improving_interventions}, "
                        f"declining: {intervention_outcomes.declining_interventions}, "
                        f"no evidence: {intervention_outcomes.no_evidence_interventions}"
                    ),
                    f"Active alerts: {len(alerts.alerts)}",
                ],
            ),
        ]

        subtitle = (
            f"{teacher_class.name} • {teacher_class.subject.title()} • {teacher_class.sss_level} Term {teacher_class.term}. "
            f"Graph-backed class briefing."
        )
        return TeacherExportOut(
            export_kind="class_briefing",
            class_id=class_id,
            class_name=teacher_class.name,
            subject=teacher_class.subject,
            sss_level=teacher_class.sss_level,
            term=teacher_class.term,
            title=f"{teacher_class.name} class briefing",
            subtitle=subtitle,
            generated_at=datetime.now(timezone.utc),
            file_name=f"{self._slugify(teacher_class.name, fallback='class')}-class-briefing.md",
            share_text=(
                f"{graph.graph_signal.headline} "
                f"{len(repeat_risk.students)} students are currently driving repeated graph risk."
            ),
            markdown=self._build_markdown(
                title=f"{teacher_class.name} class briefing",
                subtitle=subtitle,
                sections=sections,
            ),
            sections=sections,
        )

    def get_class_presentation(self, *, teacher_id: UUID, class_id: UUID) -> TeacherPresentationOut:
        teacher_class = self._require_teacher_class(teacher_id=teacher_id, class_id=class_id)
        return TeacherPresentationOut(
            class_id=class_id,
            class_name=teacher_class.name,
            subject=teacher_class.subject,
            sss_level=teacher_class.sss_level,
            term=teacher_class.term,
            generated_at=datetime.now(timezone.utc),
            dashboard=self.get_class_dashboard(teacher_id=teacher_id, class_id=class_id),
            graph_summary=self.get_class_graph_summary(teacher_id=teacher_id, class_id=class_id),
            intervention_queue=self.get_intervention_queue(teacher_id=teacher_id, class_id=class_id),
            next_cluster_plan=self.get_next_lesson_cluster_plan(teacher_id=teacher_id, class_id=class_id),
            assignment_outcomes=self.get_assignment_outcomes(teacher_id=teacher_id, class_id=class_id),
            intervention_outcomes=self.get_intervention_outcomes(teacher_id=teacher_id, class_id=class_id),
            briefing=self.get_class_briefing_export(teacher_id=teacher_id, class_id=class_id),
        )

    def get_concept_student_drilldown(
        self,
        *,
        teacher_id: UUID,
        class_id: UUID,
        concept_id: str,
    ) -> TeacherConceptStudentDrilldownOut:
        self._require_teacher_user(teacher_id)
        teacher_class = self._require_teacher_class(teacher_id=teacher_id, class_id=class_id)

        scope_rows = self.repo.get_scope_concept_rows(
            subject=teacher_class.subject,
            sss_level=teacher_class.sss_level,
            term=teacher_class.term,
        )
        concept_rows_by_id = {
            str(row["concept_id"]): row
            for row in scope_rows
            if str(row.get("concept_id") or "").strip()
        }
        target = concept_rows_by_id.get(concept_id)
        if not target:
            raise TeacherServiceNotFoundError("Concept is not mapped in this class scope.")

        prereq_ids = [item for item in list(target.get("prereq_concept_ids") or []) if item]
        concept_rows = self.repo.get_student_concept_rows(
            class_id=class_id,
            subject=teacher_class.subject,
            term=teacher_class.term,
            concept_ids=[concept_id, *prereq_ids],
        )
        student_ids = self.repo.get_active_student_ids(class_id=class_id)
        users = self.repo.get_users_by_ids(student_ids)
        activity_stats = self.repo.get_recent_activity_stats(
            class_id=class_id,
            subject=teacher_class.subject,
            term=teacher_class.term,
            since=datetime.now(timezone.utc) - timedelta(days=INACTIVITY_DAYS),
        )
        overall_scores = self.repo.get_avg_mastery_by_student(
            class_id=class_id,
            subject=teacher_class.subject,
            term=teacher_class.term,
        )

        scores_by_student: dict[UUID, dict[str, dict]] = {}
        for row in concept_rows:
            bucket = scores_by_student.setdefault(row["student_id"], {})
            bucket[row["concept_id"]] = row

        students: list[TeacherConceptStudentOut] = []
        for student_id in student_ids:
            user = users.get(student_id)
            concept_row = scores_by_student.get(student_id, {}).get(concept_id)
            concept_score = float(concept_row["mastery_score"]) if concept_row else None
            blocking_prereqs = []
            for prereq_id in prereq_ids:
                prereq_row = scores_by_student.get(student_id, {}).get(prereq_id)
                prereq_score = float(prereq_row["mastery_score"]) if prereq_row else 0.0
                if prereq_score < GRAPH_MASTERY_THRESHOLD:
                    blocking_prereqs.append(
                        self._readable_concept_label(prereq_id, fallback=concept_rows_by_id.get(prereq_id, {}).get("topic_title"))
                    )

            status, recommended_action = self._classify_concept_status(
                concept_score=concept_score,
                blocking_prerequisite_labels=blocking_prereqs,
            )
            display_name = self._display_name(user, fallback_id=student_id)

            stats = activity_stats.get(student_id, {})
            students.append(
                TeacherConceptStudentOut(
                    student_id=student_id,
                    student_name=display_name,
                    concept_score=round(concept_score, 4) if concept_score is not None else None,
                    overall_mastery_score=round(float(overall_scores.get(student_id, 0.0)), 4) if student_id in overall_scores else None,
                    status=status,
                    blocking_prerequisite_labels=blocking_prereqs,
                    recent_activity_count_7d=int(stats.get("event_count", 0)),
                    recent_study_time_seconds_7d=int(stats.get("duration_seconds", 0)),
                    recommended_action=recommended_action,
                    last_evaluated_at=concept_row["last_evaluated_at"] if concept_row else None,
                )
            )

        students.sort(
            key=lambda item: (
                {"blocked": 0, "needs_attention": 1, "unassessed": 2, "mastered": 3}[item.status],
                1.1 if item.concept_score is None else item.concept_score,
                item.student_name.lower(),
            )
        )

        return TeacherConceptStudentDrilldownOut(
            class_id=class_id,
            concept_id=concept_id,
            concept_label=self._readable_concept_label(concept_id, fallback=target.get("topic_title")),
            topic_id=target.get("topic_id"),
            topic_title=target.get("topic_title"),
            students=students,
        )

    def get_student_timeline(
        self,
        *,
        teacher_id: UUID,
        class_id: UUID,
        student_id: UUID,
        limit: int = 50,
    ) -> TeacherStudentTimelineOut:
        self._require_teacher_user(teacher_id)
        self._require_teacher_class(teacher_id=teacher_id, class_id=class_id)

        student_user = self.repo.get_user(student_id)
        if not student_user or student_user.role != "student":
            raise TeacherServiceNotFoundError("Student not found.")

        timeline = self.repo.get_student_timeline(class_id=class_id, student_id=student_id, limit=limit)
        return TeacherStudentTimelineOut(
            class_id=class_id,
            student_id=student_id,
            timeline=[
                TeacherTimelineEventOut(
                    event_type=item["event_type"],
                    occurred_at=item["occurred_at"],
                    details=item["details"],
                )
                for item in timeline
            ],
        )

    def get_student_concept_trend(
        self,
        *,
        teacher_id: UUID,
        class_id: UUID,
        student_id: UUID,
        concept_id: str,
        days: int = 30,
    ) -> TeacherStudentConceptTrendOut:
        self._require_teacher_user(teacher_id)
        teacher_class = self._require_teacher_class(teacher_id=teacher_id, class_id=class_id)

        student_user = self.repo.get_user(student_id)
        if not student_user or student_user.role != "student":
            raise TeacherServiceNotFoundError("Student not found.")

        scope_rows = self.repo.get_scope_concept_rows(
            subject=teacher_class.subject,
            sss_level=teacher_class.sss_level,
            term=teacher_class.term,
        )
        concept_rows_by_id = {
            str(row["concept_id"]): row
            for row in scope_rows
            if str(row.get("concept_id") or "").strip()
        }
        target = concept_rows_by_id.get(concept_id)
        if not target:
            raise TeacherServiceNotFoundError("Concept is not mapped in this class scope.")

        prereq_ids = [item for item in list(target.get("prereq_concept_ids") or []) if item]
        tracked_ids = [concept_id, *prereq_ids]
        concept_rows = self.repo.get_student_concept_rows(
            class_id=class_id,
            subject=teacher_class.subject,
            term=teacher_class.term,
            concept_ids=tracked_ids,
        )
        score_map = {row["concept_id"]: row for row in concept_rows if row["student_id"] == student_id}

        blocking_prereqs: list[str] = []
        for prereq_id in prereq_ids:
            prereq_row = score_map.get(prereq_id)
            prereq_score = float(prereq_row["mastery_score"]) if prereq_row else 0.0
            if prereq_score < GRAPH_MASTERY_THRESHOLD:
                blocking_prereqs.append(
                    self._readable_concept_label(prereq_id, fallback=concept_rows_by_id.get(prereq_id, {}).get("topic_title"))
                )

        target_row = score_map.get(concept_id)
        current_score = float(target_row["mastery_score"]) if target_row else None
        status, _ = self._classify_concept_status(
            concept_score=current_score,
            blocking_prerequisite_labels=blocking_prereqs,
        )

        since = datetime.now(timezone.utc) - timedelta(days=max(1, min(days, 90)))
        mastery_events = self.repo.get_mastery_events_for_students_since(
            student_ids=[student_id],
            subject=teacher_class.subject,
            term=teacher_class.term,
            since=since,
        )
        recent_events: list[TeacherConceptTrendEventOut] = []
        net_delta = 0.0
        for event in mastery_events:
            for entry in list(event.new_mastery or []):
                event_concept_id = str(entry.get("concept_id") or "").strip()
                if event_concept_id not in tracked_ids:
                    continue
                delta = float(entry.get("delta", 0.0) or 0.0)
                if event_concept_id == concept_id:
                    net_delta += delta
                recent_events.append(
                    TeacherConceptTrendEventOut(
                        concept_id=event_concept_id,
                        concept_label=self._readable_concept_label(
                            event_concept_id,
                            fallback=concept_rows_by_id.get(event_concept_id, {}).get("topic_title"),
                        ),
                        occurred_at=event.created_at,
                        delta=round(delta, 4),
                        source=str(getattr(event, "source", "") or "unknown"),
                    )
                )

        tracked_concepts = [
            TeacherConceptTrendSnapshotOut(
                concept_id=item_id,
                concept_label=self._readable_concept_label(item_id, fallback=concept_rows_by_id.get(item_id, {}).get("topic_title")),
                role="focus" if item_id == concept_id else "prerequisite",
                current_score=round(float(score_map[item_id]["mastery_score"]), 4) if item_id in score_map else None,
                last_evaluated_at=score_map[item_id]["last_evaluated_at"] if item_id in score_map else None,
            )
            for item_id in tracked_ids
        ]

        recent_events.sort(key=lambda item: item.occurred_at, reverse=True)
        return TeacherStudentConceptTrendOut(
            class_id=class_id,
            student_id=student_id,
            concept_id=concept_id,
            concept_label=self._readable_concept_label(concept_id, fallback=target.get("topic_title")),
            current_score=round(current_score, 4) if current_score is not None else None,
            last_evaluated_at=target_row["last_evaluated_at"] if target_row else None,
            status=status,
            blocking_prerequisite_labels=blocking_prereqs,
            net_delta_30d=round(net_delta, 4),
            evidence_event_count=len(recent_events),
            tracked_concepts=tracked_concepts,
            recent_events=recent_events[:8],
        )

    def get_student_focus_export(
        self,
        *,
        teacher_id: UUID,
        class_id: UUID,
        student_id: UUID,
        concept_id: str,
    ) -> TeacherExportOut:
        teacher_class = self._require_teacher_class(teacher_id=teacher_id, class_id=class_id)
        trend = self.get_student_concept_trend(
            teacher_id=teacher_id,
            class_id=class_id,
            student_id=student_id,
            concept_id=concept_id,
            days=30,
        )
        drilldown = self.get_concept_student_drilldown(
            teacher_id=teacher_id,
            class_id=class_id,
            concept_id=concept_id,
        )
        student = next((item for item in drilldown.students if item.student_id == student_id), None)
        if not student:
            raise TeacherServiceNotFoundError("Student is not part of the focused concept drilldown.")
        timeline = self.get_student_timeline(
            teacher_id=teacher_id,
            class_id=class_id,
            student_id=student_id,
            limit=8,
        )

        sections = [
            TeacherExportSectionOut(
                title="Focus summary",
                items=[
                    f"Status: {trend.status.replace('_', ' ')}",
                    f"Current concept mastery: {self._format_percentage(trend.current_score)}",
                    f"Overall mastery: {self._format_percentage(student.overall_mastery_score)}",
                    f"Net delta (30d): {trend.net_delta_30d:+.2f}",
                    f"Evidence events: {trend.evidence_event_count}",
                    f"Recommended action: {student.recommended_action}",
                ],
            ),
            TeacherExportSectionOut(
                title="Blocking prerequisites",
                items=list(trend.blocking_prerequisite_labels),
            ),
            TeacherExportSectionOut(
                title="Tracked concept path",
                items=[
                    f"{item.concept_label} [{item.role}]: {self._format_percentage(item.current_score)}"
                    for item in trend.tracked_concepts
                ],
            ),
            TeacherExportSectionOut(
                title="Recent concept evidence",
                items=[
                    f"{item.concept_label}: {item.delta:+.2f} via {item.source} on {item.occurred_at.isoformat()}"
                    for item in trend.recent_events
                ],
            ),
            TeacherExportSectionOut(
                title="Recent timeline",
                items=[
                    f"{event.event_type.replace('_', ' ')} on {event.occurred_at.isoformat()}"
                    for event in timeline.timeline
                ],
            ),
        ]
        subtitle = (
            f"{student.student_name} • {trend.concept_label} • {teacher_class.name} "
            f"({teacher_class.subject.title()} {teacher_class.sss_level} Term {teacher_class.term})"
        )
        return TeacherExportOut(
            export_kind="student_focus",
            class_id=class_id,
            class_name=teacher_class.name,
            subject=teacher_class.subject,
            sss_level=teacher_class.sss_level,
            term=teacher_class.term,
            title=f"{student.student_name} focus on {trend.concept_label}",
            subtitle=subtitle,
            generated_at=datetime.now(timezone.utc),
            file_name=(
                f"{self._slugify(student.student_name, fallback='student')}-"
                f"{self._slugify(trend.concept_label, fallback='concept')}-focus.md"
            ),
            share_text=(
                f"{student.student_name} is {trend.status.replace('_', ' ')} on {trend.concept_label}. "
                f"Recommended action: {student.recommended_action}"
            ),
            markdown=self._build_markdown(
                title=f"{student.student_name} focus on {trend.concept_label}",
                subtitle=subtitle,
                sections=sections,
            ),
            sections=sections,
            student_id=student.student_id,
            student_name=student.student_name,
            concept_id=trend.concept_id,
            concept_label=trend.concept_label,
        )

    def get_concept_compare_export(
        self,
        *,
        teacher_id: UUID,
        class_id: UUID,
        left_concept_id: str,
        right_concept_id: str,
    ) -> TeacherExportOut:
        teacher_class = self._require_teacher_class(teacher_id=teacher_id, class_id=class_id)
        comparison = self.get_concept_compare(
            teacher_id=teacher_id,
            class_id=class_id,
            left_concept_id=left_concept_id,
            right_concept_id=right_concept_id,
        )

        sections = [
            TeacherExportSectionOut(
                title="Comparison headline",
                items=[comparison.summary.headline, comparison.summary.rationale],
            ),
            TeacherExportSectionOut(
                title="Concept summary",
                items=[
                    f"{comparison.left.concept_label}: {self._format_percentage(comparison.summary.avg_left_score)} average score, "
                    f"{comparison.summary.left_weaker_count} students weaker here.",
                    f"{comparison.right.concept_label}: {self._format_percentage(comparison.summary.avg_right_score)} average score, "
                    f"{comparison.summary.right_weaker_count} students weaker here.",
                    f"Both blocked count: {comparison.summary.both_blocked_count}",
                    f"Both ready count: {comparison.summary.both_ready_count}",
                ],
            ),
            TeacherExportSectionOut(
                title="Students driving the difference",
                items=[
                    (
                        f"{student.student_name}: {student.comparison_signal.replace('_', ' ')}. "
                        f"{comparison.left.concept_label}={self._format_percentage(student.left.concept_score)}, "
                        f"{comparison.right.concept_label}={self._format_percentage(student.right.concept_score)}"
                    )
                    for student in comparison.students
                ],
            ),
        ]
        subtitle = (
            f"{teacher_class.name} • {comparison.left.concept_label} vs {comparison.right.concept_label} • "
            f"{teacher_class.subject.title()} {teacher_class.sss_level} Term {teacher_class.term}"
        )
        return TeacherExportOut(
            export_kind="concept_compare",
            class_id=class_id,
            class_name=teacher_class.name,
            subject=teacher_class.subject,
            sss_level=teacher_class.sss_level,
            term=teacher_class.term,
            title=f"{comparison.left.concept_label} vs {comparison.right.concept_label}",
            subtitle=subtitle,
            generated_at=datetime.now(timezone.utc),
            file_name=(
                f"{self._slugify(teacher_class.name, fallback='class')}-"
                f"{self._slugify(comparison.left.concept_label, fallback='left')}-vs-"
                f"{self._slugify(comparison.right.concept_label, fallback='right')}.md"
            ),
            share_text=(
                f"{comparison.summary.headline} "
                f"Recommended focus: "
                f"{comparison.left.concept_label if comparison.summary.recommended_focus_side == 'left' else comparison.right.concept_label if comparison.summary.recommended_focus_side == 'right' else 'split support across both concepts'}."
            ),
            markdown=self._build_markdown(
                title=f"{comparison.left.concept_label} vs {comparison.right.concept_label}",
                subtitle=subtitle,
                sections=sections,
            ),
            sections=sections,
            concept_id=comparison.left.concept_id,
            concept_label=f"{comparison.left.concept_label} vs {comparison.right.concept_label}",
        )

    def get_assignment_outcomes(
        self,
        *,
        teacher_id: UUID,
        class_id: UUID,
        concept_id: str | None = None,
    ) -> TeacherAssignmentOutcomeSummaryOut:
        self._require_teacher_user(teacher_id)
        teacher_class = self._require_teacher_class(teacher_id=teacher_id, class_id=class_id)

        assignments = self.repo.get_class_assignments(
            class_id=class_id,
            subject=teacher_class.subject,
            term=teacher_class.term,
            limit=50,
        )
        if concept_id:
            assignments = [row for row in assignments if str(getattr(row, "concept_id", "") or "").strip() == concept_id]
        if not assignments:
            return TeacherAssignmentOutcomeSummaryOut(class_id=class_id)

        class_student_ids = self.repo.get_active_student_ids(class_id=class_id)
        targeted_student_ids = sorted({row.student_id for row in assignments if row.student_id})
        targeted_users = self.repo.get_users_by_ids(targeted_student_ids)
        oldest_created_at = min((row.created_at for row in assignments), default=datetime.now(timezone.utc))
        mastery_events = self.repo.get_mastery_events_for_students_since(
            student_ids=class_student_ids,
            subject=teacher_class.subject,
            term=teacher_class.term,
            since=oldest_created_at,
        )
        activity_rows = self.repo.get_activity_rows_for_students_since(
            student_ids=class_student_ids,
            subject=teacher_class.subject,
            term=teacher_class.term,
            since=oldest_created_at,
        )

        mastery_by_student: dict[UUID, list] = {}
        for event in mastery_events:
            mastery_by_student.setdefault(event.student_id, []).append(event)

        activity_by_student: dict[UUID, list] = {}
        for row in activity_rows:
            activity_by_student.setdefault(row.student_id, []).append(row)

        outcomes: list[TeacherAssignmentOutcomeOut] = []
        for row in assignments:
            target_student_ids = [row.student_id] if row.student_id else class_student_ids
            window_end = row.created_at + timedelta(days=INTERVENTION_OUTCOME_WINDOW_DAYS)

            candidate_mastery = [
                event
                for student_id in target_student_ids
                for event in mastery_by_student.get(student_id, [])
                if row.created_at <= event.created_at <= window_end
            ]
            candidate_activity = [
                activity
                for student_id in target_student_ids
                for activity in activity_by_student.get(student_id, [])
                if row.created_at <= activity.created_at <= window_end
            ]

            net_delta = 0.0
            evidence_event_count = 0
            for event in candidate_mastery:
                event_matched = False
                for entry in list(event.new_mastery or []):
                    entry_concept_id = str(entry.get("concept_id") or "").strip()
                    if row.concept_id and entry_concept_id and entry_concept_id != row.concept_id:
                        continue
                    net_delta += float(entry.get("delta", 0.0) or 0.0)
                    event_matched = True
                if event_matched:
                    evidence_event_count += 1

            engaged_students = {event.student_id for event in candidate_mastery} | {
                activity.student_id for activity in candidate_activity
            }

            if not engaged_students and evidence_event_count == 0:
                outcome_status = "no_evidence"
            elif net_delta > 0.05:
                outcome_status = "improving"
            elif net_delta < -0.02:
                outcome_status = "declining"
            else:
                outcome_status = "flat"

            outcomes.append(
                TeacherAssignmentOutcomeOut(
                    assignment_id=row.id,
                    title=row.title,
                    assignment_type=row.assignment_type,
                    status=row.status,
                    ref_id=row.ref_id,
                    concept_id=row.concept_id,
                    concept_label=row.concept_label,
                    target_scope="student" if row.student_id else "class",
                    student_id=row.student_id,
                    student_name=(
                        self._display_name(targeted_users.get(row.student_id), fallback_id=row.student_id)
                        if row.student_id
                        else None
                    ),
                    target_student_count=len(target_student_ids),
                    engaged_student_count=len(engaged_students),
                    evidence_event_count=evidence_event_count,
                    outcome_status=outcome_status,
                    net_mastery_delta=round(net_delta, 4),
                    due_at=row.due_at,
                    created_at=row.created_at,
                )
            )

        outcomes.sort(
            key=lambda item: (
                {"declining": 0, "no_evidence": 1, "flat": 2, "improving": 3}[item.outcome_status],
                0 if item.target_scope == "student" else 1,
                item.created_at,
            )
        )
        evidence_outcomes = [item.net_mastery_delta for item in outcomes if item.evidence_event_count > 0]
        return TeacherAssignmentOutcomeSummaryOut(
            class_id=class_id,
            total_assignments=len(outcomes),
            open_assignments=sum(1 for item in outcomes if item.status == "assigned"),
            improving_assignments=sum(1 for item in outcomes if item.outcome_status == "improving"),
            declining_assignments=sum(1 for item in outcomes if item.outcome_status == "declining"),
            no_evidence_assignments=sum(1 for item in outcomes if item.outcome_status == "no_evidence"),
            avg_net_mastery_delta=round(sum(evidence_outcomes) / len(evidence_outcomes), 4) if evidence_outcomes else 0.0,
            outcomes=outcomes[:12],
        )

    def get_intervention_outcomes(
        self,
        *,
        teacher_id: UUID,
        class_id: UUID,
        concept_id: str | None = None,
    ) -> TeacherInterventionOutcomeSummaryOut:
        self._require_teacher_user(teacher_id)
        teacher_class = self._require_teacher_class(teacher_id=teacher_id, class_id=class_id)

        interventions = self.repo.get_class_interventions(
            class_id=class_id,
            subject=teacher_class.subject,
            term=teacher_class.term,
            limit=50,
        )
        if concept_id:
            interventions = [row for row in interventions if str(getattr(row, "concept_id", "") or "").strip() == concept_id]
        if not interventions:
            return TeacherInterventionOutcomeSummaryOut(class_id=class_id)

        student_ids = sorted({row.student_id for row in interventions})
        users = self.repo.get_users_by_ids(student_ids)
        oldest_created_at = min((row.created_at for row in interventions), default=datetime.now(timezone.utc))
        mastery_events = self.repo.get_mastery_events_for_students_since(
            student_ids=student_ids,
            subject=teacher_class.subject,
            term=teacher_class.term,
            since=oldest_created_at,
        )
        events_by_student: dict[UUID, list] = {}
        for event in mastery_events:
            events_by_student.setdefault(event.student_id, []).append(event)

        outcomes: list[TeacherInterventionOutcomeOut] = []
        for row in interventions:
            window_end = row.created_at + timedelta(days=INTERVENTION_OUTCOME_WINDOW_DAYS)
            candidate_events = [
                event
                for event in events_by_student.get(row.student_id, [])
                if row.created_at <= event.created_at <= window_end
            ]
            net_delta = 0.0
            evidence_event_count = 0
            for event in candidate_events:
                event_matched = False
                for entry in list(event.new_mastery or []):
                    entry_concept_id = str(entry.get("concept_id") or "").strip()
                    if row.concept_id and entry_concept_id and entry_concept_id != row.concept_id:
                        continue
                    net_delta += float(entry.get("delta", 0.0) or 0.0)
                    event_matched = True
                if event_matched:
                    evidence_event_count += 1

            if evidence_event_count == 0:
                outcome_status = "no_evidence"
            elif net_delta > 0.05:
                outcome_status = "improving"
            elif net_delta < -0.02:
                outcome_status = "declining"
            else:
                outcome_status = "flat"

            user = users.get(row.student_id)
            display_name = (
                str(getattr(user, "display_name", "") or "").strip()
                or " ".join(
                    part
                    for part in [
                        str(getattr(user, "first_name", "") or "").strip(),
                        str(getattr(user, "last_name", "") or "").strip(),
                    ]
                    if part
                ).strip()
                or str(getattr(user, "email", "") or "").strip()
                or f"Student {str(row.student_id)[:8]}"
            )
            outcomes.append(
                TeacherInterventionOutcomeOut(
                    intervention_id=row.id,
                    student_id=row.student_id,
                    student_name=display_name,
                    intervention_type=row.intervention_type,
                    concept_id=row.concept_id,
                    concept_label=row.concept_label,
                    severity=row.severity,
                    status=row.status,
                    outcome_status=outcome_status,
                    net_mastery_delta=round(net_delta, 4),
                    evidence_event_count=evidence_event_count,
                    created_at=row.created_at,
                    latest_mastery_event_at=candidate_events[0].created_at if candidate_events else None,
                    notes=row.notes,
                    action_plan=row.action_plan,
                )
            )

        outcomes.sort(
            key=lambda item: (
                {"declining": 0, "no_evidence": 1, "flat": 2, "improving": 3}[item.outcome_status],
                {"high": 0, "medium": 1, "low": 2}[item.severity],
                item.created_at,
            )
        )
        evidence_outcomes = [item.net_mastery_delta for item in outcomes if item.evidence_event_count > 0]
        return TeacherInterventionOutcomeSummaryOut(
            class_id=class_id,
            total_interventions=len(outcomes),
            open_interventions=sum(1 for item in outcomes if item.status == "open"),
            improving_interventions=sum(1 for item in outcomes if item.outcome_status == "improving"),
            declining_interventions=sum(1 for item in outcomes if item.outcome_status == "declining"),
            no_evidence_interventions=sum(1 for item in outcomes if item.outcome_status == "no_evidence"),
            avg_net_mastery_delta=round(sum(evidence_outcomes) / len(evidence_outcomes), 4) if evidence_outcomes else 0.0,
            outcomes=outcomes[:12],
        )

    def get_repeat_risk_summary(self, *, teacher_id: UUID, class_id: UUID) -> TeacherRepeatRiskSummaryOut:
        self._require_teacher_user(teacher_id)
        teacher_class = self._require_teacher_class(teacher_id=teacher_id, class_id=class_id)

        scope_rows = self.repo.get_scope_concept_rows(
            subject=teacher_class.subject,
            sss_level=teacher_class.sss_level,
            term=teacher_class.term,
        )
        if not scope_rows:
            return TeacherRepeatRiskSummaryOut(class_id=class_id)

        concept_rows_by_id = {
            str(row["concept_id"]): row
            for row in scope_rows
            if str(row.get("concept_id") or "").strip()
        }
        concept_ids = list(concept_rows_by_id.keys())
        if not concept_ids:
            return TeacherRepeatRiskSummaryOut(class_id=class_id)

        student_ids = self.repo.get_active_student_ids(class_id=class_id)
        if not student_ids:
            return TeacherRepeatRiskSummaryOut(class_id=class_id)

        users = self.repo.get_users_by_ids(student_ids)
        overall_scores = self.repo.get_avg_mastery_by_student(
            class_id=class_id,
            subject=teacher_class.subject,
            term=teacher_class.term,
        )
        activity_stats = self.repo.get_recent_activity_stats(
            class_id=class_id,
            subject=teacher_class.subject,
            term=teacher_class.term,
            since=datetime.now(timezone.utc) - timedelta(days=INACTIVITY_DAYS),
        )
        concept_rows = self.repo.get_student_concept_rows(
            class_id=class_id,
            subject=teacher_class.subject,
            term=teacher_class.term,
            concept_ids=concept_ids,
        )

        scores_by_student: dict[UUID, dict[str, dict]] = {}
        for row in concept_rows:
            scores_by_student.setdefault(row["student_id"], {})[row["concept_id"]] = row

        students: list[TeacherRepeatRiskStudentOut] = []
        for student_id in student_ids:
            flagged_concepts: list[TeacherRepeatRiskConceptOut] = []
            blocked_count = 0
            weak_count = 0

            for concept_id, row in concept_rows_by_id.items():
                concept_row = scores_by_student.get(student_id, {}).get(concept_id)
                concept_score = float(concept_row["mastery_score"]) if concept_row else None
                prereq_ids = [item for item in list(row.get("prereq_concept_ids") or []) if item]
                blocking_prereqs = []
                for prereq_id in prereq_ids:
                    prereq_row = scores_by_student.get(student_id, {}).get(prereq_id)
                    prereq_score = float(prereq_row["mastery_score"]) if prereq_row else 0.0
                    if prereq_score < GRAPH_MASTERY_THRESHOLD:
                        blocking_prereqs.append(
                            self._readable_concept_label(
                                prereq_id,
                                fallback=concept_rows_by_id.get(prereq_id, {}).get("topic_title"),
                            )
                        )

                status, _ = self._classify_concept_status(
                    concept_score=concept_score,
                    blocking_prerequisite_labels=blocking_prereqs,
                )
                if status not in {"blocked", "needs_attention"}:
                    continue

                if status == "blocked":
                    blocked_count += 1
                else:
                    weak_count += 1

                flagged_concepts.append(
                    TeacherRepeatRiskConceptOut(
                        concept_id=concept_id,
                        concept_label=self._readable_concept_label(concept_id, fallback=row.get("topic_title")),
                        topic_id=row.get("topic_id"),
                        topic_title=row.get("topic_title"),
                        status=status,
                        concept_score=round(concept_score, 4) if concept_score is not None else None,
                        blocking_prerequisite_labels=blocking_prereqs,
                    )
                )

            flagged_count = blocked_count + weak_count
            if flagged_count < 2:
                continue

            flagged_concepts.sort(
                key=lambda item: (
                    0 if item.status == "blocked" else 1,
                    1.1 if item.concept_score is None else item.concept_score,
                    item.concept_label.lower(),
                )
            )

            primary = flagged_concepts[0]
            if blocked_count > 0:
                risk_status = "repeat_blocker"
                recommended_action = (
                    f"Repair {primary.blocking_prerequisite_labels[0]} before reteaching {primary.concept_label}; "
                    f"this student is blocked across {flagged_count} mapped concepts."
                    if primary.blocking_prerequisite_labels
                    else f"Use a prerequisite bridge before reteaching {primary.concept_label}; "
                    f"this student is struggling across {flagged_count} mapped concepts."
                )
            else:
                risk_status = "repeat_weakness"
                recommended_action = (
                    f"Run a short checkpoint and targeted practice across {flagged_count} weak concepts, starting with "
                    f"{primary.concept_label}."
                )

            stats = activity_stats.get(student_id, {})
            students.append(
                TeacherRepeatRiskStudentOut(
                    student_id=student_id,
                    student_name=self._display_name(users.get(student_id), fallback_id=student_id),
                    risk_status=risk_status,
                    blocked_concept_count=blocked_count,
                    weak_concept_count=weak_count,
                    flagged_concept_count=flagged_count,
                    overall_mastery_score=round(float(overall_scores.get(student_id, 0.0)), 4)
                    if student_id in overall_scores
                    else None,
                    recent_activity_count_7d=int(stats.get("event_count", 0)),
                    recent_study_time_seconds_7d=int(stats.get("duration_seconds", 0)),
                    recommended_action=recommended_action,
                    driving_concepts=flagged_concepts[:4],
                )
            )

        students.sort(
            key=lambda item: (
                0 if item.risk_status == "repeat_blocker" else 1,
                -(item.blocked_concept_count * 2 + item.weak_concept_count),
                1.1 if item.overall_mastery_score is None else item.overall_mastery_score,
                item.student_name.lower(),
            )
        )

        return TeacherRepeatRiskSummaryOut(
            class_id=class_id,
            at_risk_student_count=len(students),
            repeat_blocker_students=sum(1 for item in students if item.risk_status == "repeat_blocker"),
            repeat_weakness_students=sum(1 for item in students if item.risk_status == "repeat_weakness"),
            students=students[:10],
        )

    def get_student_risk_matrix(self, *, teacher_id: UUID, class_id: UUID) -> TeacherRiskMatrixOut:
        self._require_teacher_user(teacher_id)
        teacher_class = self._require_teacher_class(teacher_id=teacher_id, class_id=class_id)

        graph = self.get_class_graph_summary(teacher_id=teacher_id, class_id=class_id)
        priority_nodes = [node for node in graph.nodes if node.status in {"blocked", "needs_attention"}]
        if not priority_nodes:
            return TeacherRiskMatrixOut(class_id=class_id)

        selected_nodes = priority_nodes[:5]
        concept_ids = [node.concept_id for node in selected_nodes]

        scope_rows = self.repo.get_scope_concept_rows(
            subject=teacher_class.subject,
            sss_level=teacher_class.sss_level,
            term=teacher_class.term,
        )
        concept_rows_by_id = {
            str(row["concept_id"]): row
            for row in scope_rows
            if str(row.get("concept_id") or "").strip()
        }
        prereq_ids = {
            prereq_id
            for concept_id in concept_ids
            for prereq_id in list(concept_rows_by_id.get(concept_id, {}).get("prereq_concept_ids") or [])
            if prereq_id
        }

        student_ids = self.repo.get_active_student_ids(class_id=class_id)
        if not student_ids:
            return TeacherRiskMatrixOut(class_id=class_id)

        users = self.repo.get_users_by_ids(student_ids)
        overall_scores = self.repo.get_avg_mastery_by_student(
            class_id=class_id,
            subject=teacher_class.subject,
            term=teacher_class.term,
        )
        activity_stats = self.repo.get_recent_activity_stats(
            class_id=class_id,
            subject=teacher_class.subject,
            term=teacher_class.term,
            since=datetime.now(timezone.utc) - timedelta(days=INACTIVITY_DAYS),
        )
        concept_rows = self.repo.get_student_concept_rows(
            class_id=class_id,
            subject=teacher_class.subject,
            term=teacher_class.term,
            concept_ids=[*concept_ids, *prereq_ids],
        )

        scores_by_student: dict[UUID, dict[str, dict]] = {}
        for row in concept_rows:
            scores_by_student.setdefault(row["student_id"], {})[row["concept_id"]] = row

        matrix_students: list[TeacherRiskMatrixStudentOut] = []
        for student_id in student_ids:
            cells: list[TeacherRiskMatrixCellOut] = []
            blocked_count = 0
            weak_count = 0
            for concept_id in concept_ids:
                row = concept_rows_by_id.get(concept_id, {})
                concept_row = scores_by_student.get(student_id, {}).get(concept_id)
                concept_score = float(concept_row["mastery_score"]) if concept_row else None
                blocking_prereqs = []
                for prereq_id in list(row.get("prereq_concept_ids") or []):
                    prereq_row = scores_by_student.get(student_id, {}).get(prereq_id)
                    prereq_score = float(prereq_row["mastery_score"]) if prereq_row else 0.0
                    if prereq_score < GRAPH_MASTERY_THRESHOLD:
                        blocking_prereqs.append(
                            self._readable_concept_label(
                                prereq_id,
                                fallback=concept_rows_by_id.get(prereq_id, {}).get("topic_title"),
                            )
                        )

                status, _ = self._classify_concept_status(
                    concept_score=concept_score,
                    blocking_prerequisite_labels=blocking_prereqs,
                )
                if status == "blocked":
                    blocked_count += 1
                elif status == "needs_attention":
                    weak_count += 1

                cells.append(
                    TeacherRiskMatrixCellOut(
                        concept_id=concept_id,
                        status=status,
                        concept_score=round(concept_score, 4) if concept_score is not None else None,
                        blocking_prerequisite_labels=blocking_prereqs,
                    )
                )

            if blocked_count == 0 and weak_count == 0:
                continue

            matrix_students.append(
                TeacherRiskMatrixStudentOut(
                    student_id=student_id,
                    student_name=self._display_name(users.get(student_id), fallback_id=student_id),
                    overall_mastery_score=round(float(overall_scores.get(student_id, 0.0)), 4)
                    if student_id in overall_scores
                    else None,
                    blocked_concept_count=blocked_count,
                    weak_concept_count=weak_count,
                    recent_activity_count_7d=int(activity_stats.get(student_id, {}).get("event_count", 0)),
                    recent_study_time_seconds_7d=int(activity_stats.get(student_id, {}).get("duration_seconds", 0)),
                    cells=cells,
                )
            )

        matrix_students.sort(
            key=lambda item: (
                -(item.blocked_concept_count * 2 + item.weak_concept_count),
                1.1 if item.overall_mastery_score is None else item.overall_mastery_score,
                item.student_name.lower(),
            )
        )

        return TeacherRiskMatrixOut(
            class_id=class_id,
            concepts=[
                TeacherRiskMatrixConceptOut(
                    concept_id=node.concept_id,
                    concept_label=node.concept_label,
                    topic_id=node.topic_id,
                    topic_title=node.topic_title,
                    status=node.status,
                )
                for node in selected_nodes
            ],
            students=matrix_students[:8],
        )

    def get_concept_compare(
        self,
        *,
        teacher_id: UUID,
        class_id: UUID,
        left_concept_id: str,
        right_concept_id: str,
    ) -> TeacherConceptCompareOut:
        self._require_teacher_user(teacher_id)
        teacher_class = self._require_teacher_class(teacher_id=teacher_id, class_id=class_id)

        left_concept_id = str(left_concept_id or "").strip()
        right_concept_id = str(right_concept_id or "").strip()
        if not left_concept_id or not right_concept_id:
            raise TeacherServiceValidationError("Both concept IDs are required for concept comparison.")
        if left_concept_id == right_concept_id:
            raise TeacherServiceValidationError("Choose two different concepts to compare.")

        graph = self.get_class_graph_summary(teacher_id=teacher_id, class_id=class_id)
        node_by_id = {node.concept_id: node for node in graph.nodes}
        left_node = node_by_id.get(left_concept_id)
        right_node = node_by_id.get(right_concept_id)
        if not left_node or not right_node:
            raise TeacherServiceNotFoundError("One or both concept nodes are not mapped in this class scope.")

        scope_rows = self.repo.get_scope_concept_rows(
            subject=teacher_class.subject,
            sss_level=teacher_class.sss_level,
            term=teacher_class.term,
        )
        concept_rows_by_id = {
            str(row["concept_id"]): row
            for row in scope_rows
            if str(row.get("concept_id") or "").strip()
        }
        left_row = concept_rows_by_id.get(left_concept_id)
        right_row = concept_rows_by_id.get(right_concept_id)
        if not left_row or not right_row:
            raise TeacherServiceNotFoundError("One or both compared concepts are missing curriculum mappings.")

        needed_concepts = {
            left_concept_id,
            right_concept_id,
            *list(left_row.get("prereq_concept_ids") or []),
            *list(right_row.get("prereq_concept_ids") or []),
        }
        student_ids = self.repo.get_active_student_ids(class_id=class_id)
        if not student_ids:
            return TeacherConceptCompareOut(
                class_id=class_id,
                left=TeacherConceptCompareSelectionOut(
                    concept_id=left_node.concept_id,
                    concept_label=left_node.concept_label,
                    topic_id=left_node.topic_id,
                    topic_title=left_node.topic_title,
                    status=left_node.status,
                    avg_score=left_node.avg_score,
                    student_count=left_node.student_count,
                    blocking_prerequisite_labels=list(left_node.blocking_prerequisite_labels or []),
                ),
                right=TeacherConceptCompareSelectionOut(
                    concept_id=right_node.concept_id,
                    concept_label=right_node.concept_label,
                    topic_id=right_node.topic_id,
                    topic_title=right_node.topic_title,
                    status=right_node.status,
                    avg_score=right_node.avg_score,
                    student_count=right_node.student_count,
                    blocking_prerequisite_labels=list(right_node.blocking_prerequisite_labels or []),
                ),
                summary=TeacherConceptCompareSummaryOut(
                    headline=f"Compare {left_node.concept_label} and {right_node.concept_label} once the class has evidence.",
                    rationale="There are no active students in this class yet, so the concept comparison is still empty.",
                    recommended_focus_side="tie",
                ),
                students=[],
            )

        users = self.repo.get_users_by_ids(student_ids)
        overall_scores = self.repo.get_avg_mastery_by_student(
            class_id=class_id,
            subject=teacher_class.subject,
            term=teacher_class.term,
        )
        activity_stats = self.repo.get_recent_activity_stats(
            class_id=class_id,
            subject=teacher_class.subject,
            term=teacher_class.term,
            since=datetime.now(timezone.utc) - timedelta(days=INACTIVITY_DAYS),
        )
        concept_rows = self.repo.get_student_concept_rows(
            class_id=class_id,
            subject=teacher_class.subject,
            term=teacher_class.term,
            concept_ids=sorted(needed_concepts),
        )
        scores_by_student: dict[UUID, dict[str, dict]] = {}
        for row in concept_rows:
            scores_by_student.setdefault(row["student_id"], {})[row["concept_id"]] = row

        def _build_side(*, student_id: UUID, concept_id: str, row: dict, node: TeacherGraphConceptNodeOut) -> TeacherConceptCompareStudentSideOut:
            concept_row = scores_by_student.get(student_id, {}).get(concept_id)
            concept_score = float(concept_row["mastery_score"]) if concept_row else None
            prereq_labels: list[str] = []
            for prereq_id in list(row.get("prereq_concept_ids") or []):
                prereq_row = scores_by_student.get(student_id, {}).get(prereq_id)
                prereq_score = float(prereq_row["mastery_score"]) if prereq_row else 0.0
                if prereq_score < GRAPH_MASTERY_THRESHOLD:
                    prereq_labels.append(
                        self._readable_concept_label(
                            prereq_id,
                            fallback=concept_rows_by_id.get(prereq_id, {}).get("topic_title"),
                        )
                    )
            status, _ = self._classify_concept_status(
                concept_score=concept_score,
                blocking_prerequisite_labels=prereq_labels,
            )
            return TeacherConceptCompareStudentSideOut(
                concept_id=concept_id,
                concept_label=node.concept_label,
                status=status,
                concept_score=round(concept_score, 4) if concept_score is not None else None,
                blocking_prerequisite_labels=prereq_labels,
            )

        students: list[TeacherConceptCompareStudentOut] = []
        both_blocked_count = 0
        left_weaker_count = 0
        right_weaker_count = 0
        both_ready_count = 0

        for student_id in student_ids:
            left_side = _build_side(student_id=student_id, concept_id=left_concept_id, row=left_row, node=left_node)
            right_side = _build_side(student_id=student_id, concept_id=right_concept_id, row=right_row, node=right_node)

            left_score = -1.0 if left_side.concept_score is None else float(left_side.concept_score)
            right_score = -1.0 if right_side.concept_score is None else float(right_side.concept_score)

            left_bad = left_side.status in {"blocked", "needs_attention", "unassessed"}
            right_bad = right_side.status in {"blocked", "needs_attention", "unassessed"}
            if left_side.status == "blocked" and right_side.status == "blocked":
                comparison_signal = "both_blocked"
                both_blocked_count += 1
            elif left_bad and (not right_bad or left_score < right_score):
                comparison_signal = "left_weaker"
                left_weaker_count += 1
            elif right_bad and (not left_bad or right_score < left_score):
                comparison_signal = "right_weaker"
                right_weaker_count += 1
            elif not left_bad and not right_bad:
                comparison_signal = "both_ready"
                both_ready_count += 1
            else:
                comparison_signal = "mixed"

            if left_score > right_score:
                stronger_side = "left"
            elif right_score > left_score:
                stronger_side = "right"
            else:
                stronger_side = "tied"

            stats = activity_stats.get(student_id, {})
            students.append(
                TeacherConceptCompareStudentOut(
                    student_id=student_id,
                    student_name=self._display_name(users.get(student_id), fallback_id=student_id),
                    overall_mastery_score=round(float(overall_scores.get(student_id, 0.0)), 4)
                    if student_id in overall_scores
                    else None,
                    recent_activity_count_7d=int(stats.get("event_count", 0)),
                    recent_study_time_seconds_7d=int(stats.get("duration_seconds", 0)),
                    stronger_side=stronger_side,
                    comparison_signal=comparison_signal,
                    left=left_side,
                    right=right_side,
                )
            )

        students.sort(
            key=lambda item: (
                {"both_blocked": 0, "left_weaker": 1, "right_weaker": 2, "mixed": 3, "both_ready": 4}[item.comparison_signal],
                1.1 if item.left.concept_score is None else item.left.concept_score,
                1.1 if item.right.concept_score is None else item.right.concept_score,
                item.student_name.lower(),
            )
        )

        left_avg = left_node.avg_score if left_node.avg_score is not None else None
        right_avg = right_node.avg_score if right_node.avg_score is not None else None
        if left_weaker_count > right_weaker_count:
            recommended_focus_side = "left"
            headline = f"{left_node.concept_label} is the stronger blocker across the class."
            rationale = (
                f"More students are weaker on {left_node.concept_label} than on {right_node.concept_label}, "
                "so reteaching should start there."
            )
        elif right_weaker_count > left_weaker_count:
            recommended_focus_side = "right"
            headline = f"{right_node.concept_label} is the stronger blocker across the class."
            rationale = (
                f"More students are weaker on {right_node.concept_label} than on {left_node.concept_label}, "
                "so reteaching should start there."
            )
        else:
            recommended_focus_side = "tie"
            headline = f"{left_node.concept_label} and {right_node.concept_label} are equally critical right now."
            rationale = (
                "The compared concepts are showing similar class-wide weakness, so use the student table to split "
                "targeted support instead of forcing one global reteach order."
            )

        return TeacherConceptCompareOut(
            class_id=class_id,
            left=TeacherConceptCompareSelectionOut(
                concept_id=left_node.concept_id,
                concept_label=left_node.concept_label,
                topic_id=left_node.topic_id,
                topic_title=left_node.topic_title,
                status=left_node.status,
                avg_score=left_avg,
                student_count=left_node.student_count,
                blocking_prerequisite_labels=list(left_node.blocking_prerequisite_labels or []),
            ),
            right=TeacherConceptCompareSelectionOut(
                concept_id=right_node.concept_id,
                concept_label=right_node.concept_label,
                topic_id=right_node.topic_id,
                topic_title=right_node.topic_title,
                status=right_node.status,
                avg_score=right_avg,
                student_count=right_node.student_count,
                blocking_prerequisite_labels=list(right_node.blocking_prerequisite_labels or []),
            ),
            summary=TeacherConceptCompareSummaryOut(
                students_compared=len(students),
                both_blocked_count=both_blocked_count,
                left_weaker_count=left_weaker_count,
                right_weaker_count=right_weaker_count,
                both_ready_count=both_ready_count,
                avg_left_score=round(float(left_avg), 4) if left_avg is not None else None,
                avg_right_score=round(float(right_avg), 4) if right_avg is not None else None,
                recommended_focus_side=recommended_focus_side,
                headline=headline,
                rationale=rationale,
            ),
            students=students[:12],
        )
