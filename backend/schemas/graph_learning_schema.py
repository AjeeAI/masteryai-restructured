from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class GraphConceptNodeOut(BaseModel):
    concept_id: str
    label: str
    topic_id: str | None = None
    topic_title: str | None = None
    mastery_score: float = Field(ge=0.0, le=1.0)
    mastery_state: Literal["demonstrated", "needs_review", "unassessed"]
    role: Literal["current", "prerequisite", "downstream", "related"]
    is_unlocked: bool = False
    detail: str | None = None
    lock_reason: str | None = None
    mastery_gap: float | None = Field(default=None, ge=0.0)
    blocking_prerequisite_labels: list[str] = Field(default_factory=list)
    blocking_prerequisite_topic_id: str | None = None
    blocking_prerequisite_topic_title: str | None = None
    recommended_action_label: str | None = None
    recommended_action_reason: str | None = None
    recommended_topic_id: str | None = None
    recommended_topic_title: str | None = None


class GraphConceptEdgeOut(BaseModel):
    source_concept_id: str
    target_concept_id: str
    relation: Literal["PREREQ_OF"]


class GraphNextStepOut(BaseModel):
    concept_id: str | None = None
    concept_label: str | None = None
    topic_id: str | None = None
    topic_title: str | None = None
    reason: str


class LessonGraphContextOut(BaseModel):
    student_id: UUID
    subject: Literal["math", "english", "civic"]
    sss_level: Literal["SSS1", "SSS2", "SSS3"]
    term: int = Field(ge=1, le=3)
    topic_id: str
    topic_title: str
    overall_mastery: float = Field(ge=0.0, le=1.0)
    status: Literal["ready", "unavailable"] = "ready"
    unavailable_reason: str | None = None
    current_concepts: list[GraphConceptNodeOut] = Field(default_factory=list)
    prerequisite_concepts: list[GraphConceptNodeOut] = Field(default_factory=list)
    downstream_concepts: list[GraphConceptNodeOut] = Field(default_factory=list)
    weakest_concepts: list[GraphConceptNodeOut] = Field(default_factory=list)
    graph_nodes: list[GraphConceptNodeOut] = Field(default_factory=list)
    graph_edges: list[GraphConceptEdgeOut] = Field(default_factory=list)
    next_unlock: GraphNextStepOut | None = None
    why_this_matters: str | None = None


class WhyThisTopicOut(BaseModel):
    student_id: UUID
    subject: Literal["math", "english", "civic"]
    sss_level: Literal["SSS1", "SSS2", "SSS3"]
    term: int = Field(ge=1, le=3)
    topic_id: str
    topic_title: str
    status: Literal["ready", "unavailable"] = "ready"
    unavailable_reason: str | None = None
    explanation: str
    prerequisite_labels: list[str] = Field(default_factory=list)
    unlock_labels: list[str] = Field(default_factory=list)
    weakest_prerequisite_label: str | None = None
    recommended_next: GraphNextStepOut | None = None
