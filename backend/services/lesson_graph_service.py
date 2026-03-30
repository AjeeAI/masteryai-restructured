from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from statistics import mean
from uuid import UUID

from sqlalchemy.orm import Session

from backend.repositories.diagnostic_repo import DiagnosticRepository
from backend.repositories.graph_repo import GraphRepository
from backend.schemas.graph_learning_schema import (
    GraphConceptEdgeOut,
    GraphConceptNodeOut,
    GraphNextStepOut,
    LessonGraphContextOut,
    WhyThisTopicOut,
)
from backend.schemas.learning_path_schema import PathNextIn
from backend.services.learning_path_service import learning_path_service


MASTERY_THRESHOLD = 0.7
WHY_TOPIC_CACHE_TTL_SECONDS = 300.0
_WHY_TOPIC_CACHE: dict[str, tuple[float, WhyThisTopicOut]] = {}

logger = logging.getLogger(__name__)


class LessonGraphValidationError(ValueError):
    pass


@dataclass(frozen=True)
class _TopicConcept:
    concept_id: str
    label: str
    topic_id: str | None
    topic_title: str | None


class LessonGraphService:
    @staticmethod
    def _scope_mastery_signature(
        *,
        db: Session,
        student_id: UUID,
        subject: str,
        sss_level: str,
        term: int,
    ) -> str:
        mastery_map = GraphRepository(db).get_mastery_map(
            student_id=student_id,
            subject=subject,
            sss_level=sss_level,
            term=term,
        )
        if not mastery_map:
            return "no_mastery"
        payload = json.dumps(sorted(mastery_map.items()), separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _why_topic_cache_key(
        *,
        student_id: UUID,
        subject: str,
        sss_level: str,
        term: int,
        topic_id: UUID,
        mastery_signature: str,
    ) -> str:
        return ":".join(
            [
                str(student_id),
                subject,
                sss_level,
                str(term),
                str(topic_id),
                mastery_signature,
            ]
        )

    @staticmethod
    def _read_cached_why_topic(*, cache_key: str) -> WhyThisTopicOut | None:
        entry = _WHY_TOPIC_CACHE.get(cache_key)
        if entry is None:
            return None
        created_at, payload = entry
        if (time.time() - created_at) > WHY_TOPIC_CACHE_TTL_SECONDS:
            _WHY_TOPIC_CACHE.pop(cache_key, None)
            return None
        return payload

    @staticmethod
    def _write_cached_why_topic(*, cache_key: str, payload: WhyThisTopicOut) -> WhyThisTopicOut:
        _WHY_TOPIC_CACHE[cache_key] = (time.time(), payload)
        return payload
    @staticmethod
    def _readable_concept_label(concept_id: str, *, fallback_topic_title: str | None = None) -> str:
        value = str(concept_id or "").strip()
        if not value:
            return str(fallback_topic_title or "Untitled Concept").strip()
        try:
            UUID(value)
            fallback = str(fallback_topic_title or "").strip()
            return fallback or "Topic Concept"
        except ValueError:
            pass
        token = value.rsplit(":", 1)[-1].strip().lower()
        token = re.sub(r"-(\d+)$", "", token)
        token = re.sub(r"[_-]+", " ", token)
        token = re.sub(r"\s+", " ", token).strip()
        return token.title() if token else str(fallback_topic_title or "Untitled Concept").strip()

    @staticmethod
    def _looks_uuid(value: str | None) -> bool:
        text = str(value or "").strip()
        if not text:
            return False
        try:
            UUID(text)
            return True
        except (TypeError, ValueError):
            return False

    def _scoped_graph(
        self,
        db: Session,
        *,
        student_id: UUID,
        subject: str,
        sss_level: str,
        term: int,
    ) -> tuple[dict[str, list[str]], dict[str, _TopicConcept], list[tuple[str, str]], dict[str, float]]:
        diagnostic_repo = DiagnosticRepository(db)
        if not diagnostic_repo.validate_student_scope(
            student_id=student_id,
            subject=subject,
            sss_level=sss_level,
            term=term,
        ):
            raise LessonGraphValidationError(
                "Student scope is invalid. Ensure profile, level, term, and subject enrollment are correct."
            )

        rows = diagnostic_repo.get_scope_topic_concept_rows(subject=subject, sss_level=sss_level, term=term)
        mastery_map = GraphRepository(db).get_mastery_map(
            student_id=student_id,
            subject=subject,
            sss_level=sss_level,
            term=term,
        )

        topic_to_concepts: dict[str, list[str]] = {}
        concept_lookup: dict[str, _TopicConcept] = {}
        prereq_edges: set[tuple[str, str]] = set()
        ordered_concepts: list[str] = []
        seen: set[str] = set()

        for row in rows:
            topic_id = str(row.get("topic_id") or "").strip()
            topic_title = str(row.get("topic_title") or "").strip()
            concept_id = str(row.get("concept_id") or "").strip()
            if not topic_id or not concept_id:
                continue
            topic_to_concepts.setdefault(topic_id, [])
            if concept_id not in topic_to_concepts[topic_id]:
                topic_to_concepts[topic_id].append(concept_id)
            concept_lookup[concept_id] = _TopicConcept(
                concept_id=concept_id,
                label=self._readable_concept_label(concept_id, fallback_topic_title=topic_title),
                topic_id=topic_id,
                topic_title=topic_title,
            )
            if concept_id not in seen:
                seen.add(concept_id)
                ordered_concepts.append(concept_id)
            for prereq_id in [str(value).strip() for value in (row.get("prereq_concept_ids") or []) if str(value).strip()]:
                if prereq_id and prereq_id != concept_id:
                    prereq_edges.add((prereq_id, concept_id))

        if not prereq_edges:
            for index in range(1, len(ordered_concepts)):
                prereq_edges.add((ordered_concepts[index - 1], ordered_concepts[index]))

        return topic_to_concepts, concept_lookup, sorted(prereq_edges), mastery_map

    @staticmethod
    def _unlocked(prereq_edges: list[tuple[str, str]], mastery_map: dict[str, float]) -> set[str]:
        prereq_by_concept: dict[str, set[str]] = {}
        all_nodes: set[str] = set()
        for prereq, concept in prereq_edges:
            all_nodes.add(prereq)
            all_nodes.add(concept)
            prereq_by_concept.setdefault(concept, set()).add(prereq)

        unlocked: set[str] = set()
        for concept_id in all_nodes:
            prereqs = prereq_by_concept.get(concept_id, set())
            if not prereqs or all(mastery_map.get(prereq, 0.0) >= MASTERY_THRESHOLD for prereq in prereqs):
                unlocked.add(concept_id)
        return unlocked

    @staticmethod
    def _node(
        *,
        concept: _TopicConcept,
        mastery_score: float,
        role: str,
        is_unlocked: bool,
        detail: str | None = None,
        lock_reason: str | None = None,
        mastery_gap: float | None = None,
        blocking_prerequisite_labels: list[str] | None = None,
        blocking_prerequisite_topic_id: str | None = None,
        blocking_prerequisite_topic_title: str | None = None,
        recommended_action_label: str | None = None,
        recommended_action_reason: str | None = None,
        recommended_topic_id: str | None = None,
        recommended_topic_title: str | None = None,
    ) -> GraphConceptNodeOut:
        if mastery_score >= MASTERY_THRESHOLD:
            mastery_state = "demonstrated"
        elif mastery_score > 0:
            mastery_state = "needs_review"
        else:
            mastery_state = "unassessed"
        return GraphConceptNodeOut(
            concept_id=concept.concept_id,
            label=concept.label,
            topic_id=concept.topic_id,
            topic_title=concept.topic_title,
            mastery_score=round(float(mastery_score), 4),
            mastery_state=mastery_state,
            role=role,  # type: ignore[arg-type]
            is_unlocked=is_unlocked,
            detail=detail,
            lock_reason=lock_reason,
            mastery_gap=round(float(mastery_gap), 4) if mastery_gap is not None else None,
            blocking_prerequisite_labels=list(blocking_prerequisite_labels or []),
            blocking_prerequisite_topic_id=blocking_prerequisite_topic_id,
            blocking_prerequisite_topic_title=blocking_prerequisite_topic_title,
            recommended_action_label=recommended_action_label,
            recommended_action_reason=recommended_action_reason,
            recommended_topic_id=recommended_topic_id,
            recommended_topic_title=recommended_topic_title,
        )

    def get_lesson_graph_context(
        self,
        db: Session,
        *,
        student_id: UUID,
        subject: str,
        sss_level: str,
        term: int,
        topic_id: UUID,
    ) -> LessonGraphContextOut:
        topic_to_concepts, concept_lookup, prereq_edges, mastery_map = self._scoped_graph(
            db,
            student_id=student_id,
            subject=subject,
            sss_level=sss_level,
            term=term,
        )
        topic_key = str(topic_id)
        current_ids = list(topic_to_concepts.get(topic_key) or [])
        if not current_ids:
            raise LessonGraphValidationError("Topic is not available in the approved graph scope.")

        def _lookup(concept_id: str) -> _TopicConcept:
            concept = concept_lookup.get(concept_id)
            if concept is not None:
                return concept
            return _TopicConcept(
                concept_id=concept_id,
                label=self._readable_concept_label(concept_id),
                topic_id=None,
                topic_title=None,
            )

        unlocked = self._unlocked(prereq_edges, mastery_map)
        prereq_by_concept: dict[str, list[str]] = {}
        for prereq_id, concept_id in prereq_edges:
            prereq_by_concept.setdefault(concept_id, []).append(prereq_id)

        current_title = concept_lookup.get(current_ids[0]).topic_title if current_ids else None

        def _blocking_info(concept_id: str) -> tuple[list[str], str | None, str | None]:
            blockers = [
                prereq_id
                for prereq_id in prereq_by_concept.get(concept_id, [])
                if mastery_map.get(prereq_id, 0.0) < MASTERY_THRESHOLD
            ]
            if not blockers:
                return [], None, None
            weakest = min(blockers, key=lambda prereq_id: mastery_map.get(prereq_id, 0.0))
            weakest_concept = _lookup(weakest)
            return (
                [_lookup(prereq_id).label for prereq_id in blockers],
                weakest_concept.topic_id,
                weakest_concept.topic_title,
            )

        def _node_detail(
            concept_id: str,
            *,
            role: str,
            is_unlocked: bool,
        ) -> tuple[
            str,
            str | None,
            float,
            list[str],
            str | None,
            str | None,
            str | None,
            str | None,
            str | None,
            str | None,
        ]:
            blocking_labels, blocking_topic_id, blocking_topic_title = _blocking_info(concept_id)
            concept = _lookup(concept_id)
            mastery_score = mastery_map.get(concept_id, 0.0)
            mastery_gap = max(0.0, MASTERY_THRESHOLD - mastery_score)
            lock_reason = None
            recommended_action_label = None
            recommended_action_reason = None
            recommended_topic_id = None
            recommended_topic_title = None
            if role == "prerequisite":
                if mastery_map.get(concept_id, 0.0) >= MASTERY_THRESHOLD:
                    detail = f"{concept.label} already supports {current_title or 'this lesson'}."
                    recommended_action_label = "Review support concept"
                    recommended_action_reason = f"{concept.label} is already strong enough to support this lesson cluster."
                    recommended_topic_id = concept.topic_id
                    recommended_topic_title = concept.topic_title
                else:
                    detail = f"Strengthen {concept.label} to stabilize {current_title or 'the current lesson'}."
                    lock_reason = f"{current_title or 'This lesson'} stays fragile until {concept.label} crosses the mastery threshold."
                    recommended_action_label = "Repair prerequisite"
                    recommended_action_reason = f"Revisit {concept.topic_title or concept.label} and lift {concept.label} above {int(MASTERY_THRESHOLD * 100)}% mastery."
                    recommended_topic_id = concept.topic_id
                    recommended_topic_title = concept.topic_title
            elif role == "downstream":
                if blocking_labels:
                    detail = f"Locked until {', '.join(blocking_labels)} is stronger."
                    lock_reason = f"{concept.label} is locked because {', '.join(blocking_labels)} still needs more evidence."
                    recommended_action_label = "Open blocking prerequisite"
                    recommended_action_reason = (
                        f"Best repair lesson: {blocking_topic_title}."
                        if blocking_topic_title
                        else f"Strengthen {blocking_labels[0]} first."
                    )
                    recommended_topic_id = blocking_topic_id
                    recommended_topic_title = blocking_topic_title
                elif is_unlocked:
                    detail = f"{concept.label} is ready to unlock next."
                    recommended_action_label = "Open unlock lesson"
                    recommended_action_reason = f"All visible prerequisites for {concept.label} are strong enough. This node is ready now."
                    recommended_topic_id = concept.topic_id
                    recommended_topic_title = concept.topic_title
                else:
                    detail = f"{concept.label} will open once this lesson cluster is stronger."
                    lock_reason = f"{concept.label} still depends on stronger performance in the current cluster."
            else:
                if blocking_labels:
                    detail = f"This lesson still depends on {', '.join(blocking_labels)}."
                    lock_reason = f"The current lesson cluster is being slowed down by {', '.join(blocking_labels)}."
                    recommended_action_label = "Open blocking prerequisite"
                    recommended_action_reason = (
                        f"Best repair lesson: {blocking_topic_title}."
                        if blocking_topic_title
                        else f"Strengthen {blocking_labels[0]} before pushing forward."
                    )
                    recommended_topic_id = blocking_topic_id
                    recommended_topic_title = blocking_topic_title
                else:
                    detail = f"{concept.label} anchors the current lesson cluster."
                    recommended_action_label = "Stay with current lesson"
                    recommended_action_reason = f"{concept.label} is the main concept cluster for this lesson."
                    recommended_topic_id = concept.topic_id
                    recommended_topic_title = concept.topic_title
            return (
                detail,
                lock_reason,
                mastery_gap,
                blocking_labels,
                blocking_topic_id,
                blocking_topic_title,
                recommended_action_label,
                recommended_action_reason,
                recommended_topic_id,
                recommended_topic_title,
            )

        prerequisite_ids = list(
            dict.fromkeys([prereq for prereq, concept in prereq_edges if concept in current_ids])
        )
        downstream_ids = list(
            dict.fromkeys([concept for prereq, concept in prereq_edges if prereq in current_ids])
        )
        related_ids = list(dict.fromkeys(current_ids + prerequisite_ids + downstream_ids))

        def _build_graph_node(concept_id: str, *, role: str) -> GraphConceptNodeOut:
            is_node_unlocked = concept_id in unlocked
            (
                detail,
                lock_reason,
                mastery_gap,
                blocking_labels,
                blocking_topic_id,
                blocking_topic_title,
                recommended_action_label,
                recommended_action_reason,
                recommended_topic_id,
                recommended_topic_title,
            ) = _node_detail(
                concept_id,
                role=role,
                is_unlocked=is_node_unlocked,
            )
            return self._node(
                concept=_lookup(concept_id),
                mastery_score=mastery_map.get(concept_id, 0.0),
                role=role,
                is_unlocked=is_node_unlocked,
                detail=detail,
                lock_reason=lock_reason,
                mastery_gap=mastery_gap,
                blocking_prerequisite_labels=blocking_labels,
                blocking_prerequisite_topic_id=blocking_topic_id,
                blocking_prerequisite_topic_title=blocking_topic_title,
                recommended_action_label=recommended_action_label,
                recommended_action_reason=recommended_action_reason,
                recommended_topic_id=recommended_topic_id,
                recommended_topic_title=recommended_topic_title,
            )

        current_nodes = [_build_graph_node(concept_id, role="current") for concept_id in current_ids]
        prerequisite_nodes = [
            _build_graph_node(concept_id, role="prerequisite")
            for concept_id in prerequisite_ids
        ]
        downstream_nodes = [
            _build_graph_node(concept_id, role="downstream")
            for concept_id in downstream_ids
        ]
        weakest_nodes = sorted(current_nodes, key=lambda item: item.mastery_score)[:3]

        graph_nodes = [
            _build_graph_node(
                concept_id,
                role=(
                    "current"
                    if concept_id in current_ids
                    else "prerequisite"
                    if concept_id in prerequisite_ids
                    else "downstream"
                ),
            )
            for concept_id in related_ids
        ]
        graph_edges = [
            GraphConceptEdgeOut(
                source_concept_id=prereq_id,
                target_concept_id=concept_id,
                relation="PREREQ_OF",
            )
            for prereq_id, concept_id in prereq_edges
            if prereq_id in related_ids and concept_id in related_ids
        ]

        next_step = learning_path_service.calculate_next_step(
            db=db,
            payload=PathNextIn(
                student_id=student_id,
                subject=subject,  # type: ignore[arg-type]
                sss_level=sss_level,  # type: ignore[arg-type]
                term=term,
            ),
        )

        next_unlock = None
        if next_step.recommended_topic_id:
            lead_concept_id = next_step.recommended_concept_id
            lead_concept = _lookup(lead_concept_id) if lead_concept_id else None
            normalized_next_label = next_step.recommended_concept_label
            if not normalized_next_label or ":" in normalized_next_label or self._looks_uuid(normalized_next_label):
                normalized_next_label = self._readable_concept_label(
                    lead_concept_id or "",
                    fallback_topic_title=lead_concept.topic_title if lead_concept else None,
                )
            normalized_topic_title = next_step.recommended_topic_title
            if not normalized_topic_title or self._looks_uuid(normalized_topic_title):
                normalized_topic_title = lead_concept.topic_title if lead_concept else None
            next_unlock = GraphNextStepOut(
                concept_id=lead_concept_id,
                concept_label=normalized_next_label or (lead_concept.label if lead_concept else None),
                topic_id=next_step.recommended_topic_id,
                topic_title=normalized_topic_title,
                reason=next_step.reason,
            )

        topic_title = current_nodes[0].topic_title or "Current Topic"
        why_this_matters = (
            f"{topic_title} builds on "
            f"{', '.join(node.label for node in prerequisite_nodes[:2]) or 'foundational concepts'} "
            f"and unlocks "
            f"{', '.join(node.label for node in downstream_nodes[:2]) or 'the next concepts in your path'}."
        )
        overall_mastery = round(mean([mastery_map.get(concept_id, 0.0) for concept_id in current_ids]), 4)

        return LessonGraphContextOut(
            student_id=student_id,
            subject=subject,  # type: ignore[arg-type]
            sss_level=sss_level,  # type: ignore[arg-type]
            term=term,
            topic_id=topic_key,
            topic_title=topic_title,
            overall_mastery=overall_mastery,
            status="ready",
            current_concepts=current_nodes,
            prerequisite_concepts=prerequisite_nodes,
            downstream_concepts=downstream_nodes,
            weakest_concepts=weakest_nodes,
            graph_nodes=graph_nodes,
            graph_edges=graph_edges,
            next_unlock=next_unlock,
            why_this_matters=why_this_matters,
        )

    def explain_why_this_topic(
        self,
        db: Session,
        *,
        student_id: UUID,
        subject: str,
        sss_level: str,
        term: int,
        topic_id: UUID,
    ) -> WhyThisTopicOut:
        mastery_signature = self._scope_mastery_signature(
            db=db,
            student_id=student_id,
            subject=subject,
            sss_level=sss_level,
            term=term,
        )
        cache_key = self._why_topic_cache_key(
            student_id=student_id,
            subject=subject,
            sss_level=sss_level,
            term=term,
            topic_id=topic_id,
            mastery_signature=mastery_signature,
        )
        cached = self._read_cached_why_topic(cache_key=cache_key)
        if cached is not None:
            logger.info(
                "lesson.graph.why_topic.cache_hit student_id=%s topic_id=%s subject=%s sss_level=%s term=%s",
                student_id,
                topic_id,
                subject,
                sss_level,
                term,
            )
            return cached
        context = self.get_lesson_graph_context(
            db,
            student_id=student_id,
            subject=subject,
            sss_level=sss_level,
            term=term,
            topic_id=topic_id,
        )
        status = getattr(context, "status", "ready")
        unavailable_reason = getattr(context, "unavailable_reason", None)
        weakest_prereq = min(
            context.prerequisite_concepts,
            key=lambda item: item.mastery_score,
            default=None,
        )
        explanation = (
            unavailable_reason
            if status == "unavailable"
            else (
                context.why_this_matters
                or f"{context.topic_title} sits in the path because it bridges prerequisites into later topics."
            )
        )
        response = WhyThisTopicOut(
            student_id=student_id,
            subject=subject,  # type: ignore[arg-type]
            sss_level=sss_level,  # type: ignore[arg-type]
            term=term,
            topic_id=context.topic_id,
            topic_title=context.topic_title,
            status=status,
            unavailable_reason=unavailable_reason,
            explanation=explanation,
            prerequisite_labels=[item.label for item in context.prerequisite_concepts],
            unlock_labels=[item.label for item in context.downstream_concepts],
            weakest_prerequisite_label=weakest_prereq.label if weakest_prereq else None,
            recommended_next=context.next_unlock,
        )
        return self._write_cached_why_topic(cache_key=cache_key, payload=response)


lesson_graph_service = LessonGraphService()
