"""Pydantic models for FastAPI <-> ai-core contract."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class TutorRequest(BaseModel):
    user_id: str
    role: Literal["student", "teacher", "admin"] = "student"
    sss_level: Literal["SSS1", "SSS2", "SSS3"]
    term: Literal[1, 2, 3]
    subject_id: str
    topic_id: Optional[str] = None
    mode: Literal["explain", "practice", "revise", "exam_prep"] = "explain"
    message: str
    session_id: Optional[str] = None


class Citation(BaseModel):
    source_id: str
    chunk_id: str
    snippet: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TutorResponse(BaseModel):
    assistant_message: str
    citations: List[Citation] = Field(default_factory=list)
    remediation_prereqs: List[str] = Field(default_factory=list)
    actions: List[str] = Field(default_factory=list)
    cost: Dict[str, Any] = Field(default_factory=dict)


# Section 5 aligned tutor API contract (backend <-> ai-core HTTP)
class TutorChatRequest(BaseModel):
    student_id: str
    session_id: str
    subject: Literal["math", "english", "civic"]
    sss_level: Literal["SSS1", "SSS2", "SSS3"]
    term: Literal[1, 2, 3]
    topic_id: Optional[str] = None
    focus_concept_id: Optional[str] = None
    focus_concept_label: Optional[str] = None
    mode: Optional[Literal["teach", "socratic", "diagnose", "drill", "recap", "exam-practice"]] = None
    message: str


class TutorRecommendation(BaseModel):
    type: str
    topic_id: Optional[str] = None
    topic_title: Optional[str] = None
    reason: str


class TutorChatResponse(BaseModel):
    assistant_message: str
    citations: List[Citation] = Field(default_factory=list)
    actions: List[str] = Field(default_factory=list)
    recommendations: List[TutorRecommendation] = Field(default_factory=list)
    mode: Optional[Literal["teach", "socratic", "diagnose", "drill", "recap", "exam-practice"]] = None
    key_points: List[str] = Field(default_factory=list)
    concept_focus: List[str] = Field(default_factory=list)
    prerequisite_warning: Optional[str] = None
    next_action: Optional[str] = None
    recommended_assessment: Optional[str] = None
    recommended_topic_title: Optional[str] = None


class TutorAssessmentStartRequest(BaseModel):
    student_id: str
    session_id: str
    subject: Literal["math", "english", "civic"]
    sss_level: Literal["SSS1", "SSS2", "SSS3"]
    term: Literal[1, 2, 3]
    topic_id: str
    focus_concept_id: Optional[str] = None
    focus_concept_label: Optional[str] = None
    difficulty: Literal["easy", "medium", "hard"] = "medium"


class TutorAssessmentStartResponse(BaseModel):
    question: str
    concept_id: str
    concept_label: str
    ideal_answer: str
    hint: Optional[str] = None
    citations: List[Citation] = Field(default_factory=list)
    actions: List[str] = Field(default_factory=list)


class TutorAssessmentSubmitRequest(BaseModel):
    student_id: str
    session_id: str
    assessment_id: str
    subject: Literal["math", "english", "civic"]
    sss_level: Literal["SSS1", "SSS2", "SSS3"]
    term: Literal[1, 2, 3]
    topic_id: str
    answer: str
    question: str
    concept_id: str
    concept_label: str
    ideal_answer: str


class TutorAssessmentSubmitResponse(BaseModel):
    assessment_id: str
    is_correct: bool
    score: float = Field(ge=0.0, le=1.0)
    feedback: str
    ideal_answer: str
    concept_id: str
    concept_label: str
    citations: List[Citation] = Field(default_factory=list)
    actions: List[str] = Field(default_factory=list)


class TutorHintRequest(BaseModel):
    student_id: str
    session_id: Optional[str] = None
    quiz_id: str
    question_id: str
    subject: Literal["math", "english", "civic"]
    sss_level: Literal["SSS1", "SSS2", "SSS3"]
    term: Literal[1, 2, 3]
    topic_id: Optional[str] = None
    message: Optional[str] = None


class TutorHintResponse(BaseModel):
    hint: str
    strategy: str = "guided_hint"


class TutorExplainMistakeRequest(BaseModel):
    student_id: str
    session_id: Optional[str] = None
    subject: Literal["math", "english", "civic"]
    sss_level: Literal["SSS1", "SSS2", "SSS3"]
    term: Literal[1, 2, 3]
    topic_id: Optional[str] = None
    question: str
    student_answer: str
    correct_answer: str


class TutorExplainMistakeResponse(BaseModel):
    explanation: str
    improvement_tip: str


class TutorRecapRequest(BaseModel):
    student_id: str
    session_id: str
    subject: Literal["math", "english", "civic"]
    sss_level: Literal["SSS1", "SSS2", "SSS3"]
    term: Literal[1, 2, 3]
    topic_id: str


class TutorDrillRequest(BaseModel):
    student_id: str
    session_id: str
    subject: Literal["math", "english", "civic"]
    sss_level: Literal["SSS1", "SSS2", "SSS3"]
    term: Literal[1, 2, 3]
    topic_id: str
    difficulty: Literal["easy", "medium", "hard"] = "medium"


class TutorPrereqBridgeRequest(BaseModel):
    student_id: str
    session_id: str
    subject: Literal["math", "english", "civic"]
    sss_level: Literal["SSS1", "SSS2", "SSS3"]
    term: Literal[1, 2, 3]
    topic_id: str


class TutorStudyPlanRequest(BaseModel):
    student_id: str
    session_id: str
    subject: Literal["math", "english", "civic"]
    sss_level: Literal["SSS1", "SSS2", "SSS3"]
    term: Literal[1, 2, 3]
    topic_id: str
    horizon_days: int = Field(default=7, ge=1, le=21)
