from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class MasteryNodeOut(BaseModel):
    concept_id: str
    score: float


class PrereqEdgeOut(BaseModel):
    prerequisite_concept_id: str
    concept_id: str


class InternalGraphContextOut(BaseModel):
    student_id: UUID
    subject: Literal["math", "english", "civic"]
    sss_level: Literal["SSS1", "SSS2", "SSS3"]
    term: int
    topic_id: str | None = None
    mastery: list[MasteryNodeOut]
    prereqs: list[PrereqEdgeOut]
    unlocked_nodes: list[str]
    overall_mastery: float


class ConceptUpdateIn(BaseModel):
    concept_id: str
    is_correct: bool
    weight_change: float


class InternalGraphUpdateIn(BaseModel):
    student_id: UUID
    quiz_id: UUID | None = None
    attempt_id: UUID | None = None
    subject: Literal["math", "english", "civic"]
    sss_level: Literal["SSS1", "SSS2", "SSS3"]
    term: int = Field(ge=1, le=3)
    timestamp: datetime
    source: Literal["practice", "diagnostic", "exam_prep"]
    concept_breakdown: list[ConceptUpdateIn]


class InternalGraphUpdateOut(BaseModel):
    success: bool
    new_mastery: float
    updated_concepts: int = 0
