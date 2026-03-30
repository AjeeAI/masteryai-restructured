from __future__ import annotations

import re
from statistics import mean
from uuid import UUID

from sqlalchemy.orm import Session

from backend.repositories.diagnostic_repo import DiagnosticRepository
from backend.repositories.graph_repo import GraphRepository
from backend.schemas.learning_path_schema import (
    LearningMapEdgeOut,
    LearningMapNodeOut,
    LearningMapVisualOut,
    PathNextIn,
    PathNextOut,
)


MASTERY_THRESHOLD = 0.7


class LearningPathValidationError(ValueError):
    pass


class LearningPathService:
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

    @classmethod
    def _normalize_concept_label(
        cls,
        label: str | None,
        *,
        concept_id: str | None,
        fallback_topic_title: str | None = None,
    ) -> str:
        text = str(label or "").strip()
        concept_text = str(concept_id or "").strip()
        if not text or text == concept_text or ":" in text or cls._looks_uuid(text):
            return cls._readable_concept_label(concept_text, fallback_topic_title=fallback_topic_title)
        return text

    @classmethod
    def _normalize_topic_title(cls, title: str | None, *, fallback: str | None = None) -> str | None:
        text = str(title or "").strip()
        if not text or cls._looks_uuid(text):
            fallback_text = str(fallback or "").strip()
            return fallback_text or None
        return text

    @staticmethod
    def _scope_graph_rows(
        *,
        db: Session,
        student_id: UUID,
        subject: str,
        sss_level: str,
        term: int,
    ) -> tuple[list, list[dict], dict[str, float]]:
        diagnostic_repo = DiagnosticRepository(db)
        if not diagnostic_repo.validate_student_scope(
            student_id=student_id,
            subject=subject,
            sss_level=sss_level,
            term=term,
        ):
            raise LearningPathValidationError(
                "Student scope is invalid. Ensure profile, level, term, and subject enrollment are correct."
            )

        topics = diagnostic_repo.get_scope_topics(subject=subject, sss_level=sss_level, term=term)
        if not topics:
            raise LearningPathValidationError("No approved topics found for the requested scope.")

        rows = diagnostic_repo.get_scope_topic_concept_rows(subject=subject, sss_level=sss_level, term=term)
        mastery_map = GraphRepository(db).get_mastery_map(
            student_id=student_id,
            subject=subject,
            sss_level=sss_level,
            term=term,
        )
        return topics, rows, mastery_map

    def _topic_graph(
        self,
        *,
        topics: list,
        rows: list[dict],
        mastery_map: dict[str, float],
    ) -> tuple[dict[str, list[dict]], dict[str, tuple[str, str]], dict[str, set[str]], list[tuple[str, str]]]:
        topic_lookup = {str(topic.id): topic for topic in topics}
        topic_rows: dict[str, list[dict]] = {str(topic.id): [] for topic in topics}
        concept_to_topic: dict[str, tuple[str, str]] = {}
        prereqs_by_concept: dict[str, set[str]] = {}
        unmapped_topics: list[tuple[str, str]] = []

        for row in rows:
            topic_id = str(row.get("topic_id") or "").strip()
            concept_id = str(row.get("concept_id") or "").strip()
            topic_title = str(row.get("topic_title") or "").strip()
            if not topic_id or not concept_id:
                continue
            if topic_id not in topic_rows:
                continue
            label = self._readable_concept_label(concept_id, fallback_topic_title=topic_title)
            item = {
                "concept_id": concept_id,
                "concept_label": label,
                "topic_title": topic_title,
                "score": mastery_map.get(concept_id, 0.0),
                "prereqs": [
                    str(value).strip()
                    for value in (row.get("prereq_concept_ids") or [])
                    if str(value).strip() and str(value).strip() != concept_id
                ],
            }
            topic_rows[topic_id].append(item)
            concept_to_topic[concept_id] = (topic_id, topic_title or getattr(topic_lookup.get(topic_id), "title", ""))
            prereqs_by_concept.setdefault(concept_id, set()).update(item["prereqs"])

        for topic in topics:
            topic_id = str(topic.id)
            if topic_rows[topic_id]:
                continue
            unmapped_topics.append((topic_id, str(topic.title)))

        return topic_rows, concept_to_topic, prereqs_by_concept, unmapped_topics

    def calculate_next_step(self, db: Session, payload: PathNextIn) -> PathNextOut:
        topics, rows, mastery_map = self._scope_graph_rows(
            db=db,
            student_id=payload.student_id,
            subject=payload.subject,
            sss_level=payload.sss_level,
            term=payload.term,
        )
        topic_rows, concept_to_topic, prereqs_by_concept, unmapped_topics = self._topic_graph(
            topics=topics,
            rows=rows,
            mastery_map=mastery_map,
        )
        mapped_topic_ids = [topic_id for topic_id, concept_rows in topic_rows.items() if concept_rows]
        if not mapped_topic_ids:
            raise LearningPathValidationError(
                "No curriculum concept mappings found for the requested scope. Ingest and approve mapped curriculum first."
            )
        scope_warning = None
        unmapped_topic_titles = [title for _, title in unmapped_topics]
        if unmapped_topic_titles:
            scope_warning = (
                "Some topics are not fully mapped into curriculum concepts yet and are excluded from adaptive sequencing: "
                + ", ".join(unmapped_topic_titles[:4])
                + ("." if len(unmapped_topic_titles) <= 4 else ", ...")
            )

        blocking_candidates: list[dict] = []
        weak_topic_candidates: list[dict] = []

        for topic in topics:
            topic_id = str(topic.id)
            concept_rows = topic_rows.get(topic_id, [])
            if not concept_rows:
                continue

            unmet_prereqs = []
            for concept_row in concept_rows:
                for prereq_id in concept_row["prereqs"]:
                    if mastery_map.get(prereq_id, 0.0) < MASTERY_THRESHOLD:
                        unmet_prereqs.append(prereq_id)
            unmet_prereqs = list(dict.fromkeys(unmet_prereqs))
            if unmet_prereqs:
                blocking_concept = min(
                    unmet_prereqs,
                    key=lambda concept_id: (
                        float(mastery_map.get(concept_id, 0.0)),
                        self._readable_concept_label(concept_id, fallback_topic_title=concept_to_topic.get(concept_id, (None, None))[1]),
                    ),
                )
                blocking_topic_id, blocking_topic_title = concept_to_topic.get(
                    blocking_concept,
                    (None, None),
                )
                normalized_blocking_topic_title = self._normalize_topic_title(blocking_topic_title)
                blocking_candidates.append(
                    {
                        "recommended_topic_id": blocking_topic_id,
                        "recommended_topic_title": normalized_blocking_topic_title,
                        "recommended_concept_id": blocking_concept,
                        "recommended_concept_label": self._normalize_concept_label(
                            None,
                            concept_id=blocking_concept,
                            fallback_topic_title=normalized_blocking_topic_title or blocking_topic_title,
                        ),
                        "reason": (
                            "A prerequisite concept is still weak; revisit the weakest blocking foundation before proceeding."
                        ),
                        "prereq_gaps": unmet_prereqs,
                        "prereq_gap_labels": [
                            self._readable_concept_label(
                                item,
                                fallback_topic_title=concept_to_topic.get(item, (None, None))[1],
                            )
                            for item in unmet_prereqs
                        ],
                        "score": float(mastery_map.get(blocking_concept, 0.0)),
                    }
                )
                continue

            topic_mastery = mean([float(item["score"]) for item in concept_rows]) if concept_rows else 0.0
            if topic_mastery < MASTERY_THRESHOLD:
                weakest_concept = min(concept_rows, key=lambda item: float(item["score"]))
                normalized_topic_title = self._normalize_topic_title(str(topic.title), fallback=str(topic.title))
                weak_topic_candidates.append(
                    {
                        "recommended_topic_id": topic_id,
                        "recommended_topic_title": normalized_topic_title,
                        "recommended_concept_id": str(weakest_concept["concept_id"]),
                        "recommended_concept_label": self._normalize_concept_label(
                            str(weakest_concept.get("concept_label") or ""),
                            concept_id=str(weakest_concept.get("concept_id") or ""),
                            fallback_topic_title=normalized_topic_title or str(topic.title),
                        ),
                        "reason": "Recommended next topic based on the weakest ready concept cluster still below mastery threshold.",
                        "prereq_gaps": [],
                        "prereq_gap_labels": [],
                        "score": float(weakest_concept["score"]),
                    }
                )

        if blocking_candidates:
            best_blocker = min(
                blocking_candidates,
                key=lambda item: (
                    float(item["score"]),
                    str(item["recommended_topic_title"] or ""),
                    str(item["recommended_concept_label"] or ""),
                ),
            )
            return PathNextOut(
                recommended_topic_id=best_blocker["recommended_topic_id"],
                recommended_topic_title=best_blocker["recommended_topic_title"],
                recommended_concept_id=best_blocker["recommended_concept_id"],
                recommended_concept_label=best_blocker["recommended_concept_label"],
                reason=best_blocker["reason"],
                prereq_gaps=list(best_blocker["prereq_gaps"]),
                prereq_gap_labels=list(best_blocker["prereq_gap_labels"]),
                scope_warning=scope_warning,
                unmapped_topic_titles=unmapped_topic_titles,
            )

        if weak_topic_candidates:
            best_ready_cluster = min(
                weak_topic_candidates,
                key=lambda item: (
                    float(item["score"]),
                    str(item["recommended_topic_title"] or ""),
                    str(item["recommended_concept_label"] or ""),
                ),
            )
            return PathNextOut(
                recommended_topic_id=best_ready_cluster["recommended_topic_id"],
                recommended_topic_title=best_ready_cluster["recommended_topic_title"],
                recommended_concept_id=best_ready_cluster["recommended_concept_id"],
                recommended_concept_label=best_ready_cluster["recommended_concept_label"],
                reason=best_ready_cluster["reason"],
                prereq_gaps=[],
                prereq_gap_labels=[],
                scope_warning=scope_warning,
                unmapped_topic_titles=unmapped_topic_titles,
            )

        mapped_topics = [topic for topic in topics if topic_rows.get(str(topic.id))]
        weakest_topic = min(
            mapped_topics,
            key=lambda item: mean(
                [float(row["score"]) for row in topic_rows.get(str(item.id), [])] or [1.0]
            ),
        )
        weakest_rows = topic_rows.get(str(weakest_topic.id), [])
        weakest_concept = min(weakest_rows, key=lambda item: float(item["score"])) if weakest_rows else None
        normalized_weakest_title = self._normalize_topic_title(str(weakest_topic.title), fallback=str(weakest_topic.title))
        return PathNextOut(
            recommended_topic_id=str(weakest_topic.id),
            recommended_topic_title=normalized_weakest_title,
            recommended_concept_id=str(weakest_concept["concept_id"]) if weakest_concept else None,
            recommended_concept_label=(
                self._normalize_concept_label(
                    str(weakest_concept.get("concept_label") or ""),
                    concept_id=str(weakest_concept.get("concept_id") or ""),
                    fallback_topic_title=normalized_weakest_title or str(weakest_topic.title),
                )
                if weakest_concept
                else None
            ),
            reason="All scoped topics are above threshold; recommending the weakest concept cluster for revision.",
            prereq_gaps=[],
            prereq_gap_labels=[],
            scope_warning=scope_warning,
            unmapped_topic_titles=unmapped_topic_titles,
        )

    def get_learning_map_visual(
        self,
        db: Session,
        *,
        student_id: UUID,
        subject: str,
        sss_level: str,
        term: int,
        view: str,
    ) -> LearningMapVisualOut:
        topics, rows, mastery_map = self._scope_graph_rows(
            db=db,
            student_id=student_id,
            subject=subject,
            sss_level=sss_level,
            term=term,
        )
        topic_rows, _, prereqs_by_concept, unmapped_topics = self._topic_graph(
            topics=topics,
            rows=rows,
            mastery_map=mastery_map,
        )
        next_step = self.calculate_next_step(
            db=db,
            payload=PathNextIn(
                student_id=student_id,
                subject=subject,  # type: ignore[arg-type]
                sss_level=sss_level,  # type: ignore[arg-type]
                term=term,
            ),
        )

        nodes: list[LearningMapNodeOut] = []
        edges: list[LearningMapEdgeOut] = []
        current_assigned = False
        previous_topic_id: str | None = None
        for topic in topics:
            topic_id = str(topic.id)
            concept_rows = topic_rows.get(topic_id, [])
            if not concept_rows:
                nodes.append(
                    LearningMapNodeOut(
                        topic_id=topic_id,
                        concept_id=None,
                        title=str(topic.title),
                        details="Curriculum mapping pending. This topic is visible, but adaptive graph guidance is not available yet.",
                        status="unmapped",
                        mastery_score=0.0,
                        concept_label=None,
                        kind="topic" if view == "topic" else "concept",
                    )
                )
                if view == "topic":
                    previous_topic_id = topic_id
                continue
            topic_mastery = mean([float(item["score"]) for item in concept_rows]) if concept_rows else 0.0
            weakest_concept = min(concept_rows, key=lambda item: float(item["score"])) if concept_rows else None

            prereq_ids = {
                prereq_id
                for row in concept_rows
                for prereq_id in prereqs_by_concept.get(str(row["concept_id"]), set())
            }
            prereqs_mastered = all(mastery_map.get(prereq_id, 0.0) >= MASTERY_THRESHOLD for prereq_id in prereq_ids)

            if topic_mastery >= MASTERY_THRESHOLD:
                status = "mastered"
            elif prereqs_mastered and not current_assigned:
                status = "current"
                current_assigned = True
            elif prereqs_mastered:
                status = "ready"
            else:
                status = "locked"

            if status == "mastered":
                details = f"{round(topic_mastery * 100)}% mastery"
            elif status == "current" and weakest_concept is not None:
                details = f"Weakest focus: {weakest_concept['concept_label']}"
            elif status == "ready":
                details = "Unlocked and ready to learn"
            else:
                details = "Strengthen prerequisites first"

            nodes.append(
                LearningMapNodeOut(
                    topic_id=topic_id,
                    concept_id=str(weakest_concept["concept_id"]) if weakest_concept else topic_id,
                    title=str(topic.title),
                    details=details,
                    status=status,
                    mastery_score=round(topic_mastery, 4),
                    concept_label=str(weakest_concept["concept_label"]) if weakest_concept else None,
                    kind="topic" if view == "topic" else "concept",
                )
            )
            if view == "topic":
                if previous_topic_id is not None:
                    edges.append(
                        LearningMapEdgeOut(
                            source_id=previous_topic_id,
                            target_id=topic_id,
                            relation="NEXT",
                        )
                    )
                previous_topic_id = topic_id

        if view == "concept":
            concept_ids = {
                str(row["concept_id"])
                for concept_rows in topic_rows.values()
                for row in concept_rows
            }
            for concept_id, prereq_ids in prereqs_by_concept.items():
                if concept_id not in concept_ids:
                    continue
                for prereq_id in prereq_ids:
                    if prereq_id not in concept_ids:
                        continue
                    edges.append(
                        LearningMapEdgeOut(
                            source_id=str(prereq_id),
                            target_id=str(concept_id),
                            relation="PREREQ_OF",
                        )
                    )

        return LearningMapVisualOut(
            student_id=student_id,
            subject=subject,
            sss_level=sss_level,
            term=term,
            view=view,
            nodes=nodes,
            edges=edges,
            next_step=next_step,
        )


learning_path_service = LearningPathService()
