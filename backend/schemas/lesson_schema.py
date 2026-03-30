"""Lesson content schemas.

Logic:
- Response matches the normalized contract for lesson delivery.
- Includes graph-backed lesson context used by the student cockpit.
"""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

BlockType = Literal["text", "video", "image", "example", "exercise"]


class ContentBlockOut(BaseModel):
    type: BlockType
    value: Any | None = None
    url: str | None = None


class LessonConceptOut(BaseModel):
    concept_id: str
    label: str
    mastery_score: float | None = Field(default=None, ge=0.0, le=1.0)
    mastery_state: Literal["demonstrated", "needs_review", "unassessed"] | None = None


class LessonNextUnlockOut(BaseModel):
    concept_id: str | None = None
    concept_label: str | None = None
    topic_id: str | None = None
    topic_title: str | None = None
    reason: str | None = None


class TopicLessonResponse(BaseModel):
    topic_id: str
    title: str
    summary: str | None = None
    estimated_duration_minutes: int | None = None
    content_blocks: list[ContentBlockOut]
    covered_concepts: list[LessonConceptOut] = Field(default_factory=list)
    prerequisites: list[LessonConceptOut] = Field(default_factory=list)
    weakest_concepts: list[LessonConceptOut] = Field(default_factory=list)
    next_unlock: LessonNextUnlockOut | None = None
    why_this_matters: str | None = None
    assessment_ready: bool = False


class LessonPrewarmIn(BaseModel):
    student_id: UUID
    subject: Literal["math", "english", "civic"]
    sss_level: Literal["SSS1", "SSS2", "SSS3"]
    term: Literal[1, 2, 3]
    topic_ids: list[UUID] = Field(min_length=1, max_length=4)


class LessonPrewarmOut(BaseModel):
    requested_topic_ids: list[str] = Field(default_factory=list)
    warmed_topic_ids: list[str] = Field(default_factory=list)
    cache_hit_topic_ids: list[str] = Field(default_factory=list)
    failed_topic_ids: list[str] = Field(default_factory=list)
    queued_job_ids: list[str] = Field(default_factory=list)
