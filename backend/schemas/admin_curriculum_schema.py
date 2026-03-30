"""Schemas for admin curriculum ingestion and governance operations."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


SubjectLiteral = Literal["math", "english", "civic"]
SSSLevelLiteral = Literal["SSS1", "SSS2", "SSS3"]
CurriculumVersionStatus = Literal[
    "draft",
    "ingesting",
    "pending_approval",
    "approved",
    "published",
    "rolled_back",
    "failed",
]
IngestionJobStatus = Literal["queued", "parsing", "chunking", "embedding", "indexing", "completed", "failed"]


class CurriculumUploadRequest(BaseModel):
    """Admin request payload for uploading curriculum files for one scope."""

    subject: SubjectLiteral
    sss_level: SSSLevelLiteral
    term: int = Field(ge=1, le=3)
    source_root: str = Field(min_length=1, max_length=500)
    version_name: str | None = Field(default=None, min_length=3, max_length=100)

    @field_validator("source_root")
    @classmethod
    def validate_source_root(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("source_root cannot be empty")
        return normalized


class CurriculumUploadResponse(BaseModel):
    version_id: UUID
    job_id: UUID
    status: CurriculumVersionStatus
    discovered_files: int
    skipped_files: int
    processed_chunks: int


class CurriculumBulkIngestRequest(BaseModel):
    """Bulk-ingest all curriculum files found under one root directory."""

    source_root: str = Field(default="docs/SSS_NOTES_2026", min_length=1, max_length=500)

    @field_validator("source_root")
    @classmethod
    def validate_source_root(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("source_root cannot be empty")
        return normalized


class CurriculumBulkScopeResult(BaseModel):
    subject: SubjectLiteral
    sss_level: SSSLevelLiteral
    term: int
    files_count: int
    version_id: UUID | None = None
    job_id: UUID | None = None
    status: CurriculumVersionStatus | Literal["failed"]
    message: str | None = None


class CurriculumBulkIngestResponse(BaseModel):
    source_root: str
    total_supported_files: int
    total_unsupported_files: int
    total_undetected_scope_files: int
    discovered_scopes: int
    succeeded_scopes: int
    failed_scopes: int
    approve_ready_version_ids: list[UUID]
    skipped_files: list[str]
    undetected_scope_files: list[str]
    results: list[CurriculumBulkScopeResult]


class IngestionJobOut(BaseModel):
    id: UUID
    version_id: UUID
    status: IngestionJobStatus
    progress_percent: int
    current_stage: str | None = None
    processed_files_count: int
    processed_chunks_count: int
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class CurriculumIngestionStatusResponse(BaseModel):
    jobs: list[IngestionJobOut]


class CurriculumVersionOut(BaseModel):
    id: UUID
    version_name: str
    subject: SubjectLiteral
    sss_level: SSSLevelLiteral
    term: int
    source_file_count: int
    status: CurriculumVersionStatus
    created_at: datetime
    updated_at: datetime


class PendingApprovalsResponse(BaseModel):
    versions: list[CurriculumVersionOut]


class TopicMapPatchItem(BaseModel):
    concept_id: str = Field(min_length=1, max_length=128)
    prereq_concept_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    is_manual_override: bool = True


class TopicMapPatchRequest(BaseModel):
    version_id: UUID
    mappings: list[TopicMapPatchItem] = Field(min_length=1)


class TopicConceptMapOut(BaseModel):
    id: UUID
    version_id: UUID
    topic_id: UUID
    concept_id: str
    prereq_concept_ids: list[str]
    confidence: float
    is_manual_override: bool
    created_at: datetime
    updated_at: datetime


class TopicInspectResponse(BaseModel):
    topic_id: UUID
    subject: SubjectLiteral
    sss_level: SSSLevelLiteral
    term: int
    title: str
    is_approved: bool
    curriculum_version_id: UUID | None = None
    mappings: list[TopicConceptMapOut]


class ConceptInspectTopicOut(BaseModel):
    topic_id: UUID
    title: str
    subject: SubjectLiteral
    sss_level: SSSLevelLiteral
    term: int
    confidence: float


class ConceptInspectResponse(BaseModel):
    concept_id: str
    prereq_concept_ids: list[str]
    topics: list[ConceptInspectTopicOut]


class CurriculumVersionActionRequest(BaseModel):
    actor_user_id: UUID | None = None
    note: str | None = Field(default=None, max_length=500)


class CurriculumVersionActionResponse(BaseModel):
    version_id: UUID
    status: CurriculumVersionStatus
    affected_topics: int
    message: str
