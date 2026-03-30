from __future__ import annotations

import logging
import re
from statistics import mean
from uuid import UUID

from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.repositories.diagnostic_repo import DiagnosticRepository
from backend.repositories.graph_repo import GraphRepository
from backend.repositories.neo4j_graph_repo import (
    Neo4jGraphConfig,
    Neo4jGraphRepository,
    Neo4jGraphRepositoryError,
)
from backend.schemas.internal_graph_schema import (
    InternalGraphContextOut,
    InternalGraphUpdateIn,
    InternalGraphUpdateOut,
    MasteryNodeOut,
    PrereqEdgeOut,
)


logger = logging.getLogger(__name__)
MASTERY_UNLOCK_THRESHOLD = 0.7


class GraphClientValidationError(ValueError):
    pass


class GraphClientService:
    @staticmethod
    def _readable_concept_label(*, concept_id: str, topic_title: str) -> str:
        value = str(concept_id or "").strip()
        if not value:
            return str(topic_title or "").strip().lower()

        try:
            UUID(value)
            return str(topic_title or "").strip().lower()
        except ValueError:
            pass

        token = value.rsplit(":", 1)[-1].strip().lower()
        token = re.sub(r"-(\d+)$", "", token)
        token = re.sub(r"[^a-z0-9]+", " ", token).strip()
        return token or str(topic_title or "").strip().lower()

    @staticmethod
    def _build_context_response(
        *,
        student_id: UUID,
        subject: str,
        sss_level: str,
        term: int,
        topic_id: str | None,
        concept_ids: list[str],
        mastery_map: dict[str, float],
        prereq_edges: list[tuple[str, str]],
    ) -> InternalGraphContextOut:
        mastery_nodes = [
            MasteryNodeOut(concept_id=concept_id, score=round(mastery_map.get(concept_id, 0.0), 4))
            for concept_id in concept_ids
        ]

        prereq_nodes = [
            PrereqEdgeOut(prerequisite_concept_id=prereq, concept_id=concept)
            for prereq, concept in prereq_edges
        ]

        prereq_by_concept: dict[str, set[str]] = {}
        for prereq, concept in prereq_edges:
            prereq_by_concept.setdefault(concept, set()).add(prereq)

        unlocked_nodes: list[str] = []
        for concept_id in concept_ids:
            prereqs = prereq_by_concept.get(concept_id, set())
            if not prereqs:
                unlocked_nodes.append(concept_id)
                continue
            if all(mastery_map.get(prereq, 0.0) >= MASTERY_UNLOCK_THRESHOLD for prereq in prereqs):
                unlocked_nodes.append(concept_id)

        overall_mastery = round(mean([node.score for node in mastery_nodes]), 4) if mastery_nodes else 0.0

        return InternalGraphContextOut(
            student_id=student_id,
            subject=subject,
            sss_level=sss_level,
            term=term,
            topic_id=topic_id,
            mastery=mastery_nodes,
            prereqs=prereq_nodes,
            unlocked_nodes=unlocked_nodes,
            overall_mastery=overall_mastery,
        )

    @staticmethod
    def _build_scope_graph_from_rows(rows: list[dict]) -> tuple[list[str], list[tuple[str, str]], list[dict]]:
        """Build ordered concept IDs, prerequisite edges, and topic bundles from mapping rows."""
        topic_bundles: dict[str, dict] = {}
        concept_ids: list[str] = []
        concept_seen: set[str] = set()
        explicit_prereqs: set[tuple[str, str]] = set()

        for row in rows:
            topic_id = str(row["topic_id"])
            topic_title = str(row.get("topic_title") or "")
            concept_id = str(row["concept_id"])
            prereq_ids = [str(value) for value in (row.get("prereq_concept_ids") or [])]

            bundle = topic_bundles.setdefault(
                topic_id,
                {
                    "topic_id": topic_id,
                    "title": topic_title,
                    "concept_ids": [],
                    "concept_labels": {},
                },
            )
            if concept_id not in bundle["concept_ids"]:
                bundle["concept_ids"].append(concept_id)
            bundle["concept_labels"][concept_id] = GraphClientService._readable_concept_label(
                concept_id=concept_id,
                topic_title=topic_title,
            )

            if concept_id not in concept_seen:
                concept_seen.add(concept_id)
                concept_ids.append(concept_id)

            for prereq_id in prereq_ids:
                normalized = prereq_id.strip()
                if normalized and normalized != concept_id:
                    explicit_prereqs.add((normalized, concept_id))

        prereq_edges = sorted(explicit_prereqs) if explicit_prereqs else GraphClientService._sequential_prereq_edges(concept_ids)
        topics = list(topic_bundles.values())
        return concept_ids, prereq_edges, topics

    @staticmethod
    def _sequential_prereq_edges(concept_ids: list[str]) -> list[tuple[str, str]]:
        if len(concept_ids) <= 1:
            return []
        return [(concept_ids[idx - 1], concept_ids[idx]) for idx in range(1, len(concept_ids))]

    @staticmethod
    def _neo4j_repo_or_none() -> Neo4jGraphRepository | None:
        if not settings.use_neo4j_graph:
            return None
        config = Neo4jGraphConfig(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
        )
        if not config.is_configured:
            return None
        return Neo4jGraphRepository(config)

    def get_student_graph_context(
        self,
        db: Session,
        *,
        student_id: UUID,
        subject: str,
        sss_level: str,
        term: int,
        topic_id: str | None = None,
    ) -> InternalGraphContextOut:
        diagnostic_repo = DiagnosticRepository(db)
        if not diagnostic_repo.validate_student_scope(
            student_id=student_id,
            subject=subject,
            sss_level=sss_level,
            term=term,
        ):
            raise GraphClientValidationError(
                "Student scope is invalid. Ensure profile, level, term, and subject enrollment are correct."
            )

        scoped_rows = diagnostic_repo.get_scope_topic_concept_rows(
            subject=subject,
            sss_level=sss_level,
            term=term,
        )
        concept_ids, prereq_edges, topics = self._build_scope_graph_from_rows(scoped_rows)

        neo_repo = self._neo4j_repo_or_none()
        if neo_repo is not None:
            try:
                neo_repo.ensure_subject_topics(subject=subject, topics=topics)
                for topic in topics:
                    neo_repo.ensure_topic_concept_links(
                        subject=subject,
                        sss_level=sss_level,
                        term=term,
                        topic_id=topic["topic_id"],
                        topic_title=topic["title"],
                        concept_ids=topic["concept_ids"],
                        concept_labels=topic.get("concept_labels", {}),
                    )
                if prereq_edges:
                    neo_repo.ensure_prerequisite_edges(edges=prereq_edges)
                else:
                    neo_repo.ensure_prerequisite_chain(concept_ids=concept_ids)
                mastery_map = neo_repo.get_mastery_map(
                    student_id=str(student_id),
                    subject=subject,
                    sss_level=sss_level,
                    term=term,
                    concept_ids=concept_ids,
                )
                persisted_edges = neo_repo.get_prerequisite_edges(concept_ids=concept_ids)
                if persisted_edges:
                    prereq_edges = persisted_edges

                return self._build_context_response(
                    student_id=student_id,
                    subject=subject,
                    sss_level=sss_level,
                    term=term,
                    topic_id=topic_id,
                    concept_ids=concept_ids,
                    mastery_map=mastery_map,
                    prereq_edges=prereq_edges,
                )
            except Neo4jGraphRepositoryError as exc:
                logger.warning("Neo4j graph context failed; falling back to Postgres graph store: %s", exc)
            finally:
                neo_repo.close()

        graph_repo = GraphRepository(db)
        mastery_map = graph_repo.get_mastery_map(
            student_id=student_id,
            subject=subject,
            sss_level=sss_level,
            term=term,
        )
        return self._build_context_response(
            student_id=student_id,
            subject=subject,
            sss_level=sss_level,
            term=term,
            topic_id=topic_id,
            concept_ids=concept_ids,
            mastery_map=mastery_map,
            prereq_edges=prereq_edges,
        )

    def push_mastery_update(self, db: Session, *, payload: InternalGraphUpdateIn) -> InternalGraphUpdateOut:
        diagnostic_repo = DiagnosticRepository(db)
        if not diagnostic_repo.validate_student_scope(
            student_id=payload.student_id,
            subject=payload.subject,
            sss_level=payload.sss_level,
            term=payload.term,
        ):
            raise GraphClientValidationError(
                "Student scope is invalid. Ensure profile, level, term, and subject enrollment are correct."
            )

        graph_repo = GraphRepository(db)
        mastery_map = graph_repo.get_mastery_map(
            student_id=payload.student_id,
            subject=payload.subject,
            sss_level=payload.sss_level,
            term=payload.term,
        )

        event_mastery: list[dict] = []
        for item in payload.concept_breakdown:
            previous = mastery_map.get(item.concept_id, 0.0)
            delta = abs(item.weight_change) if item.is_correct else -abs(item.weight_change)
            projected = previous + delta

            _, stored_new = graph_repo.upsert_mastery(
                student_id=payload.student_id,
                subject=payload.subject,
                sss_level=payload.sss_level,
                term=payload.term,
                concept_id=item.concept_id,
                new_score=projected,
                source=payload.source,
                evaluated_at=payload.timestamp,
            )
            mastery_map[item.concept_id] = stored_new
            event_mastery.append(
                {
                    "concept_id": item.concept_id,
                    "previous_score": round(previous, 4),
                    "new_score": round(stored_new, 4),
                    "delta": round(stored_new - previous, 4),
                }
            )

        graph_repo.record_update_event(
            student_id=payload.student_id,
            quiz_id=payload.quiz_id,
            attempt_id=payload.attempt_id,
            subject=payload.subject,
            sss_level=payload.sss_level,
            term=payload.term,
            source=payload.source,
            concept_breakdown=[item.model_dump() for item in payload.concept_breakdown],
            new_mastery=event_mastery,
        )
        db.commit()

        neo_repo = self._neo4j_repo_or_none()
        if neo_repo is not None:
            try:
                concept_ids = [item.concept_id for item in payload.concept_breakdown]
                neo_repo.ensure_concepts(
                    subject=payload.subject,
                    sss_level=payload.sss_level,
                    term=payload.term,
                    concept_ids=concept_ids,
                )
                for row in event_mastery:
                    neo_repo.upsert_mastery(
                        student_id=str(payload.student_id),
                        concept_id=row["concept_id"],
                        score=float(row["new_score"]),
                        source=payload.source,
                        evaluated_at=payload.timestamp,
                    )
                neo_repo.record_update_event(
                    student_id=str(payload.student_id),
                    quiz_id=str(payload.quiz_id) if payload.quiz_id else None,
                    attempt_id=str(payload.attempt_id) if payload.attempt_id else None,
                    subject=payload.subject,
                    sss_level=payload.sss_level,
                    term=payload.term,
                    source=payload.source,
                    concept_breakdown=[item.model_dump() for item in payload.concept_breakdown],
                )
            except Neo4jGraphRepositoryError as exc:
                logger.warning("Neo4j mastery mirror write failed: %s", exc)
            finally:
                neo_repo.close()

        overall_mastery = round(mean(mastery_map.values()), 4) if mastery_map else 0.0
        return InternalGraphUpdateOut(
            success=True,
            new_mastery=overall_mastery,
            updated_concepts=len(payload.concept_breakdown),
        )


graph_client_service = GraphClientService()
