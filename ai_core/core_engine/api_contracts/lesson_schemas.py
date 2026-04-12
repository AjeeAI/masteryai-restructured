from pydantic import BaseModel
from typing import List, Optional, Dict

class LessonGenerateRequest(BaseModel):
    topic_id: str
    topic_title: str
    subject: str
    sss_level: str
    term: int
    preferences: Dict[str, str]
    mastery_gaps: List[Dict]
    curriculum_context: List[str]

class LessonGenerateResponse(BaseModel):
    title: str
    summary: str
    estimated_duration_minutes: int
    content_blocks: List[Dict]
    generation_metadata: Dict