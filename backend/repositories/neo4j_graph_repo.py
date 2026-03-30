from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


class Neo4jGraphRepositoryError(RuntimeError):
    """Raised when Neo4j access fails."""


@dataclass
class Neo4jGraphConfig:
    uri: str
    user: str
    password: str

    @property
    def is_configured(self) -> bool:
        return bool(self.uri and self.user and self.password)


class Neo4jGraphRepository:
    """Small Neo4j adapter for section-3/5 graph context and mastery updates."""
    PREREQ_REL = "PREREQ_OF"
    LEGACY_PREREQ_REL = "PREREQUISITE_OF"
    LEGACY_TOPIC_CONCEPT_REL = "MAPS_TO"

    def __init__(self, config: Neo4jGraphConfig):
        self.config = config
        self._driver = None

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def _ensure_driver(self):
        if self._driver is not None:
            return self._driver

        try:
            from neo4j import GraphDatabase
        except ModuleNotFoundError as exc:
            raise Neo4jGraphRepositoryError(
                "Neo4j driver not installed. Install `neo4j` package in backend environment."
            ) from exc

        try:
            self._driver = GraphDatabase.driver(
                self.config.uri,
                auth=(self.config.user, self.config.password),
            )
            return self._driver
        except Exception as exc:
            raise Neo4jGraphRepositoryError(f"Failed to initialize Neo4j driver: {exc}") from exc

    def _run(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        params = params or {}
        driver = self._ensure_driver()
        try:
            with driver.session() as session:
                result = session.run(cypher, params)
                return [row.data() for row in result]
        except Exception as exc:
            raise Neo4jGraphRepositoryError(f"Neo4j query failed: {exc}") from exc

    def ensure_subject_topics(
        self,
        *,
        subject: str,
        topics: list[dict[str, Any]],
    ) -> None:
        if not topics:
            return
        normalized = [
            {
                "id": str(item["topic_id"]),
                "title": str(item.get("title") or "").strip().lower(),
                "sss_level": str(item.get("sss_level") or ""),
                "term": int(item.get("term") or 1),
            }
            for item in topics
        ]
        self._run(
            """
            MERGE (s:Subject {slug: $subject})
            SET s.slug = $subject
            WITH s
            UNWIND $topics AS topic_row
            MERGE (t:Topic {id: topic_row.id})
            SET t.subject = $subject,
                t.sss_level = topic_row.sss_level,
                t.term = topic_row.term,
                t.title = topic_row.title
            MERGE (s)-[:HAS_TOPIC]->(t)
            """,
            {"subject": subject, "topics": normalized},
        )

    def ensure_topic_concept_links(
        self,
        *,
        subject: str,
        sss_level: str,
        term: int,
        topic_id: str,
        topic_title: str,
        concept_ids: list[str],
        concept_labels: dict[str, str] | None = None,
    ) -> None:
        if not concept_ids:
            return
        cleaned_concept_ids = [str(concept_id) for concept_id in concept_ids if str(concept_id).strip()]
        if not cleaned_concept_ids:
            return
        normalized_labels = {
            str(concept_id).strip(): str(label).strip()
            for concept_id, label in (concept_labels or {}).items()
            if str(concept_id).strip()
        }
        self._run(
            """
            MERGE (s:Subject {slug: $subject})
            MERGE (t:Topic {id: $topic_id})
            SET t.subject = $subject, t.sss_level = $sss_level, t.term = $term, t.title = $topic_title
            MERGE (s)-[:HAS_TOPIC]->(t)
            WITH t
            UNWIND $concept_ids AS concept_id
            MERGE (c:Concept {id: concept_id})
            SET c.subject = $subject,
                c.sss_level = $sss_level,
                c.term = $term,
                c.name = coalesce($concept_labels[concept_id], c.name)
            MERGE (t)-[:COVERS]->(c)
            WITH t, c
            OPTIONAL MATCH (t)-[legacy:MAPS_TO]->(c)
            DELETE legacy
            """,
            {
                "topic_id": str(topic_id),
                "topic_title": str(topic_title or "").strip().lower(),
                "concept_ids": cleaned_concept_ids,
                "subject": subject,
                "sss_level": sss_level,
                "term": term,
                "concept_labels": normalized_labels,
            },
        )

    def ensure_concepts_with_labels(
        self,
        *,
        subject: str,
        sss_level: str,
        term: int,
        concepts: list[dict[str, Any]],
    ) -> None:
        if not concepts:
            return
        normalized_concepts = []
        for concept in concepts:
            concept_id = str(concept.get("id") or "").strip()
            if not concept_id:
                continue
            concept_name = str(concept.get("name") or "").strip()
            normalized_concepts.append({"id": concept_id, "name": concept_name})

        if not normalized_concepts:
            return

        self._run(
            """
            UNWIND $concepts AS row
            MERGE (c:Concept {id: row.id})
            SET c.subject = $subject,
                c.sss_level = $sss_level,
                c.term = $term,
                c.name = row.name
            """,
            {
                "concepts": normalized_concepts,
                "subject": subject,
                "sss_level": sss_level,
                "term": term,
            },
        )

    def remove_legacy_maps_to_edges(self) -> None:
        """Cleanup helper to remove old Topic-[:MAPS_TO]->Concept edges."""
        self._run(
            """
            MATCH (:Topic)-[r:MAPS_TO]->(:Concept)
            DELETE r
            """
        )

    def remove_legacy_prerequisite_edges(self) -> None:
        """Cleanup helper to remove old :PREREQUISITE_OF edges."""
        self._run(
            """
            MATCH (:Concept)-[r:PREREQUISITE_OF]->(:Concept)
            DELETE r
            """
        )

    def remove_legacy_relationships(self) -> None:
        self.remove_legacy_maps_to_edges()
        self.remove_legacy_prerequisite_edges()

    def normalize_topic_titles_to_lowercase(self) -> None:
        """Normalize existing Topic node titles to lowercase."""
        self._run(
            """
            MATCH (t:Topic)
            WHERE t.title IS NOT NULL
            SET t.title = toLower(t.title)
            """
        )

    def reset_curriculum_subgraph(self) -> None:
        """Remove curriculum graph nodes to allow a clean reseed."""
        self._run(
            """
            MATCH (n)
            WHERE n:Subject OR n:Topic OR n:Concept OR n:MasteryUpdateEvent OR n:Student
            DETACH DELETE n
            """
        )

    def ensure_concepts(
        self,
        *,
        subject: str,
        sss_level: str,
        term: int,
        concept_ids: list[str],
    ) -> None:
        if not concept_ids:
            return
        self._run(
            """
            UNWIND $concept_ids AS concept_id
            MERGE (c:Concept {id: concept_id})
            SET c.subject = $subject, c.sss_level = $sss_level, c.term = $term
            """,
            {
                "concept_ids": concept_ids,
                "subject": subject,
                "sss_level": sss_level,
                "term": term,
            },
        )

    def ensure_prerequisite_chain(self, *, concept_ids: list[str]) -> None:
        if len(concept_ids) <= 1:
            return
        self._run(
            """
            UNWIND range(0, size($concept_ids) - 2) AS idx
            MATCH (a:Concept {id: $concept_ids[idx]}), (b:Concept {id: $concept_ids[idx + 1]})
            MERGE (a)-[:PREREQ_OF]->(b)
            """,
            {"concept_ids": concept_ids},
        )

    def ensure_prerequisite_edges(self, *, edges: list[tuple[str, str]]) -> None:
        if not edges:
            return
        records = [
            {"from": str(source), "to": str(target)}
            for source, target in edges
            if str(source).strip() and str(target).strip() and str(source) != str(target)
        ]
        if not records:
            return
        self._run(
            """
            UNWIND $edges AS edge
            MATCH (a:Concept {id: edge.from}), (b:Concept {id: edge.to})
            MERGE (a)-[:PREREQ_OF]->(b)
            """,
            {"edges": records},
        )

    def get_prerequisite_edges(self, *, concept_ids: list[str]) -> list[tuple[str, str]]:
        if not concept_ids:
            return []
        rows = self._run(
            """
            MATCH (p:Concept)-[r:PREREQ_OF|PREREQUISITE_OF]->(c:Concept)
            WHERE p.id IN $concept_ids AND c.id IN $concept_ids
            RETURN p.id AS prerequisite_concept_id, c.id AS concept_id
            """,
            {"concept_ids": concept_ids},
        )
        return [
            (str(row["prerequisite_concept_id"]), str(row["concept_id"]))
            for row in rows
            if row.get("prerequisite_concept_id") and row.get("concept_id")
        ]

    def get_mastery_map(
        self,
        *,
        student_id: str,
        subject: str,
        sss_level: str,
        term: int,
        concept_ids: list[str] | None = None,
    ) -> dict[str, float]:
        params: dict[str, Any] = {
            "student_id": student_id,
            "subject": subject,
            "sss_level": sss_level,
            "term": term,
            "concept_ids": concept_ids or [],
            "has_filter": bool(concept_ids),
        }
        rows = self._run(
            """
            MATCH (s:Student {id: $student_id})-[r:HAS_MASTERY]->(c:Concept)
            WHERE c.subject = $subject AND c.sss_level = $sss_level AND c.term = $term
              AND ($has_filter = false OR c.id IN $concept_ids)
            RETURN c.id AS concept_id, coalesce(r.score, 0.0) AS score
            """,
            params,
        )
        return {
            str(row["concept_id"]): float(row.get("score", 0.0))
            for row in rows
            if row.get("concept_id")
        }

    def upsert_mastery(
        self,
        *,
        student_id: str,
        concept_id: str,
        score: float,
        source: str,
        evaluated_at: datetime,
    ) -> None:
        self._run(
            """
            MERGE (s:Student {id: $student_id})
            MERGE (c:Concept {id: $concept_id})
            MERGE (s)-[r:HAS_MASTERY]->(c)
            SET r.score = $score,
                r.source = $source,
                r.last_evaluated_at = $evaluated_at
            """,
            {
                "student_id": student_id,
                "concept_id": concept_id,
                "score": max(0.0, min(1.0, float(score))),
                "source": source,
                "evaluated_at": evaluated_at.isoformat(),
            },
        )

    def record_update_event(
        self,
        *,
        student_id: str,
        quiz_id: str | None,
        attempt_id: str | None,
        subject: str,
        sss_level: str,
        term: int,
        source: str,
        concept_breakdown: list[dict[str, Any]],
    ) -> None:
        self._run(
            """
            CREATE (e:MasteryUpdateEvent {
                student_id: $student_id,
                quiz_id: $quiz_id,
                attempt_id: $attempt_id,
                subject: $subject,
                sss_level: $sss_level,
                term: $term,
                source: $source,
                concept_breakdown: $concept_breakdown,
                created_at: $created_at
            })
            """,
            {
                "student_id": student_id,
                "quiz_id": quiz_id,
                "attempt_id": attempt_id,
                "subject": subject,
                "sss_level": sss_level,
                "term": term,
                "source": source,
                "concept_breakdown": concept_breakdown,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
