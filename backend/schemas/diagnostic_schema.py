from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class DiagnosticWeakConceptOut(BaseModel):
    concept_id: str
    concept_label: str
    mastery_score: float = Field(ge=0.0, le=1.0)


class DiagnosticLearningGapSummaryOut(BaseModel):
    weakest_concepts: list[DiagnosticWeakConceptOut] = Field(default_factory=list)
    blocking_prerequisite_id: str | None = None
    blocking_prerequisite_label: str | None = None
    recommended_start_topic_id: str | None = None
    recommended_start_topic_title: str | None = None
    next_best_action: str | None = None
    rationale: str | None = None
    question_count: int = Field(default=0, ge=0)
    completion_timestamp: str | None = None


class DiagnosticOptionOut(BaseModel):
    label: str
    context_title: str | None = None


class DiagnosticQuestionOut(BaseModel):
    question_id: str
    concept_id: str
    concept_label: str | None = None
    topic_id: str | None = None
    topic_title: str | None = None
    prompt: str
    options: list[str]
    option_details: list[DiagnosticOptionOut] = Field(default_factory=list)


class DiagnosticStartIn(BaseModel):
    student_id: UUID
    subject: Literal["math", "english", "civic"] = Field(..., json_schema_extra={"example": "math"})
    sss_level: Literal["SSS1", "SSS2", "SSS3"] = Field(..., json_schema_extra={"example": "SSS1"})
    term: int = Field(..., ge=1, le=3)
    num_questions: int = Field(default=10, ge=1, le=25)


class DiagnosticStartOut(BaseModel):
    diagnostic_id: UUID
    subject: Literal["math", "english", "civic"]
    sss_level: Literal["SSS1", "SSS2", "SSS3"]
    term: int = Field(ge=1, le=3)
    question_count: int = Field(ge=0)
    resumed: bool = False
    concept_targets: list[str]
    questions: list[DiagnosticQuestionOut]


class DiagnosticAnswerIn(BaseModel):
    question_id: str
    answer: str = Field(min_length=1, max_length=4)


class DiagnosticSubmitIn(BaseModel):
    diagnostic_id: UUID
    student_id: UUID
    answers: list[DiagnosticAnswerIn]


class BaselineMasteryUpdateOut(BaseModel):
    concept_id: str
    previous_score: float
    new_score: float
    delta: float


class DiagnosticSubmitOut(BaseModel):
    baseline_mastery_updates: list[BaselineMasteryUpdateOut]
    recommended_start_topic_id: str | None
    recommended_start_topic_title: str | None = None
    scope_warning: str | None = None
    weakest_concepts: list[DiagnosticWeakConceptOut] = Field(default_factory=list)
    blocking_prerequisite_id: str | None = None
    blocking_prerequisite_label: str | None = None
    learning_gap_summary: DiagnosticLearningGapSummaryOut | None = None


class DiagnosticSubjectRunOut(BaseModel):
    subject: Literal["math", "english", "civic"]
    status: Literal["pending", "in_progress", "completed"]
    diagnostic_id: UUID | None = None
    question_count: int = Field(default=0, ge=0)
    recommended_start_topic_id: str | None = None
    recommended_start_topic_title: str | None = None
    weakest_concepts: list[DiagnosticWeakConceptOut] = Field(default_factory=list)
    blocking_prerequisite_id: str | None = None
    blocking_prerequisite_label: str | None = None
    completion_timestamp: str | None = None


class DiagnosticStatusOut(BaseModel):
    student_id: UUID
    onboarding_complete: bool
    pending_subjects: list[Literal["math", "english", "civic"]] = Field(default_factory=list)
    completed_subjects: list[Literal["math", "english", "civic"]] = Field(default_factory=list)
    subject_runs: list[DiagnosticSubjectRunOut] = Field(default_factory=list)
