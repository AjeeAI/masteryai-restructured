"""Schemas for internal RAG retrieval contract."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class InternalRagRetrieveRequest(BaseModel):
    query: str = Field(min_length=3, max_length=4000)
    subject: Literal["math", "english", "civic"]
    sss_level: Literal["SSS1", "SSS2", "SSS3"]
    term: int = Field(ge=1, le=3)
    topic_ids: list[UUID] = Field(default_factory=list)
    top_k: int = Field(default=6, ge=1, le=20)
    approved_only: bool = True
    curriculum_version_id: UUID | None = None

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        return " ".join(value.split())


class InternalRagChunkOut(BaseModel):
    chunk_id: str
    source_id: str
    text: str
    score: float
    metadata: dict


class InternalRagRetrieveResponse(BaseModel):
    chunks: list[InternalRagChunkOut]
