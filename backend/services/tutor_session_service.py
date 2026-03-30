from __future__ import annotations

from uuid import UUID

from backend.repositories.tutor_session_repo import TutorSessionRepository
from backend.schemas.tutor_session_schema import (
    SessionMessageOut,
    TutorSessionEndIn,
    TutorSessionEndOut,
    TutorSessionHistoryOut,
    TutorSessionStartIn,
    TutorSessionStartOut,
)


class TutorSessionNotFoundError(ValueError):
    pass


class TutorSessionService:
    def __init__(self, repo: TutorSessionRepository):
        self.repo = repo

    def start_session(self, payload: TutorSessionStartIn) -> TutorSessionStartOut:
        row = self.repo.create_session(
            student_id=payload.student_id,
            subject=payload.subject,
            term=payload.term,
        )
        if not row:
            raise RuntimeError("Failed to create tutor session.")
        return TutorSessionStartOut(
            session_id=row["id"],
            student_id=row["student_id"],
            subject=row["subject"],
            term=row["term"],
            started_at=row["started_at"],
        )

    def get_history(self, *, session_id: UUID, student_id: UUID) -> TutorSessionHistoryOut:
        if not self.repo.session_exists_for_student(session_id=session_id, student_id=student_id):
            raise TutorSessionNotFoundError("Session not found for this student.")

        rows = self.repo.get_session_history(session_id=session_id)
        messages = [
            SessionMessageOut(
                id=row["id"],
                role=row["role"],
                content=row["content"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
        return TutorSessionHistoryOut(session_id=session_id, messages=messages)

    def end_session(
        self,
        *,
        session_id: UUID,
        student_id: UUID,
        payload: TutorSessionEndIn,
    ) -> TutorSessionEndOut:
        row = self.repo.end_session(
            session_id=session_id,
            student_id=student_id,
            total_tokens=payload.total_tokens,
            prompt_tokens=payload.prompt_tokens,
            completion_tokens=payload.completion_tokens,
            cost_usd=payload.cost_usd,
            end_reason=payload.end_reason,
        )
        if not row:
            raise TutorSessionNotFoundError("Session not found for this student.")

        return TutorSessionEndOut(
            session_id=row["id"],
            status=row["status"],
            ended_at=row["ended_at"],
            duration_seconds=row["duration_seconds"] or 0,
            cost_summary={
                "total_tokens": row.get("total_tokens"),
                "prompt_tokens": row.get("prompt_tokens"),
                "completion_tokens": row.get("completion_tokens"),
                "cost_usd": row.get("cost_usd"),
            },
        )
