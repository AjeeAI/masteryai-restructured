from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal

BlockType = Literal["text", "video", "image", "example", "exercise"]

class ContentBlock(BaseModel):
    """
    Explicit schema for a lesson block. 
    This ensures the AI Core doesn't accidentally drop fields.
    """
    type: BlockType
    content: Optional[str] = None
    note: Optional[str] = ""
    value: Optional[Any] = None  # Legacy support
    url: Optional[str] = None

class LessonGenerateRequest(BaseModel):
    topic_id: str
    topic_title: str
    subject: str
    sss_level: str
    term: int
    preferences: Dict[str, str] = Field(default_factory=dict)
    mastery_gaps: List[Dict] = Field(default_factory=list)
    curriculum_context: List[str] = Field(default_factory=list)

class LessonGenerateResponse(BaseModel):
    title: str
    summary: str
    estimated_duration_minutes: int
    content_blocks: List[ContentBlock]  # Updated from List[Dict] to be explicit
    generation_metadata: Dict[str, Any]