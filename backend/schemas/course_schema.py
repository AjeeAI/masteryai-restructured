from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from backend.schemas.diagnostic_schema import DiagnosticLearningGapSummaryOut, DiagnosticSubjectRunOut
from backend.schemas.learning_path_schema import LearningMapEdgeOut, LearningMapNodeOut, PathNextOut


class CourseBootstrapTopicOut(BaseModel):
    topic_id: str
    title: str
    description: str | None = None
    lesson_title: str | None = None
    estimated_duration_minutes: int | None = None
    lesson_ready: bool = False
    lesson_unavailable_reason: str | None = None
    sss_level: str
    term: int
    subject_id: str
    status: Literal["mastered", "current", "locked", "ready", "unmapped", "pending"] = "pending"
    mastery_score: float = Field(default=0.0, ge=0.0, le=1.0)
    concept_label: str | None = None
    graph_details: str | None = None
    is_recommended: bool = False


class CourseRecentEvidenceOut(BaseModel):
    source: str
    created_at: str
    strongest_gain_concept_label: str | None = None
    strongest_drop_concept_label: str | None = None
    summary: str


class CourseInterventionEventOut(BaseModel):
    kind: Literal["quiz", "checkpoint", "diagnostic", "exam_prep", "practice"]
    source: str
    source_label: str
    created_at: str
    summary: str
    focus_concept_label: str | None = None
    strongest_gain_concept_label: str | None = None
    strongest_drop_concept_label: str | None = None
    action_label: str


class CourseRecommendationStoryOut(BaseModel):
    status: Literal["bridge_prerequisite", "advance_to_next", "hold_current"]
    headline: str
    supporting_reason: str
    blocking_prerequisite_label: str | None = None
    next_concept_label: str | None = None
    evidence_summary: str | None = None
    action_label: str


class CourseEvidenceSummaryOut(BaseModel):
    demonstrated: int = 0
    needs_review: int = 0
    unassessed: int = 0


class CourseInitialLessonPlanOut(BaseModel):
    recommended_topic_id: str | None = None
    recommended_topic_title: str | None = None
    prerequisite_repair_label: str | None = None
    next_best_action: str | None = None
    rationale: str | None = None


class CourseBootstrapOut(BaseModel):
    student_id: UUID
    subject: Literal["math", "english", "civic"]
    sss_level: Literal["SSS1", "SSS2", "SSS3"]
    term: Literal[1, 2, 3]
    topics: list[CourseBootstrapTopicOut] = Field(default_factory=list)
    nodes: list[LearningMapNodeOut] = Field(default_factory=list)
    edges: list[LearningMapEdgeOut] = Field(default_factory=list)
    next_step: PathNextOut | None = None
    recent_evidence: CourseRecentEvidenceOut | None = None
    intervention_timeline: list[CourseInterventionEventOut] = Field(default_factory=list)
    recommendation_story: CourseRecommendationStoryOut | None = None
    evidence_summary: CourseEvidenceSummaryOut | None = None
    diagnostic_status: DiagnosticSubjectRunOut | None = None
    learning_gap_summary: DiagnosticLearningGapSummaryOut | None = None
    initial_lesson_plan: CourseInitialLessonPlanOut | None = None
    map_error: str | None = None
    warmed_topic_ids: list[str] = Field(default_factory=list)
    cache_hit_topic_ids: list[str] = Field(default_factory=list)
    failed_topic_ids: list[str] = Field(default_factory=list)
