from __future__ import annotations

import uuid
from uuid import UUID

from sqlalchemy import inspect
from sqlalchemy import text
from sqlalchemy.orm import Session


class TutorSessionRepository:
    def __init__(self, db: Session):
        self.db = db

    def _tutor_sessions_columns(self) -> dict[str, dict]:
        table_info = {
            col["name"]: col
            for col in inspect(self.db.bind).get_columns("tutor_sessions")
        }
        return table_info

    def _resolve_student_profile_id(self, student_id: UUID) -> UUID | None:
        row = self.db.execute(
            text(
                """
                SELECT id
                FROM student_profiles
                WHERE student_id = :student_id
                LIMIT 1
                """
            ),
            {"student_id": student_id},
        ).first()
        return row[0] if row else None

    def create_session(self, *, student_id: UUID, subject: str, term: int) -> dict:
        session_id = uuid.uuid4()
        columns = self._tutor_sessions_columns()
        has_student_id = "student_id" in columns
        has_student_profile_id = "student_profile_id" in columns
        if not has_student_id and not has_student_profile_id:
            raise ValueError("tutor_sessions schema is missing student ownership columns.")

        requires_profile_id = has_student_profile_id and not bool(columns["student_profile_id"]["nullable"])
        student_profile_id = None
        if requires_profile_id:
            student_profile_id = self._resolve_student_profile_id(student_id)
            if student_profile_id is None:
                raise ValueError("Student profile is required before starting tutor session.")

        insert_columns = ["id", "subject", "term", "status", "started_at", "created_at", "updated_at"]
        insert_values = [":id", ":subject", ":term", "'active'", "NOW()", "NOW()", "NOW()"]

        if has_student_id:
            insert_columns.insert(1, "student_id")
            insert_values.insert(1, ":student_id")
        if has_student_profile_id:
            insert_columns.insert(1, "student_profile_id")
            insert_values.insert(1, ":student_profile_id")

        returning_cols = ["id", "subject", "term", "started_at"]
        if has_student_id:
            returning_cols.insert(1, "student_id")

        sql = f"""
                INSERT INTO tutor_sessions (
                    {", ".join(insert_columns)}
                )
                VALUES (
                    {", ".join(insert_values)}
                )
                RETURNING {", ".join(returning_cols)}
                """

        params = {
            "id": session_id,
            "student_id": student_id,
            "subject": subject,
            "term": term,
            "student_profile_id": student_profile_id,
        }

        row = self.db.execute(
            text(sql),
            params,
        ).mappings().first()
        self.db.commit()
        payload = dict(row) if row else {}
        if payload and "student_id" not in payload:
            payload["student_id"] = student_id
        return payload

    def session_exists_for_student(self, *, session_id: UUID, student_id: UUID) -> bool:
        columns = self._tutor_sessions_columns()
        if "student_id" in columns:
            sql = """
                SELECT 1
                FROM tutor_sessions
                WHERE id = :session_id
                  AND student_id = :student_id
            """
        else:
            sql = """
                SELECT 1
                FROM tutor_sessions ts
                JOIN student_profiles sp ON sp.id = ts.student_profile_id
                WHERE ts.id = :session_id
                  AND sp.student_id = :student_id
            """
        row = self.db.execute(
            text(sql),
            {"session_id": session_id, "student_id": student_id},
        ).first()
        return row is not None

    def get_session_history(self, *, session_id: UUID) -> list[dict]:
        rows = self.db.execute(
            text(
                """
                SELECT id, role, content, created_at
                FROM tutor_messages
                WHERE session_id = :session_id
                ORDER BY created_at ASC
                """
            ),
            {"session_id": session_id},
        ).mappings().all()
        return [dict(row) for row in rows]

    def add_message(self, *, session_id: UUID, role: str, content: str) -> dict:
        message_id = uuid.uuid4()
        row = self.db.execute(
            text(
                """
                INSERT INTO tutor_messages (id, session_id, role, content, created_at, updated_at)
                VALUES (:id, :session_id, :role, :content, NOW(), NOW())
                RETURNING id, session_id, role, content, created_at
                """
            ),
            {
                "id": message_id,
                "session_id": session_id,
                "role": role,
                "content": content,
            },
        ).mappings().first()
        self.db.commit()
        return dict(row) if row else {}

    def update_message_content(self, *, message_id: UUID, content: str) -> dict:
        row = self.db.execute(
            text(
                """
                UPDATE tutor_messages
                SET content = :content, updated_at = NOW()
                WHERE id = :message_id
                RETURNING id, session_id, role, content, created_at, updated_at
                """
            ),
            {
                "message_id": message_id,
                "content": content,
            },
        ).mappings().first()
        self.db.commit()
        return dict(row) if row else {}

    def end_session(
        self,
        *,
        session_id: UUID,
        student_id: UUID,
        total_tokens: int | None,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        cost_usd: float | None,
        end_reason: str | None,
    ) -> dict:
        columns = self._tutor_sessions_columns()
        if "student_id" in columns:
            ownership_filter = "student_id = :student_id"
        else:
            ownership_filter = """
                student_profile_id IN (
                    SELECT id FROM student_profiles WHERE student_id = :student_id
                )
            """

        row = self.db.execute(
            text(
                f"""
                UPDATE tutor_sessions
                SET
                    status = 'ended',
                    ended_at = NOW(),
                    duration_seconds = GREATEST(
                        0,
                        CAST(EXTRACT(EPOCH FROM (NOW() - started_at)) AS INTEGER)
                    ),
                    total_tokens = COALESCE(:total_tokens, total_tokens),
                    prompt_tokens = COALESCE(:prompt_tokens, prompt_tokens),
                    completion_tokens = COALESCE(:completion_tokens, completion_tokens),
                    cost_usd = COALESCE(:cost_usd, cost_usd),
                    end_reason = COALESCE(:end_reason, end_reason),
                    updated_at = NOW()
                WHERE id = :session_id
                  AND {ownership_filter}
                RETURNING id, status, ended_at, duration_seconds, total_tokens, prompt_tokens, completion_tokens, cost_usd
                """
            ),
            {
                "session_id": session_id,
                "student_id": student_id,
                "total_tokens": total_tokens,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "cost_usd": cost_usd,
                "end_reason": end_reason,
            },
        ).mappings().first()
        self.db.commit()
        return dict(row) if row else {}
