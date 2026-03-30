from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from backend.schemas.tutor_session_schema import SessionMessageOut


class InternalPreferenceOut(BaseModel):
    explanation_depth: str
    examples_first: bool
    pace: str


class InternalProfileOut(BaseModel):
    student_id: UUID
    profile_id: UUID
    sss_level: str
    term: int
    subjects: list[str]
    preferences: InternalPreferenceOut | None = None


class InternalHistoryOut(BaseModel):
    session_id: UUID
    student_id: UUID
    messages: list[SessionMessageOut]


class InternalLessonContextOut(BaseModel):
    student_id: UUID
    topic_id: UUID
    title: str
    summary: str | None = None
    context_source: Literal["personalized", "structured"] = "personalized"
    content_blocks: list[dict] = Field(default_factory=list)
    source_chunk_ids: list[str] = Field(default_factory=list)
    covered_concept_ids: list[str] = Field(default_factory=list)
    covered_concept_labels: dict[str, str] = Field(default_factory=dict)
    generation_metadata: dict = Field(default_factory=dict)


class InternalQuizAnswerIn(BaseModel):
    question_id: str = Field(min_length=1, max_length=255)
    answer: str = Field(min_length=1, max_length=255)


class InternalQuizAttemptIn(BaseModel):
    student_id: UUID
    quiz_id: UUID
    attempt_id: UUID | None = None
    subject: Literal["math", "english", "civic"]
    sss_level: Literal["SSS1", "SSS2", "SSS3"]
    term: int = Field(ge=1, le=3)
    answers: list[InternalQuizAnswerIn]
    time_taken_seconds: int = Field(ge=0)
    score: float | None = Field(default=None, ge=0, le=100)


class InternalQuizAttemptOut(BaseModel):
    attempt_id: UUID
    stored: bool
    created_at: datetime


class InternalClassRosterOut(BaseModel):
    class_id: UUID
    student_ids: list[UUID]
