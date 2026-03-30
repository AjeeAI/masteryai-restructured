from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.models.prewarm_job import PrewarmJob


class PrewarmJobRepository:
    def __init__(self, db: Session):
        self.db = db

    def find_active_by_dedupe_key(self, *, job_type: str, dedupe_key: str) -> PrewarmJob | None:
        return (
            self.db.query(PrewarmJob)
            .filter(
                PrewarmJob.job_type == job_type,
                PrewarmJob.dedupe_key == dedupe_key,
                PrewarmJob.status.in_(("queued", "running")),
            )
            .order_by(PrewarmJob.created_at.desc())
            .first()
        )

    def create_job(self, *, job_type: str, dedupe_key: str, payload: dict) -> PrewarmJob:
        row = PrewarmJob(
            job_type=job_type,
            status="queued",
            dedupe_key=dedupe_key,
            payload=payload,
            attempts=0,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def claim_next_job(self) -> PrewarmJob | None:
        query = (
            self.db.query(PrewarmJob)
            .filter(PrewarmJob.status == "queued")
            .order_by(PrewarmJob.created_at.asc())
        )
        dialect_name = str(getattr(getattr(self.db.bind, "dialect", None), "name", "") or "").lower()
        if dialect_name and dialect_name != "sqlite":
            query = query.with_for_update(skip_locked=True)
        row = query.first()
        if row is None:
            return None
        row.status = "running"
        row.attempts = int(row.attempts or 0) + 1
        row.error_message = None
        row.started_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(row)
        return row

    def mark_completed(self, job: PrewarmJob) -> PrewarmJob:
        job.status = "completed"
        job.error_message = None
        job.finished_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(job)
        return job

    def mark_failed(self, job: PrewarmJob, *, error_message: str) -> PrewarmJob:
        job.status = "failed"
        job.error_message = error_message[:2000]
        job.finished_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(job)
        return job

    def requeue_running_jobs(self) -> int:
        count = (
            self.db.query(PrewarmJob)
            .filter(PrewarmJob.status == "running")
            .update(
                {
                    PrewarmJob.status: "queued",
                    PrewarmJob.error_message: None,
                    PrewarmJob.started_at: None,
                    PrewarmJob.finished_at: None,
                },
                synchronize_session=False,
            )
        )
        self.db.commit()
        return int(count or 0)

    def queue_counts(self) -> dict[str, int]:
        rows = self.db.query(PrewarmJob.status).all()
        counts = {"queued": 0, "running": 0, "completed": 0, "failed": 0}
        for (status,) in rows:
            key = str(status or "").strip().lower()
            if key in counts:
                counts[key] += 1
        return counts
