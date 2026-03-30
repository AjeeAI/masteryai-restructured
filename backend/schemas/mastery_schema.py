from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


MasteryView = Literal["concept", "topic"]


class ConceptMasteryOut(BaseModel):
    concept_id: str
    score: float


class TopicMasteryOut(BaseModel):
    topic_id: str
    score: float


class StreakOut(BaseModel):
    current: int
    best: int


class MasteryEvidenceSummary(BaseModel):
    demonstrated: int = 0
    needs_review: int = 0
    unassessed: int = 0


class MasteryDashboardOut(BaseModel):
    subject: Literal["math", "english", "civic"]
    view: MasteryView
    mastery: list[dict]
    streak: StreakOut
    badges: list[str]
    evidence_summary: MasteryEvidenceSummary = Field(default_factory=MasteryEvidenceSummary)


class MasterySnapshotCreate(BaseModel):
    student_id: UUID
    subject: Literal["math", "english", "civic"]
    term: Literal[1, 2, 3]
    view: MasteryView
    snapshot_date: date
    mastery_payload: list[dict] = Field(default_factory=list)
    overall_mastery: float = Field(ge=0, le=1)
    source: str = Field(default="dashboard", max_length=30)
