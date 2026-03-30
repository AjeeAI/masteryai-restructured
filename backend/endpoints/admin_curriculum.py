"""Admin curriculum ingestion and version governance endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.schemas.admin_curriculum_schema import (
    ConceptInspectResponse,
    CurriculumBulkIngestRequest,
    CurriculumBulkIngestResponse,
    CurriculumIngestionStatusResponse,
    CurriculumUploadRequest,
    CurriculumUploadResponse,
    CurriculumVersionActionRequest,
    CurriculumVersionActionResponse,
    PendingApprovalsResponse,
    TopicInspectResponse,
    TopicMapPatchRequest,
)
from backend.services.admin_curriculum_service import (
    AdminCurriculumNotFoundError,
    AdminCurriculumService,
    AdminCurriculumServiceError,
    AdminCurriculumValidationError,
)
from backend.services.rag_retrieve_service import RagRetrieveServiceError

router = APIRouter(prefix="/admin/curriculum", tags=["Admin Curriculum"])


def _service(db: Session) -> AdminCurriculumService:
    return AdminCurriculumService(db)


def _require_admin(current_user) -> None:
    if getattr(current_user, "role", None) != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required.",
        )


@router.post("/upload", response_model=CurriculumUploadResponse, status_code=status.HTTP_201_CREATED)
def upload_curriculum(
    payload: CurriculumUploadRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Upload and ingest curriculum notes for one scoped subject/level/term."""
    _require_admin(current_user)
    try:
        return _service(db).upload_curriculum(payload=payload, actor_user_id=current_user.id)
    except AdminCurriculumValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except AdminCurriculumServiceError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post("/ingest-all", response_model=CurriculumBulkIngestResponse, status_code=status.HTTP_201_CREATED)
def ingest_all_curriculum(
    payload: CurriculumBulkIngestRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Bulk-ingest all supported curriculum files under one root directory.

    Files are auto-grouped by inferred scope (subject + sss_level + term) from path/name.
    Each scope is ingested using the same pipeline as `/upload`.
    """
    _require_admin(current_user)
    if payload is None:
        payload = CurriculumBulkIngestRequest()
    try:
        return _service(db).ingest_all_from_source_root(payload=payload, actor_user_id=current_user.id)
    except AdminCurriculumValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except AdminCurriculumServiceError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get("/ingestion-status", response_model=CurriculumIngestionStatusResponse)
def ingestion_status(
    job_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return ingestion run status with parsing/chunking/embedding progress."""
    _require_admin(current_user)
    return _service(db).get_ingestion_status(job_id=job_id)


@router.get("/pending-approvals", response_model=PendingApprovalsResponse)
def pending_approvals(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List curriculum versions waiting for admin approval."""
    _require_admin(current_user)
    return _service(db).get_pending_approvals()


@router.get("/topics/{topic_id}", response_model=TopicInspectResponse)
def inspect_topic(
    topic_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Inspect one topic and its concept/prerequisite mappings."""
    _require_admin(current_user)
    try:
        return _service(db).inspect_topic(topic_id=topic_id)
    except AdminCurriculumNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/concepts/{concept_id}", response_model=ConceptInspectResponse)
def inspect_concept(
    concept_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Inspect a concept node and mapped topics/prerequisites."""
    _require_admin(current_user)
    try:
        return _service(db).inspect_concept(concept_id=concept_id)
    except AdminCurriculumNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.put("/topics/{topic_id}/map", response_model=TopicInspectResponse)
def patch_topic_map(
    topic_id: UUID,
    payload: TopicMapPatchRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Manually adjust topic-to-concept mappings for one version/topic pair."""
    _require_admin(current_user)
    try:
        return _service(db).patch_topic_map(
            topic_id=topic_id,
            payload=payload,
            actor_user_id=current_user.id,
        )
    except AdminCurriculumNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except AdminCurriculumValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/versions/{version_id}/approve", response_model=CurriculumVersionActionResponse)
def approve_version(
    version_id: UUID,
    payload: CurriculumVersionActionRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Publish a curriculum version and mark its scope topics as approved."""
    _require_admin(current_user)
    if payload is None:
        payload = CurriculumVersionActionRequest()
    if payload.actor_user_id is None:
        payload.actor_user_id = current_user.id
    try:
        return _service(db).approve_version(version_id=version_id, payload=payload)
    except AdminCurriculumNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except AdminCurriculumValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except RagRetrieveServiceError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))


@router.post("/versions/{version_id}/rollback", response_model=CurriculumVersionActionResponse)
def rollback_version(
    version_id: UUID,
    payload: CurriculumVersionActionRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Rollback a curriculum version from live usage and unapprove its scope."""
    _require_admin(current_user)
    if payload is None:
        payload = CurriculumVersionActionRequest()
    if payload.actor_user_id is None:
        payload.actor_user_id = current_user.id
    try:
        return _service(db).rollback_version(version_id=version_id, payload=payload)
    except AdminCurriculumNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except AdminCurriculumValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except RagRetrieveServiceError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
