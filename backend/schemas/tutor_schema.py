from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from backend.schemas.graph_learning_schema import (
    GraphConceptEdgeOut,
    GraphConceptNodeOut,
    GraphNextStepOut,
    LessonGraphContextOut,
)
from backend.schemas.lesson_schema import TopicLessonResponse


class TutorCitationOut(BaseModel):
    source_id: str
    chunk_id: str
    snippet: str


class TutorRecommendationOut(BaseModel):
    type: str
    topic_id: str | None = None
    topic_title: str | None = None
    reason: str


class TutorChatIn(BaseModel):
    student_id: UUID
    session_id: UUID
    subject: Literal["math", "english", "civic"]
    sss_level: Literal["SSS1", "SSS2", "SSS3"]
    term: Literal[1, 2, 3]
    topic_id: UUID | None = None
    focus_concept_id: str | None = None
    focus_concept_label: str | None = None
    mode: Literal["teach", "socratic", "diagnose", "drill", "recap", "exam-practice"] | None = None
    message: str = Field(min_length=1, max_length=4000)


class TutorChatOut(BaseModel):
    assistant_message: str
    citations: list[TutorCitationOut] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    recommendations: list[TutorRecommendationOut] = Field(default_factory=list)
    mode: Literal["teach", "socratic", "diagnose", "drill", "recap", "exam-practice"] | None = None
    key_points: list[str] = Field(default_factory=list)
    concept_focus: list[str] = Field(default_factory=list)
    prerequisite_warning: str | None = None
    next_action: str | None = None
    recommended_assessment: str | None = None
    recommended_topic_title: str | None = None


class TutorQuickActionOut(BaseModel):
    id: str
    label: str
    prompt: str
    icon: str
    intent: Literal[
        "teach",
        "socratic",
        "diagnose",
        "drill",
        "recap",
        "exam-practice",
        "assessment_start",
    ]


class TutorPendingAssessmentOut(BaseModel):
    assessment_id: UUID
    question: str
    concept_id: str
    concept_label: str
    hint: str | None = None
    difficulty: str | None = None


class TutorSessionBootstrapIn(BaseModel):
    student_id: UUID
    subject: Literal["math", "english", "civic"]
    sss_level: Literal["SSS1", "SSS2", "SSS3"]
    term: Literal[1, 2, 3]
    topic_id: UUID
    session_id: UUID | None = None


class TutorSessionBootstrapOut(BaseModel):
    session_id: UUID
    session_started: bool = False
    greeting: str
    topic_id: UUID
    lesson: TopicLessonResponse
    graph_context: LessonGraphContextOut
    suggested_actions: list[TutorQuickActionOut] = Field(default_factory=list)
    pending_assessment: TutorPendingAssessmentOut | None = None
    next_unlock: GraphNextStepOut | None = None
    why_this_topic: str | None = None
    graph_nodes: list[GraphConceptNodeOut] = Field(default_factory=list)
    graph_edges: list[GraphConceptEdgeOut] = Field(default_factory=list)
    assessment_ready: bool = False


class TutorRecapIn(BaseModel):
    student_id: UUID
    session_id: UUID
    subject: Literal["math", "english", "civic"]
    sss_level: Literal["SSS1", "SSS2", "SSS3"]
    term: Literal[1, 2, 3]
    topic_id: UUID


class TutorDrillIn(BaseModel):
    student_id: UUID
    session_id: UUID
    subject: Literal["math", "english", "civic"]
    sss_level: Literal["SSS1", "SSS2", "SSS3"]
    term: Literal[1, 2, 3]
    topic_id: UUID
    difficulty: Literal["easy", "medium", "hard"] = "medium"


class TutorPrereqBridgeIn(BaseModel):
    student_id: UUID
    session_id: UUID
    subject: Literal["math", "english", "civic"]
    sss_level: Literal["SSS1", "SSS2", "SSS3"]
    term: Literal[1, 2, 3]
    topic_id: UUID


class TutorStudyPlanIn(BaseModel):
    student_id: UUID
    session_id: UUID
    subject: Literal["math", "english", "civic"]
    sss_level: Literal["SSS1", "SSS2", "SSS3"]
    term: Literal[1, 2, 3]
    topic_id: UUID
    horizon_days: int = Field(default=7, ge=1, le=21)


class TutorAssessmentStartIn(BaseModel):
    student_id: UUID
    session_id: UUID
    subject: Literal["math", "english", "civic"]
    sss_level: Literal["SSS1", "SSS2", "SSS3"]
    term: Literal[1, 2, 3]
    topic_id: UUID
    focus_concept_id: str | None = None
    focus_concept_label: str | None = None
    difficulty: Literal["easy", "medium", "hard"] = "medium"


class TutorAssessmentStartOut(BaseModel):
    assessment_id: UUID
    question: str
    concept_id: str = Field(min_length=1, max_length=255)
    concept_label: str = Field(min_length=1, max_length=255)
    ideal_answer: str = Field(min_length=1)
    hint: str | None = None
    citations: list[TutorCitationOut] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)


class TutorAssessmentSubmitIn(BaseModel):
    student_id: UUID
    session_id: UUID
    assessment_id: UUID
    subject: Literal["math", "english", "civic"]
    sss_level: Literal["SSS1", "SSS2", "SSS3"]
    term: Literal[1, 2, 3]
    topic_id: UUID
    answer: str = Field(min_length=1, max_length=2000)


class TutorAssessmentSubmitOut(BaseModel):
    assessment_id: UUID
    is_correct: bool
    score: float = Field(ge=0.0, le=1.0)
    feedback: str
    ideal_answer: str
    concept_id: str = Field(min_length=1, max_length=255)
    concept_label: str = Field(min_length=1, max_length=255)
    mastery_updated: bool
    new_mastery: float | None = Field(default=None, ge=0.0, le=1.0)
    actions: list[str] = Field(default_factory=list)
    prerequisite_warning: str | None = None
    recommended_topic_id: str | None = None
    recommended_topic_title: str | None = None
    recommended_next_concept_label: str | None = None
    graph_remediation: "TutorGraphRemediationOut | None" = None
    adaptive_action: Literal["bridge_prerequisite", "harder_checkpoint"] | None = None
    adaptive_reason: str | None = None
    adaptive_difficulty: Literal["easy", "medium", "hard"] | None = None


class TutorGraphRemediationOut(BaseModel):
    focus_concept_id: str | None = None
    focus_concept_label: str | None = None
    blocking_prerequisite_id: str | None = None
    blocking_prerequisite_label: str | None = None
    blocking_prerequisite_topic_title: str | None = None
    recommended_next_concept_id: str | None = None
    recommended_next_concept_label: str | None = None
    recommended_next_topic_id: str | None = None
    recommended_next_topic_title: str | None = None
    recommendation_reason: str | None = None


class TutorHintIn(BaseModel):
    student_id: UUID
    session_id: UUID | None = None
    quiz_id: UUID
    question_id: str = Field(min_length=1, max_length=255)
    subject: Literal["math", "english", "civic"]
    sss_level: Literal["SSS1", "SSS2", "SSS3"]
    term: Literal[1, 2, 3]
    topic_id: UUID | None = None
    message: str | None = Field(default=None, max_length=1000)


class TutorHintOut(BaseModel):
    hint: str
    strategy: str = "guided_hint"


class TutorExplainMistakeIn(BaseModel):
    student_id: UUID
    session_id: UUID | None = None
    subject: Literal["math", "english", "civic"]
    sss_level: Literal["SSS1", "SSS2", "SSS3"]
    term: Literal[1, 2, 3]
    topic_id: UUID | None = None
    question: str = Field(min_length=1, max_length=2000)
    student_answer: str = Field(min_length=1, max_length=255)
    correct_answer: str = Field(min_length=1, max_length=255)


class TutorExplainMistakeOut(BaseModel):
    explanation: str
    improvement_tip: str
