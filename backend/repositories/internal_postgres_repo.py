from __future__ import annotations

import uuid
from uuid import UUID

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session


class InternalPostgresRepository:
    def __init__(self, db: Session):
        self.db = db

    def _table_exists(self, table_name: str) -> bool:
        return inspect(self.db.bind).has_table(table_name)

    def _column_exists(self, table_name: str, column_name: str) -> bool:
        inspector = inspect(self.db.bind)
        if not inspector.has_table(table_name):
            return False
        return any(col["name"] == column_name for col in inspector.get_columns(table_name))

    @staticmethod
    def _readable_concept_label(concept_id: str) -> str:
        value = str(concept_id or "").strip()
        if not value:
            return "Unknown Concept"
        try:
            uuid.UUID(value)
            return value
        except ValueError:
            pass
        token = value.rsplit(":", 1)[-1].strip().lower()
        token = token.replace("_", " ").replace("-", " ")
        token = " ".join(token.split())
        return token.title() if token else value

    def get_profile_context(self, *, student_id: UUID) -> dict:
        row = self.db.execute(
            text(
                """
                SELECT id, student_id, sss_level, active_term
                FROM student_profiles
                WHERE student_id = :student_id
                """
            ),
            {"student_id": student_id},
        ).mappings().first()
        if not row:
            return {}

        profile_id = row["id"]

        subject_rows = self.db.execute(
            text(
                """
                SELECT s.slug
                FROM student_subjects ss
                JOIN subjects s ON s.id = ss.subject_id
                WHERE ss.student_profile_id = :profile_id
                ORDER BY s.slug
                """
            ),
            {"profile_id": profile_id},
        ).mappings().all()

        pref_row = self.db.execute(
            text(
                """
                SELECT explanation_depth, examples_first, pace
                FROM learning_preferences
                WHERE student_profile_id = :profile_id
                """
            ),
            {"profile_id": profile_id},
        ).mappings().first()

        return {
            "student_id": row["student_id"],
            "profile_id": row["id"],
            "sss_level": row["sss_level"],
            "term": row["active_term"],
            "subjects": [r["slug"] for r in subject_rows],
            "preferences": dict(pref_row) if pref_row else None,
        }

    def get_history(self, *, student_id: UUID, session_id: UUID) -> list[dict]:
        rows = self.db.execute(
            text(
                """
                SELECT tm.id, tm.role, tm.content, tm.created_at
                FROM tutor_messages tm
                JOIN tutor_sessions ts ON ts.id = tm.session_id
                WHERE ts.id = :session_id
                  AND ts.student_id = :student_id
                ORDER BY tm.created_at ASC
                """
            ),
            {"session_id": session_id, "student_id": student_id},
        ).mappings().all()
        return [dict(row) for row in rows]

    def get_lesson_context(self, *, student_id: UUID, topic_id: UUID) -> dict:
        if self._table_exists("personalized_lessons"):
            row = self.db.execute(
                text(
                    """
                    SELECT
                        student_id,
                        topic_id,
                        title,
                        summary,
                        'personalized' AS context_source,
                        content_blocks,
                        source_chunk_ids,
                        generation_metadata
                    FROM personalized_lessons
                    WHERE student_id = :student_id
                      AND topic_id = :topic_id
                    """
                ),
                {"student_id": student_id, "topic_id": topic_id},
            ).mappings().first()
            if row:
                return dict(row)

        lesson_row = self.db.execute(
            text(
                """
                SELECT
                    l.id AS lesson_id,
                    l.topic_id,
                    l.title,
                    l.summary,
                    t.curriculum_version_id
                FROM lessons l
                JOIN topics t ON t.id = l.topic_id
                WHERE l.topic_id = :topic_id
                LIMIT 1
                """
            ),
            {"topic_id": topic_id},
        ).mappings().first()
        if not lesson_row:
            return {}

        block_rows = self.db.execute(
            text(
                """
                SELECT block_type, content, order_index
                FROM lesson_blocks
                WHERE lesson_id = :lesson_id
                ORDER BY order_index ASC
                """
            ),
            {"lesson_id": lesson_row["lesson_id"]},
        ).mappings().all()

        content_blocks: list[dict] = []
        for block_row in block_rows:
            block_type = str(block_row.get("block_type") or "").strip().lower()
            content = dict(block_row.get("content") or {})
            if block_type in {"video", "image"}:
                url = str(content.get("url") or "").strip()
                if url:
                    content_blocks.append({"type": block_type, "url": url})
                continue

            text_value = str(content.get("text") or content.get("value") or "").strip()
            if not text_value:
                continue
            heading = str(content.get("heading") or "").strip()
            if heading:
                text_value = f"{heading}\n\n{text_value}"
            content_blocks.append({"type": block_type or "text", "value": text_value})

        concept_rows = self.db.execute(
            text(
                """
                SELECT concept_id
                FROM curriculum_topic_maps
                WHERE topic_id = :topic_id
                  AND (:version_id IS NULL OR version_id = :version_id)
                ORDER BY confidence DESC, updated_at DESC, concept_id ASC
                """
            ),
            {"topic_id": topic_id, "version_id": lesson_row.get("curriculum_version_id")},
        ).mappings().all()

        covered_concept_ids: list[str] = []
        covered_concept_labels: dict[str, str] = {}
        seen: set[str] = set()
        for concept_row in concept_rows:
            concept_id = str(concept_row.get("concept_id") or "").strip()
            if not concept_id or concept_id in seen:
                continue
            seen.add(concept_id)
            covered_concept_ids.append(concept_id)
            covered_concept_labels[concept_id] = self._readable_concept_label(concept_id)

        generation_metadata = {
            "generator_version": "structured_curriculum_v1",
            "context_source": "structured",
            "covered_concept_ids": covered_concept_ids,
            "covered_concept_labels": covered_concept_labels,
        }

        return {
            "student_id": student_id,
            "topic_id": lesson_row["topic_id"],
            "title": lesson_row["title"],
            "summary": lesson_row.get("summary"),
            "context_source": "structured",
            "content_blocks": content_blocks,
            "source_chunk_ids": [],
            "generation_metadata": generation_metadata,
        }

    def save_quiz_attempt(self, payload: dict) -> dict:
        if not self._table_exists("internal_quiz_attempts"):
            raise RuntimeError("internal_quiz_attempts table is missing. Apply Section 2 migrations.")

        attempt_id = payload.get("attempt_id") or uuid.uuid4()
        row = self.db.execute(
            text(
                """
                INSERT INTO internal_quiz_attempts (
                    attempt_id, quiz_id, student_id, subject, sss_level, term,
                    answers, time_taken_seconds, score, created_at
                )
                VALUES (
                    :attempt_id, :quiz_id, :student_id, :subject, :sss_level, :term,
                    CAST(:answers AS JSONB), :time_taken_seconds, :score, NOW()
                )
                RETURNING attempt_id, created_at
                """
            ),
            {
                "attempt_id": attempt_id,
                "quiz_id": payload["quiz_id"],
                "student_id": payload["student_id"],
                "subject": payload["subject"],
                "sss_level": payload["sss_level"],
                "term": payload["term"],
                "answers": payload["answers_json"],
                "time_taken_seconds": payload["time_taken_seconds"],
                "score": payload.get("score"),
            },
        ).mappings().first()
        self.db.commit()
        return dict(row) if row else {}

    def get_class_roster(self, *, class_id: UUID) -> list[UUID]:
        if not self._table_exists("class_enrollments"):
            return []

        status_filter = ""
        if self._column_exists("class_enrollments", "status"):
            status_filter = " AND status = 'active'"

        rows = self.db.execute(
            text(
                f"""
                SELECT student_id
                FROM class_enrollments
                WHERE class_id = :class_id
                {status_filter}
                ORDER BY student_id
                """
            ),
            {"class_id": class_id},
        ).mappings().all()
        return [row["student_id"] for row in rows]
