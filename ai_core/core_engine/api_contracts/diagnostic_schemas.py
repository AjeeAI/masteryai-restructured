from __future__ import annotations
from typing import List, Optional, Literal
from pydantic import BaseModel

# Using the same literals I see in your quiz_schemas.py
SupportedSubject = Literal["math", "english", "civic"]
SupportedLevel = Literal["SSS1", "SSS2", "SSS3"]

class DiagnosticConcept(BaseModel):
    concept_id: str
    label: str
    topic_title: Optional[str] = None

class DiagnosticGenerateRequest(BaseModel):
    subject: SupportedSubject
    sss_level: SupportedLevel
    term: Literal[1, 2, 3]
    concepts: List[DiagnosticConcept]

class DiagnosticQuestionSchema(BaseModel):
    question_id: str
    concept_id: str
    topic_id: Optional[str] = None
    topic_title: Optional[str] = None
    prompt: str
    options: List[str]
    correct_answer: str  # "A", "B", "C", or "D"

class DiagnosticGenerateResponse(BaseModel):
    questions: List[DiagnosticQuestionSchema]