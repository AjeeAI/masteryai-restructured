from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class TutorSessionStartIn(BaseModel):
    student_id: UUID
    subject: Literal["math", "english", "civic"]
    term: int = Field(ge=1, le=3)


class TutorSessionStartOut(BaseModel):
    session_id: UUID
    student_id: UUID
    subject: str
    term: int
    started_at: datetime


class SessionMessageOut(BaseModel):
    id: UUID
    role: Literal["student", "assistant", "system"]
    content: str
    created_at: datetime


class TutorSessionHistoryOut(BaseModel):
    session_id: UUID
    messages: list[SessionMessageOut]


class TutorSessionEndIn(BaseModel):
    total_tokens: int | None = Field(default=None, ge=0)
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    cost_usd: float | None = Field(default=None, ge=0)
    end_reason: str | None = Field(default=None, max_length=100)


class TutorSessionEndOut(BaseModel):
    session_id: UUID
    status: str
    ended_at: datetime
    duration_seconds: int
    cost_summary: dict
