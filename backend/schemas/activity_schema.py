from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ActivityLogCreate(BaseModel):
    student_id: UUID
    subject: Literal["math", "english", "civic"]
    term: int = Field(ge=1, le=3)
    event_type: Literal["lesson_viewed", "quiz_submitted", "mastery_check_done", "tutor_chat"]
    ref_id: str = Field(min_length=1, max_length=255)
    duration_seconds: int = Field(ge=0, le=60 * 60 * 8)


class ActivityLogOut(BaseModel):
    status: str
    message: str
    points_awarded: int


class StudentStatsOut(BaseModel):
    streak: int
    mastery_points: int
    study_time_seconds: int


class LeaderboardEntryOut(BaseModel):
    student_id: UUID
    total_mastery_points: int
    rank: int
