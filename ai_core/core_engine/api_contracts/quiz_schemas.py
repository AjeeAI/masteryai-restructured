"""Shared schemas between AI Core and backend for quiz generation."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

QuizPurpose = Literal["practice", "diagnostic", "exam_prep"]
Difficulty = Literal["easy", "medium", "hard"]
SupportedSubject = Literal["math", "english", "civic"]
SupportedLevel = Literal["SSS1", "SSS2", "SSS3"]


class QuizGenerateRequest(BaseModel):
    student_id: UUID | None = None
    subject: SupportedSubject
    sss_level: SupportedLevel
    term: Literal[1, 2, 3]
    topic_id: UUID
    purpose: QuizPurpose
    difficulty: Difficulty
    num_questions: int = Field(default=10, ge=1, le=50)


class QuestionSchema(BaseModel):
    id: UUID
    text: str
    options: list[str] | None = None
    correct_answer: str | None = None
    concept_id: str
    difficulty: Difficulty


class QuizGenerateResponse(BaseModel):
    questions: list[QuestionSchema]


class QuizInsightsResponse(BaseModel):
    insights: list[str]
