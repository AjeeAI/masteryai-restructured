from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


Subject = Literal["math", "english", "civic"]
SSSLevel = Literal["SSS1", "SSS2", "SSS3"]
AssignmentType = Literal["topic", "quiz", "revision"]
InterventionType = Literal["note", "flag", "support_plan", "parent_contact"]
Severity = Literal["low", "medium", "high"]


class TeacherClassCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=500)
    subject: Subject
    sss_level: SSSLevel
    term: Literal[1, 2, 3]


class TeacherClassOut(BaseModel):
    id: UUID
    teacher_id: UUID
    name: str
    description: str | None = None
    subject: Subject
    sss_level: SSSLevel
    term: Literal[1, 2, 3]
    is_active: bool
    enrolled_count: int = 0
    created_at: datetime
    updated_at: datetime


class TeacherClassListOut(BaseModel):
    classes: list[TeacherClassOut]


class TeacherClassEnrollIn(BaseModel):
    student_ids: list[UUID] = Field(min_length=1, max_length=500)


class TeacherClassEnrollOut(BaseModel):
    class_id: UUID
    enrolled_student_ids: list[UUID]
    already_enrolled_student_ids: list[UUID]
    total_enrolled: int


class CompletionDistributionOut(BaseModel):
    completed: int = 0
    in_progress: int = 0
    no_activity: int = 0


class TeacherClassDashboardOut(BaseModel):
    class_id: UUID
    total_students: int
    active_students_7d: int
    avg_study_time_seconds_7d: int
    avg_mastery_score: float
    completion_distribution: CompletionDistributionOut


class TeacherHeatmapPointOut(BaseModel):
    concept_id: str
    avg_score: float
    student_count: int


class TeacherClassHeatmapOut(BaseModel):
    class_id: UUID
    points: list[TeacherHeatmapPointOut]


class TeacherGraphMetricsOut(BaseModel):
    mapped_concepts: int = 0
    blocked_concepts: int = 0
    weak_concepts: int = 0
    mastered_concepts: int = 0
    unassessed_concepts: int = 0


class TeacherGraphConceptNodeOut(BaseModel):
    concept_id: str
    concept_label: str
    topic_id: UUID | None = None
    topic_title: str | None = None
    avg_score: float
    student_count: int = 0
    status: Literal["blocked", "needs_attention", "mastered", "unassessed"]
    prerequisite_labels: list[str] = Field(default_factory=list)
    blocking_prerequisite_labels: list[str] = Field(default_factory=list)
    recommended_action: str


class TeacherGraphSignalOut(BaseModel):
    status: Literal["repair_prerequisite", "strengthen_cluster", "advance_class", "insufficient_data"]
    headline: str
    supporting_reason: str
    focus_concept_label: str | None = None
    blocking_prerequisite_label: str | None = None
    recommended_action: str


class TeacherGraphEdgeOut(BaseModel):
    source_concept_id: str
    target_concept_id: str
    status: Literal["blocked", "ready"]


class TeacherClassGraphOut(BaseModel):
    class_id: UUID
    metrics: TeacherGraphMetricsOut
    graph_signal: TeacherGraphSignalOut
    nodes: list[TeacherGraphConceptNodeOut] = Field(default_factory=list)
    edges: list[TeacherGraphEdgeOut] = Field(default_factory=list)
    weakest_blockers: list[TeacherGraphConceptNodeOut] = Field(default_factory=list)
    ready_to_push: list[TeacherGraphConceptNodeOut] = Field(default_factory=list)


class TeacherGraphPlaybookActionOut(BaseModel):
    action_type: Literal["repair_prerequisite", "run_checkpoint", "advance_cluster", "support_students"]
    title: str
    summary: str
    severity: Severity
    target_concept_id: str | None = None
    target_concept_label: str | None = None
    target_topic_id: UUID | None = None
    target_topic_title: str | None = None
    suggested_assignment_type: AssignmentType | None = None
    suggested_intervention_type: InterventionType | None = None
    affected_student_count: int | None = None


class TeacherGraphPlaybookOut(BaseModel):
    class_id: UUID
    actions: list[TeacherGraphPlaybookActionOut] = Field(default_factory=list)


class TeacherInterventionQueueItemOut(BaseModel):
    queue_id: str
    priority: Literal["urgent", "high", "medium"]
    recommendation_type: Literal["repair_prerequisite", "reteach_concept", "repeat_risk_support", "collect_evidence"]
    headline: str
    rationale: str
    student_id: UUID | None = None
    student_name: str | None = None
    concept_id: str | None = None
    concept_label: str | None = None
    topic_id: UUID | None = None
    topic_title: str | None = None
    blocking_prerequisite_labels: list[str] = Field(default_factory=list)
    suggested_assignment_type: AssignmentType | None = None
    suggested_intervention_type: InterventionType | None = None


class TeacherInterventionQueueOut(BaseModel):
    class_id: UUID
    total_items: int = 0
    urgent_items: int = 0
    student_targeted_items: int = 0
    class_scope_items: int = 0
    items: list[TeacherInterventionQueueItemOut] = Field(default_factory=list)


class TeacherNextLessonClusterConceptOut(BaseModel):
    concept_id: str
    concept_label: str
    topic_id: UUID | None = None
    topic_title: str | None = None
    status: Literal["blocked", "needs_attention", "mastered", "unassessed"]
    avg_score: float | None = None
    student_count: int = 0
    blocking_prerequisite_labels: list[str] = Field(default_factory=list)
    recommended_action: str


class TeacherNextLessonClusterPlanOut(BaseModel):
    class_id: UUID
    plan_status: Literal["repair_first", "stabilize_cluster", "advance_cluster", "collect_evidence"]
    headline: str
    rationale: str
    repair_first: list[TeacherNextLessonClusterConceptOut] = Field(default_factory=list)
    teach_next: list[TeacherNextLessonClusterConceptOut] = Field(default_factory=list)
    watchlist: list[TeacherNextLessonClusterConceptOut] = Field(default_factory=list)
    suggested_actions: list[TeacherGraphPlaybookActionOut] = Field(default_factory=list)


class TeacherExportSectionOut(BaseModel):
    title: str
    items: list[str] = Field(default_factory=list)


class TeacherExportOut(BaseModel):
    export_kind: Literal["next_cluster_plan", "student_focus", "class_briefing", "concept_compare"]
    class_id: UUID
    class_name: str
    subject: Subject
    sss_level: SSSLevel
    term: Literal[1, 2, 3]
    title: str
    subtitle: str
    generated_at: datetime
    file_name: str
    share_text: str
    markdown: str
    sections: list[TeacherExportSectionOut] = Field(default_factory=list)
    student_id: UUID | None = None
    student_name: str | None = None
    concept_id: str | None = None
    concept_label: str | None = None


class TeacherConceptStudentOut(BaseModel):
    student_id: UUID
    student_name: str
    concept_score: float | None = None
    overall_mastery_score: float | None = None
    status: Literal["blocked", "needs_attention", "mastered", "unassessed"]
    blocking_prerequisite_labels: list[str] = Field(default_factory=list)
    recent_activity_count_7d: int = 0
    recent_study_time_seconds_7d: int = 0
    recommended_action: str
    last_evaluated_at: datetime | None = None


class TeacherConceptStudentDrilldownOut(BaseModel):
    class_id: UUID
    concept_id: str
    concept_label: str
    topic_id: UUID | None = None
    topic_title: str | None = None
    students: list[TeacherConceptStudentOut] = Field(default_factory=list)


class TeacherAlertOut(BaseModel):
    alert_type: Literal["inactivity", "rapid_decline", "prereq_failure"]
    severity: Severity
    student_id: UUID
    message: str
    generated_at: datetime


class TeacherAlertsOut(BaseModel):
    class_id: UUID
    alerts: list[TeacherAlertOut]


class TeacherTimelineEventOut(BaseModel):
    event_type: str
    occurred_at: datetime
    details: dict


class TeacherStudentTimelineOut(BaseModel):
    class_id: UUID
    student_id: UUID
    timeline: list[TeacherTimelineEventOut]


class TeacherConceptTrendSnapshotOut(BaseModel):
    concept_id: str
    concept_label: str
    role: Literal["focus", "prerequisite"]
    current_score: float | None = None
    last_evaluated_at: datetime | None = None


class TeacherConceptTrendEventOut(BaseModel):
    concept_id: str
    concept_label: str
    occurred_at: datetime
    delta: float
    source: str


class TeacherStudentConceptTrendOut(BaseModel):
    class_id: UUID
    student_id: UUID
    concept_id: str
    concept_label: str
    current_score: float | None = None
    last_evaluated_at: datetime | None = None
    status: Literal["blocked", "needs_attention", "mastered", "unassessed"]
    blocking_prerequisite_labels: list[str] = Field(default_factory=list)
    net_delta_30d: float = 0.0
    evidence_event_count: int = 0
    tracked_concepts: list[TeacherConceptTrendSnapshotOut] = Field(default_factory=list)
    recent_events: list[TeacherConceptTrendEventOut] = Field(default_factory=list)


class TeacherInterventionOutcomeOut(BaseModel):
    intervention_id: UUID
    student_id: UUID
    student_name: str
    intervention_type: InterventionType
    concept_id: str | None = None
    concept_label: str | None = None
    severity: Severity
    status: Literal["open", "resolved", "dismissed"]
    outcome_status: Literal["improving", "flat", "declining", "no_evidence"]
    net_mastery_delta: float = 0.0
    evidence_event_count: int = 0
    created_at: datetime
    latest_mastery_event_at: datetime | None = None
    notes: str
    action_plan: str | None = None


class TeacherInterventionOutcomeSummaryOut(BaseModel):
    class_id: UUID
    total_interventions: int = 0
    open_interventions: int = 0
    improving_interventions: int = 0
    declining_interventions: int = 0
    no_evidence_interventions: int = 0
    avg_net_mastery_delta: float = 0.0
    outcomes: list[TeacherInterventionOutcomeOut] = Field(default_factory=list)


class TeacherAssignmentOutcomeOut(BaseModel):
    assignment_id: UUID
    title: str
    assignment_type: AssignmentType
    status: Literal["assigned", "completed", "cancelled"]
    ref_id: str
    concept_id: str | None = None
    concept_label: str | None = None
    target_scope: Literal["class", "student"]
    student_id: UUID | None = None
    student_name: str | None = None
    target_student_count: int = 0
    engaged_student_count: int = 0
    evidence_event_count: int = 0
    outcome_status: Literal["improving", "flat", "declining", "no_evidence"]
    net_mastery_delta: float = 0.0
    due_at: datetime | None = None
    created_at: datetime


class TeacherAssignmentOutcomeSummaryOut(BaseModel):
    class_id: UUID
    total_assignments: int = 0
    open_assignments: int = 0
    improving_assignments: int = 0
    declining_assignments: int = 0
    no_evidence_assignments: int = 0
    avg_net_mastery_delta: float = 0.0
    outcomes: list[TeacherAssignmentOutcomeOut] = Field(default_factory=list)


class TeacherRepeatRiskConceptOut(BaseModel):
    concept_id: str
    concept_label: str
    topic_id: UUID | None = None
    topic_title: str | None = None
    status: Literal["blocked", "needs_attention"]
    concept_score: float | None = None
    blocking_prerequisite_labels: list[str] = Field(default_factory=list)


class TeacherRepeatRiskStudentOut(BaseModel):
    student_id: UUID
    student_name: str
    risk_status: Literal["repeat_blocker", "repeat_weakness"]
    blocked_concept_count: int = 0
    weak_concept_count: int = 0
    flagged_concept_count: int = 0
    overall_mastery_score: float | None = None
    recent_activity_count_7d: int = 0
    recent_study_time_seconds_7d: int = 0
    recommended_action: str
    driving_concepts: list[TeacherRepeatRiskConceptOut] = Field(default_factory=list)


class TeacherRepeatRiskSummaryOut(BaseModel):
    class_id: UUID
    at_risk_student_count: int = 0
    repeat_blocker_students: int = 0
    repeat_weakness_students: int = 0
    students: list[TeacherRepeatRiskStudentOut] = Field(default_factory=list)


class TeacherRiskMatrixConceptOut(BaseModel):
    concept_id: str
    concept_label: str
    topic_id: UUID | None = None
    topic_title: str | None = None
    status: Literal["blocked", "needs_attention", "mastered", "unassessed"]


class TeacherRiskMatrixCellOut(BaseModel):
    concept_id: str
    status: Literal["blocked", "needs_attention", "mastered", "unassessed"]
    concept_score: float | None = None
    blocking_prerequisite_labels: list[str] = Field(default_factory=list)


class TeacherRiskMatrixStudentOut(BaseModel):
    student_id: UUID
    student_name: str
    overall_mastery_score: float | None = None
    blocked_concept_count: int = 0
    weak_concept_count: int = 0
    recent_activity_count_7d: int = 0
    recent_study_time_seconds_7d: int = 0
    cells: list[TeacherRiskMatrixCellOut] = Field(default_factory=list)


class TeacherRiskMatrixOut(BaseModel):
    class_id: UUID
    concepts: list[TeacherRiskMatrixConceptOut] = Field(default_factory=list)
    students: list[TeacherRiskMatrixStudentOut] = Field(default_factory=list)


class TeacherConceptCompareSelectionOut(BaseModel):
    concept_id: str
    concept_label: str
    topic_id: UUID | None = None
    topic_title: str | None = None
    status: Literal["blocked", "needs_attention", "mastered", "unassessed"]
    avg_score: float | None = None
    student_count: int = 0
    blocking_prerequisite_labels: list[str] = Field(default_factory=list)


class TeacherConceptCompareStudentSideOut(BaseModel):
    concept_id: str
    concept_label: str
    status: Literal["blocked", "needs_attention", "mastered", "unassessed"]
    concept_score: float | None = None
    blocking_prerequisite_labels: list[str] = Field(default_factory=list)


class TeacherConceptCompareStudentOut(BaseModel):
    student_id: UUID
    student_name: str
    overall_mastery_score: float | None = None
    recent_activity_count_7d: int = 0
    recent_study_time_seconds_7d: int = 0
    stronger_side: Literal["left", "right", "tied"]
    comparison_signal: Literal["both_blocked", "left_weaker", "right_weaker", "both_ready", "mixed"]
    left: TeacherConceptCompareStudentSideOut
    right: TeacherConceptCompareStudentSideOut


class TeacherConceptCompareSummaryOut(BaseModel):
    students_compared: int = 0
    both_blocked_count: int = 0
    left_weaker_count: int = 0
    right_weaker_count: int = 0
    both_ready_count: int = 0
    avg_left_score: float | None = None
    avg_right_score: float | None = None
    recommended_focus_side: Literal["left", "right", "tie"]
    headline: str
    rationale: str


class TeacherConceptCompareOut(BaseModel):
    class_id: UUID
    left: TeacherConceptCompareSelectionOut
    right: TeacherConceptCompareSelectionOut
    summary: TeacherConceptCompareSummaryOut
    students: list[TeacherConceptCompareStudentOut] = Field(default_factory=list)


class TeacherAssignmentCreateIn(BaseModel):
    class_id: UUID | None = None
    student_id: UUID | None = None
    assignment_type: AssignmentType
    concept_id: str | None = Field(default=None, max_length=255)
    concept_label: str | None = Field(default=None, max_length=255)
    ref_id: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    instructions: str | None = Field(default=None, max_length=2000)
    subject: Subject
    sss_level: SSSLevel
    term: Literal[1, 2, 3]
    due_at: datetime | None = None


class TeacherAssignmentOut(BaseModel):
    id: UUID
    teacher_id: UUID
    class_id: UUID | None = None
    student_id: UUID | None = None
    assignment_type: AssignmentType
    concept_id: str | None = None
    concept_label: str | None = None
    ref_id: str
    title: str
    instructions: str | None = None
    subject: Subject
    sss_level: SSSLevel
    term: Literal[1, 2, 3]
    due_at: datetime | None = None
    status: Literal["assigned", "completed", "cancelled"]
    created_at: datetime
    updated_at: datetime


class TeacherBulkAssignmentCreateIn(BaseModel):
    class_id: UUID | None = None
    student_ids: list[UUID] = Field(min_length=1, max_length=500)
    assignment_type: AssignmentType
    concept_id: str | None = Field(default=None, max_length=255)
    concept_label: str | None = Field(default=None, max_length=255)
    ref_id: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    instructions: str | None = Field(default=None, max_length=2000)
    subject: Subject
    sss_level: SSSLevel
    term: Literal[1, 2, 3]
    due_at: datetime | None = None


class TeacherBulkAssignmentOut(BaseModel):
    created_count: int
    student_ids: list[UUID]
    assignment_ids: list[UUID]


class TeacherInterventionCreateIn(BaseModel):
    class_id: UUID | None = None
    student_id: UUID
    intervention_type: InterventionType
    concept_id: str | None = Field(default=None, max_length=255)
    concept_label: str | None = Field(default=None, max_length=255)
    severity: Severity = "medium"
    subject: Subject
    sss_level: SSSLevel
    term: Literal[1, 2, 3]
    notes: str = Field(min_length=1, max_length=2000)
    action_plan: str | None = Field(default=None, max_length=2000)


class TeacherBulkInterventionCreateIn(BaseModel):
    class_id: UUID | None = None
    student_ids: list[UUID] = Field(min_length=1, max_length=500)
    intervention_type: InterventionType
    concept_id: str | None = Field(default=None, max_length=255)
    concept_label: str | None = Field(default=None, max_length=255)
    severity: Severity = "medium"
    subject: Subject
    sss_level: SSSLevel
    term: Literal[1, 2, 3]
    notes: str = Field(min_length=1, max_length=2000)
    action_plan: str | None = Field(default=None, max_length=2000)


class TeacherBulkInterventionOut(BaseModel):
    created_count: int
    student_ids: list[UUID]
    intervention_ids: list[UUID]


class TeacherInterventionUpdateIn(BaseModel):
    status: Literal["resolved", "dismissed"]


class TeacherInterventionOut(BaseModel):
    id: UUID
    teacher_id: UUID
    class_id: UUID | None = None
    student_id: UUID
    intervention_type: InterventionType
    concept_id: str | None = None
    concept_label: str | None = None
    severity: Severity
    subject: Subject
    sss_level: SSSLevel
    term: Literal[1, 2, 3]
    notes: str
    action_plan: str | None = None
    status: Literal["open", "resolved", "dismissed"]
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class TeacherPresentationOut(BaseModel):
    class_id: UUID
    class_name: str
    subject: Subject
    sss_level: SSSLevel
    term: Literal[1, 2, 3]
    generated_at: datetime
    dashboard: TeacherClassDashboardOut
    graph_summary: TeacherClassGraphOut
    intervention_queue: TeacherInterventionQueueOut
    next_cluster_plan: TeacherNextLessonClusterPlanOut
    assignment_outcomes: TeacherAssignmentOutcomeSummaryOut
    intervention_outcomes: TeacherInterventionOutcomeSummaryOut
    briefing: TeacherExportOut
