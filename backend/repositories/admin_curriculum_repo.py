"""Repository for admin curriculum ingestion/versioning operations."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session

from backend.models.curriculum_ingestion_job import CurriculumIngestionJob
from backend.models.curriculum_topic_map import CurriculumTopicMap
from backend.models.curriculum_version import CurriculumVersion
from backend.models.subject import Subject
from backend.models.topic import Topic


class AdminCurriculumRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_subject_by_slug(self, slug: str) -> Subject | None:
        return self.db.query(Subject).filter(Subject.slug == slug).first()

    def get_curriculum_version(self, version_id: UUID) -> CurriculumVersion | None:
        return self.db.query(CurriculumVersion).filter(CurriculumVersion.id == version_id).first()

    def get_curriculum_version_by_name(self, version_name: str) -> CurriculumVersion | None:
        return (
            self.db.query(CurriculumVersion)
            .filter(func.lower(CurriculumVersion.version_name) == version_name.lower())
            .first()
        )

    def create_curriculum_version(
        self,
        *,
        version_name: str,
        subject: str,
        sss_level: str,
        term: int,
        source_root: str,
        uploaded_by: UUID | None,
        status: str,
        source_file_count: int,
        metadata_payload: dict | None = None,
    ) -> CurriculumVersion:
        row = CurriculumVersion(
            id=uuid4(),
            version_name=version_name,
            subject=subject,
            sss_level=sss_level,
            term=term,
            source_root=source_root,
            source_file_count=source_file_count,
            status=status,
            uploaded_by=uploaded_by,
            metadata_payload=metadata_payload or {},
        )
        self.db.add(row)
        self.db.flush()
        return row

    def update_curriculum_version(
        self,
        version: CurriculumVersion,
        *,
        status: str | None = None,
        approved_by: UUID | None = None,
        approved_at: datetime | None = None,
        metadata_payload: dict | None = None,
    ) -> CurriculumVersion:
        if status is not None:
            version.status = status
        if approved_by is not None:
            version.approved_by = approved_by
        if approved_at is not None:
            version.approved_at = approved_at
        if metadata_payload is not None:
            version.metadata_payload = metadata_payload
        self.db.flush()
        return version

    def create_ingestion_job(
        self,
        *,
        version_id: UUID,
        created_by: UUID | None = None,
        status: str = "queued",
        current_stage: str | None = None,
    ) -> CurriculumIngestionJob:
        row = CurriculumIngestionJob(
            id=uuid4(),
            version_id=version_id,
            status=status,
            current_stage=current_stage,
            created_by=created_by,
            started_at=datetime.now(timezone.utc),
            logs_payload=[],
        )
        self.db.add(row)
        self.db.flush()
        return row

    def get_ingestion_job(self, job_id: UUID) -> CurriculumIngestionJob | None:
        return self.db.query(CurriculumIngestionJob).filter(CurriculumIngestionJob.id == job_id).first()

    def list_ingestion_jobs(self, *, job_id: UUID | None = None) -> list[CurriculumIngestionJob]:
        query = self.db.query(CurriculumIngestionJob)
        if job_id is not None:
            query = query.filter(CurriculumIngestionJob.id == job_id)
        return query.order_by(desc(CurriculumIngestionJob.created_at)).all()

    def update_ingestion_job(
        self,
        job: CurriculumIngestionJob,
        *,
        status: str | None = None,
        progress_percent: int | None = None,
        current_stage: str | None = None,
        processed_files_count: int | None = None,
        processed_chunks_count: int | None = None,
        error_message: str | None = None,
        finished_at: datetime | None = None,
    ) -> CurriculumIngestionJob:
        if status is not None:
            job.status = status
        if progress_percent is not None:
            job.progress_percent = progress_percent
        if current_stage is not None:
            job.current_stage = current_stage
        if processed_files_count is not None:
            job.processed_files_count = processed_files_count
        if processed_chunks_count is not None:
            job.processed_chunks_count = processed_chunks_count
        if error_message is not None:
            job.error_message = error_message
        if finished_at is not None:
            job.finished_at = finished_at
        self.db.flush()
        return job

    def append_ingestion_log(
        self,
        job: CurriculumIngestionJob,
        *,
        stage: str,
        message: str,
        extra: dict | None = None,
    ) -> CurriculumIngestionJob:
        existing = list(job.logs_payload or [])
        existing.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "stage": stage,
                "message": message,
                "extra": extra or {},
            }
        )
        job.logs_payload = existing
        self.db.flush()
        return job

    def list_pending_approvals(self) -> list[CurriculumVersion]:
        return (
            self.db.query(CurriculumVersion)
            .filter(CurriculumVersion.status == "pending_approval")
            .order_by(desc(CurriculumVersion.created_at))
            .all()
        )

    def get_scope_topics(self, *, subject: str, sss_level: str, term: int) -> list[Topic]:
        return (
            self.db.query(Topic)
            .join(Subject, Subject.id == Topic.subject_id)
            .filter(
                and_(
                    Subject.slug == subject,
                    Topic.sss_level == sss_level,
                    Topic.term == term,
                )
            )
            .order_by(Topic.title.asc())
            .all()
        )

    def get_topic_with_subject(self, topic_id: UUID) -> tuple[Topic, str] | None:
        row = (
            self.db.query(Topic, Subject.slug)
            .join(Subject, Subject.id == Topic.subject_id)
            .filter(Topic.id == topic_id)
            .first()
        )
        if not row:
            return None
        return row[0], str(row[1])

    def set_topics_version(
        self,
        *,
        topic_ids: list[UUID],
        version_id: UUID,
        is_approved: bool,
    ) -> int:
        if not topic_ids:
            return 0
        count = (
            self.db.query(Topic)
            .filter(Topic.id.in_(topic_ids))
            .update(
                {
                    Topic.curriculum_version_id: version_id,
                    Topic.is_approved: is_approved,
                },
                synchronize_session=False,
            )
        )
        self.db.flush()
        return int(count or 0)

    def get_topic_maps(self, *, topic_id: UUID, version_id: UUID | None = None) -> list[CurriculumTopicMap]:
        query = self.db.query(CurriculumTopicMap).filter(CurriculumTopicMap.topic_id == topic_id)
        if version_id is not None:
            query = query.filter(CurriculumTopicMap.version_id == version_id)
        return query.order_by(CurriculumTopicMap.created_at.desc()).all()

    def upsert_topic_map(
        self,
        *,
        version_id: UUID,
        topic_id: UUID,
        concept_id: str,
        prereq_concept_ids: list[str],
        confidence: float,
        is_manual_override: bool,
        created_by: UUID | None,
    ) -> CurriculumTopicMap:
        existing = (
            self.db.query(CurriculumTopicMap)
            .filter(
                and_(
                    CurriculumTopicMap.version_id == version_id,
                    CurriculumTopicMap.topic_id == topic_id,
                    CurriculumTopicMap.concept_id == concept_id,
                )
            )
            .first()
        )
        if existing is not None:
            existing.prereq_concept_ids = prereq_concept_ids
            existing.confidence = confidence
            existing.is_manual_override = is_manual_override
            existing.created_by = created_by
            self.db.flush()
            return existing

        row = CurriculumTopicMap(
            id=uuid4(),
            version_id=version_id,
            topic_id=topic_id,
            concept_id=concept_id,
            prereq_concept_ids=prereq_concept_ids,
            confidence=confidence,
            is_manual_override=is_manual_override,
            created_by=created_by,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def get_concept_maps(self, concept_id: str) -> list[tuple[CurriculumTopicMap, Topic, str]]:
        rows = (
            self.db.query(CurriculumTopicMap, Topic, Subject.slug)
            .join(Topic, Topic.id == CurriculumTopicMap.topic_id)
            .join(Subject, Subject.id == Topic.subject_id)
            .filter(CurriculumTopicMap.concept_id == concept_id)
            .order_by(desc(CurriculumTopicMap.updated_at))
            .all()
        )
        return [(row[0], row[1], str(row[2])) for row in rows]

    def get_latest_published_version_for_scope(
        self,
        *,
        subject: str,
        sss_level: str,
        term: int,
        exclude_version_id: UUID | None = None,
    ) -> CurriculumVersion | None:
        query = self.db.query(CurriculumVersion).filter(
            and_(
                CurriculumVersion.subject == subject,
                CurriculumVersion.sss_level == sss_level,
                CurriculumVersion.term == term,
                CurriculumVersion.status == "published",
            )
        )
        if exclude_version_id is not None:
            query = query.filter(CurriculumVersion.id != exclude_version_id)
        return query.order_by(desc(CurriculumVersion.updated_at)).first()

