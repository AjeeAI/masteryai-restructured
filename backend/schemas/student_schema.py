from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional
from uuid import UUID
from datetime import datetime
import enum

# Enums for validation
class SSSLevel(str, enum.Enum):
    SSS1 = "SSS1"
    SSS2 = "SSS2"
    SSS3 = "SSS3"

class Subject(str, enum.Enum):
    MATH = "math"
    ENGLISH = "english"
    CIVIC = "civic"

class Term(int, enum.Enum):
    TERM_1 = 1
    TERM_2 = 2
    TERM_3 = 3

class ExplanationDepth(str, enum.Enum):
    SIMPLE = "simple"
    STANDARD = "standard"
    DETAILED = "detailed"

class Pace(str, enum.Enum):
    SLOW = "slow"
    NORMAL = "normal"
    FAST = "fast"


class LearningPreferenceUpdateRequest(BaseModel):
    explanation_depth: Optional[ExplanationDepth] = None
    examples_first: Optional[bool] = None
    pace: Optional[Pace] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "explanation_depth": "standard",
                "examples_first": True,
                "pace": "normal",
            }
        }
    )


# Requests
class StudentProfileSetupRequest(BaseModel):
    student_id: UUID
    sss_level: SSSLevel
    subjects: List[Subject]
    term: Term
    preferences: Optional[LearningPreferenceUpdateRequest] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "student_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "sss_level": "SSS1",
                "subjects": ["math", "english"],
                "term": 1,
                "preferences": {
                    "explanation_depth": "standard",
                    "examples_first": True,
                    "pace": "normal",
                },
            }
        }
    )

class StudentProfileUpdateRequest(BaseModel):
    sss_level: Optional[SSSLevel] = None
    current_term: Optional[Term] = None          # API uses "current_term" for updates too
    subjects: Optional[List[Subject]] = None
    preferences: Optional[LearningPreferenceUpdateRequest] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "sss_level": "SSS2",
                "current_term": 2,
                "subjects": ["math", "civic"],
                "preferences": {
                    "explanation_depth": "detailed",
                    "examples_first": True,
                    "pace": "normal",
                },
            }
        }
    )

# Responses
class LearningPreferenceResponse(BaseModel):
    student_id: UUID
    explanation_depth: str
    examples_first: bool
    pace: str
    updated_at: datetime

class StudentProfileResponse(BaseModel):
    id: UUID
    user_id: UUID
    sss_level: str
    current_term: int                # API spec uses "current_term"
    subjects: List[str]
    preferences: Optional[LearningPreferenceResponse] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "e8e7b8f2-39a4-40a4-8f8e-3f4e2d7a1f60",
                "user_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "sss_level": "SSS1",
                "current_term": 1,
                "subjects": ["math", "english"],
                "preferences": {
                    "student_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "explanation_depth": "standard",
                    "examples_first": True,
                    "pace": "normal",
                    "updated_at": "2026-03-02T15:17:36.864Z",
                },
                "created_at": "2026-03-02T15:17:36.864Z",
                "updated_at": "2026-03-02T15:17:36.864Z",
            }
        }
    )


class StudentProfileStatusResponse(BaseModel):
    """Lightweight onboarding status for authenticated student users."""

    has_profile: bool
    user_id: UUID
