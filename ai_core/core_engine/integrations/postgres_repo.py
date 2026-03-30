"""Postgres repository methods used by ai-core orchestration."""

from __future__ import annotations

from uuid import UUID
from typing import Any, Dict, List


class PostgresRepoError(RuntimeError):
    """Raised when Postgres query execution fails."""


class PostgresRepo:
    def __init__(self, dsn: str):
        self.dsn = (dsn or "").strip()
        if not self.dsn:
            raise PostgresRepoError("POSTGRES_DSN is required for ai-core Postgres access.")

    def _connect(self):
        try:
            import psycopg
        except ModuleNotFoundError as exc:
            raise PostgresRepoError("psycopg dependency missing in ai-core environment.") from exc

        return psycopg.connect(self.dsn)

    @staticmethod
    def _is_uuid(value: str) -> bool:
        try:
            UUID(str(value))
            return True
        except (TypeError, ValueError):
            return False

    def list_topics(self, *, subject_id: str, sss_level: str, term: int) -> List[Dict[str, Any]]:
        """Return approved topic IDs and titles for a subject/level/term scope.

        `subject_id` may be either:
        - subject UUID
        - subject slug (`math|english|civic`)
        """
        sql = """
            SELECT t.id::text AS id, t.title
            FROM topics t
            JOIN subjects s ON s.id = t.subject_id
            WHERE (
                t.subject_id::text = %s
                OR s.slug = %s
            )
              AND t.sss_level = %s
              AND t.term = %s
              AND t.is_approved = TRUE
            ORDER BY t.title ASC
        """
        normalized_subject = str(subject_id).strip().lower()
        try:
            with self._connect() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, (str(subject_id), normalized_subject, sss_level, term))
                    rows = cursor.fetchall()
        except Exception as exc:
            raise PostgresRepoError(f"Failed to list scoped topics: {exc}") from exc

        return [{"id": row[0], "title": row[1]} for row in rows]

    def get_topic_title(self, *, topic_id: str) -> str | None:
        """Return a single topic title when a valid approved topic exists."""
        if not self._is_uuid(topic_id):
            return None

        sql = """
            SELECT title
            FROM topics
            WHERE id = %s::uuid
              AND is_approved = TRUE
            LIMIT 1
        """
        try:
            with self._connect() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, (topic_id,))
                    row = cursor.fetchone()
        except Exception as exc:
            raise PostgresRepoError(f"Failed to resolve topic title: {exc}") from exc
        return str(row[0]) if row and row[0] else None

    def list_scope_concepts(
        self,
        *,
        subject: str,
        sss_level: str,
        term: int,
        topic_id: str | None = None,
        limit: int = 200,
    ) -> List[str]:
        """Return concept IDs mapped to a curriculum scope.

        Priority is confidence-based when explicit mappings exist.
        """
        scoped_topic_id = str(topic_id).strip() if topic_id else None
        if scoped_topic_id and not self._is_uuid(scoped_topic_id):
            scoped_topic_id = None

        topic_filter_sql = "AND t.id = %s::uuid" if scoped_topic_id else ""
        sql = f"""
            SELECT m.concept_id
            FROM curriculum_topic_maps m
            JOIN topics t ON t.id = m.topic_id
            JOIN subjects s ON s.id = t.subject_id
            WHERE s.slug = %s
              AND t.sss_level = %s
              AND t.term = %s
              AND t.is_approved = TRUE
              {topic_filter_sql}
            GROUP BY m.concept_id
            ORDER BY MAX(m.confidence) DESC, m.concept_id ASC
            LIMIT %s
        """

        params: list[Any] = [subject.strip().lower(), sss_level, term]
        if scoped_topic_id:
            params.append(scoped_topic_id)
        params.append(max(1, min(int(limit), 500)))

        try:
            with self._connect() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, tuple(params))
                    rows = cursor.fetchall()
        except Exception as exc:
            raise PostgresRepoError(f"Failed to list scoped concept IDs: {exc}") from exc

        return [str(row[0]) for row in rows if row and row[0]]

    def list_learning_objective_ids(self, *, topic_ids: List[str]) -> List[str]:
        """Return concept IDs mapped to supplied topic IDs."""
        if not topic_ids:
            return []

        valid_topic_ids = [str(topic_id) for topic_id in topic_ids if self._is_uuid(str(topic_id))]
        if not valid_topic_ids:
            return []

        sql = """
            SELECT DISTINCT concept_id
            FROM curriculum_topic_maps
            WHERE topic_id = ANY(%s::uuid[])
              AND concept_id IS NOT NULL
            ORDER BY concept_id ASC
        """
        try:
            with self._connect() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, (valid_topic_ids,))
                    rows = cursor.fetchall()
        except Exception as exc:
            raise PostgresRepoError(f"Failed to list learning objective IDs: {exc}") from exc

        return [str(row[0]) for row in rows if row[0]]

    def list_topic_concepts(
        self,
        *,
        topic_id: str,
    ) -> List[str]:
        """Return concept IDs mapped to a single topic."""
        return self.list_learning_objective_ids(topic_ids=[topic_id])

    def find_topic_id_for_concept(
        self,
        *,
        concept_id: str,
        subject: str,
        sss_level: str,
        term: int,
    ) -> str | None:
        """Resolve a recommended topic ID from concept mapping for a scope."""
        sql = """
            SELECT t.id::text AS topic_id
            FROM curriculum_topic_maps m
            JOIN topics t ON t.id = m.topic_id
            JOIN subjects s ON s.id = t.subject_id
            WHERE m.concept_id = %s
              AND s.slug = %s
              AND t.sss_level = %s
              AND t.term = %s
              AND t.is_approved = TRUE
            ORDER BY m.confidence DESC, m.updated_at DESC
            LIMIT 1
        """
        try:
            with self._connect() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, (concept_id, subject, sss_level, term))
                    row = cursor.fetchone()
        except Exception as exc:
            raise PostgresRepoError(f"Failed to resolve topic for concept: {exc}") from exc
        return str(row[0]) if row and row[0] else None

    def _resolve_subject_slug(self, cursor, subject_id: str) -> str:
        """Resolve subject slug from ID; fallback to provided value if already slug."""
        if not self._is_uuid(subject_id):
            return str(subject_id).strip().lower()
        sql = "SELECT slug FROM subjects WHERE id = %s::uuid LIMIT 1"
        cursor.execute(sql, (subject_id,))
        row = cursor.fetchone()
        if row and row[0]:
            return str(row[0])
        return subject_id

    def _resolve_student_scope(self, cursor, user_id: str) -> tuple[str, int]:
        """Resolve student's active learning scope; fallback to SSS1 term 1."""
        sql = """
            SELECT sss_level, active_term
            FROM student_profiles
            WHERE student_id = %s::uuid
            LIMIT 1
        """
        cursor.execute(sql, (user_id,))
        row = cursor.fetchone()
        if row:
            return str(row[0]), int(row[1])
        return "SSS1", 1

    def upsert_topic_mastery(
        self, *, user_id: str, subject_id: str, topic_id: str, mastery_delta: float
    ) -> None:
        """Upsert concept mastery row using topic ID as concept anchor."""
        upsert_sql = """
            INSERT INTO student_concept_mastery (
                student_id, subject, sss_level, term, concept_id, mastery_score, source, last_evaluated_at
            )
            VALUES (
                %s::uuid, %s, %s, %s, %s, GREATEST(0.0, LEAST(1.0, %s)), 'practice', NOW()
            )
            ON CONFLICT (student_id, subject, sss_level, term, concept_id)
            DO UPDATE
            SET mastery_score = GREATEST(
                0.0,
                LEAST(1.0, student_concept_mastery.mastery_score + EXCLUDED.mastery_score)
            ),
            source = EXCLUDED.source,
            last_evaluated_at = NOW(),
            updated_at = NOW()
        """
        try:
            with self._connect() as conn:
                with conn.cursor() as cursor:
                    subject_slug = self._resolve_subject_slug(cursor, subject_id)
                    sss_level, term = self._resolve_student_scope(cursor, user_id)
                    cursor.execute(
                        upsert_sql,
                        (
                            user_id,
                            subject_slug,
                            sss_level,
                            term,
                            topic_id,
                            float(mastery_delta),
                        ),
                    )
                conn.commit()
        except Exception as exc:
            raise PostgresRepoError(f"Failed to upsert topic mastery: {exc}") from exc
