from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import random
import re
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from backend.repositories.diagnostic_repo import DiagnosticRepository
from backend.repositories.graph_repo import GraphRepository
from backend.schemas.diagnostic_schema import (
    BaselineMasteryUpdateOut,
    DiagnosticLearningGapSummaryOut,
    DiagnosticOptionOut,
    DiagnosticQuestionOut,
    DiagnosticStartIn,
    DiagnosticStartOut,
    DiagnosticStatusOut,
    DiagnosticSubjectRunOut,
    DiagnosticSubmitIn,
    DiagnosticSubmitOut,
    DiagnosticWeakConceptOut,
)
from backend.schemas.learning_path_schema import PathNextIn
from backend.services.learning_path_service import LearningPathValidationError, learning_path_service


MASTERY_PASS_THRESHOLD = 0.7
QUESTION_PROMPTS = [
    "For the topic '{topic_title}', which concept should you recognise first?",
    "Which concept best matches the core idea behind '{topic_title}'?",
    "If you begin studying '{topic_title}', which concept is the best starting focus?",
    "Which concept is most central to understanding '{topic_title}'?",
]
_MINOR_WORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}


class DiagnosticValidationError(ValueError):
    pass


class DiagnosticNotFoundError(ValueError):
    pass


class DiagnosticAlreadySubmittedError(ValueError):
    pass


class DiagnosticService:
    @staticmethod
    def _normalize_lookup_key(value: str) -> str:
        normalized = re.sub(r"[_-]+", " ", str(value or "").strip().lower())
        normalized = re.sub(r"\btopic\b\s+", "", normalized, count=1)
        normalized = re.sub(r"\s+", " ", normalized).strip(" -:\t\r\n'\"")
        return normalized

    @classmethod
    def _sentence_case(cls, value: str) -> str:
        cleaned = re.sub(r"\s+", " ", str(value or "").strip())
        if not cleaned:
            return ""
        tokens = cleaned.lower().split(" ")
        if not tokens:
            return ""
        normalized: list[str] = []
        for index, token in enumerate(tokens):
            if not token:
                continue
            if index == 0:
                normalized.append(token.capitalize())
            elif token in _MINOR_WORDS:
                normalized.append(token)
            else:
                normalized.append(token)
        return " ".join(normalized)

    @classmethod
    def _display_text(cls, value: str, *, strip_topic_prefix: bool = False) -> str:
        cleaned = re.sub(r"[_-]+", " ", str(value or "").strip())
        if strip_topic_prefix:
            cleaned = re.sub(r"^\s*topic\s+", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" -:\t\r\n'\"")
        if not cleaned:
            return ""
        return cls._sentence_case(cleaned)

    @classmethod
    def _prefer_topic_title(cls, concept_text: str, fallback_topic_title: str | None) -> bool:
        topic_title = str(fallback_topic_title or "").strip()
        if not topic_title:
            return False

        concept_key = cls._normalize_lookup_key(concept_text)
        topic_key = cls._normalize_lookup_key(topic_title)
        if not concept_key or not topic_key:
            return False

        if concept_key.startswith("topic "):
            return True

        if topic_key == concept_key:
            return True

        if (
            len(concept_key) >= 14
            and topic_key.startswith(concept_key)
            and len(concept_key) >= int(len(topic_key) * 0.72)
        ):
            return True

        return False

    @staticmethod
    def _is_topic_surrogate_concept(concept_id: str) -> bool:
        token = str(concept_id or "").rsplit(":", 1)[-1].strip().lower()
        return token.startswith("topic-") or token == "topic"

    @classmethod
    def _readable_concept_label(cls, concept_id: str, *, fallback_topic_title: str | None = None) -> str:
        value = str(concept_id or "").strip()
        if not value:
            return cls._display_text(str(fallback_topic_title or "Untitled Concept"))
        token = value.rsplit(":", 1)[-1].strip().lower()
        if token.startswith("topic-") and fallback_topic_title:
            return cls._display_text(str(fallback_topic_title or "Untitled Concept"))
        token = re.sub(r"-(\d+)$", "", token)
        token = re.sub(r"^\s*topic[-\s]+", "", token)
        token = re.sub(r"[_-]+", " ", token)
        token = re.sub(r"\s+", " ", token).strip()
        if cls._prefer_topic_title(token, fallback_topic_title):
            return cls._display_text(str(fallback_topic_title or "Untitled Concept"))
        return cls._display_text(token) if token else cls._display_text(str(fallback_topic_title or "Untitled Concept"))

    @classmethod
    def _display_topic_title(cls, topic_title: str | None) -> str | None:
        cleaned = cls._display_text(str(topic_title or ""))
        return cleaned or None

    @classmethod
    def _normalize_prompt(cls, prompt: str | None, *, topic_title: str | None) -> str:
        readable_topic = cls._display_topic_title(topic_title) or "this topic"
        raw_prompt = str(prompt or "").strip()
        if not raw_prompt:
            return QUESTION_PROMPTS[0].format(topic_title=readable_topic)

        raw_topic = str(topic_title or "").strip()
        if raw_topic:
            raw_prompt = raw_prompt.replace(raw_topic, readable_topic)
        return re.sub(r"\s+", " ", raw_prompt).strip()

    @classmethod
    def _build_option_display_lookup(cls, concept_rows: list[dict]) -> dict[str, str]:
        lookup: dict[str, str] = {}
        for row in concept_rows:
            topic_title = str(row.get("topic_title") or "").strip()
            concept_id = str(row.get("concept_id") or "").strip()
            display_label = cls._readable_concept_label(concept_id, fallback_topic_title=topic_title)
            keys = {
                cls._normalize_lookup_key(concept_id),
                cls._normalize_lookup_key(display_label),
                cls._normalize_lookup_key(topic_title),
                cls._normalize_lookup_key(concept_id.rsplit(":", 1)[-1]),
            }
            for key in keys:
                if key:
                    lookup.setdefault(key, display_label)
        return lookup

    @classmethod
    def _build_option_context_lookup(cls, concept_rows: list[dict]) -> dict[str, str | None]:
        lookup: dict[str, str | None] = {}
        for row in concept_rows:
            topic_title = cls._display_topic_title(row.get("topic_title"))
            concept_id = str(row.get("concept_id") or "").strip()
            display_label = cls._readable_concept_label(concept_id, fallback_topic_title=topic_title)
            context_title = topic_title if topic_title and cls._normalize_lookup_key(topic_title) != cls._normalize_lookup_key(display_label) else None
            keys = {
                cls._normalize_lookup_key(concept_id),
                cls._normalize_lookup_key(display_label),
                cls._normalize_lookup_key(topic_title or ""),
                cls._normalize_lookup_key(concept_id.rsplit(":", 1)[-1]),
            }
            for key in keys:
                if key:
                    lookup.setdefault(key, context_title)
        return lookup

    @classmethod
    def _display_option_text(cls, option: str, *, option_display_lookup: dict[str, str] | None = None) -> str:
        key = cls._normalize_lookup_key(option)
        if option_display_lookup and key in option_display_lookup:
            return option_display_lookup[key]
        return cls._display_text(option, strip_topic_prefix=True)

    @classmethod
    def _option_context_text(cls, option: str, *, option_context_lookup: dict[str, str | None] | None = None) -> str | None:
        key = cls._normalize_lookup_key(option)
        if option_context_lookup and key in option_context_lookup:
            return option_context_lookup[key]
        return None

    @staticmethod
    def _dedupe_titles(rows: list[dict]) -> list[str]:
        titles: list[str] = []
        seen: set[str] = set()
        for row in rows:
            label = str(row.get("concept_label") or "").strip()
            if not label or label in seen:
                continue
            seen.add(label)
            titles.append(label)
        return titles

    def _build_options(self, current_row: dict, all_rows: list[dict], *, rng: random.Random) -> tuple[list[str], str]:
        correct_title = str(current_row.get("concept_label") or "").strip()
        if not correct_title:
            raise DiagnosticValidationError("Diagnostic question is missing a readable concept label.")

        correct_id = str(current_row.get("concept_id") or "").strip()
        current_topic_id = str(current_row.get("topic_id") or "").strip()
        prereq_ids = {
            str(value).strip()
            for value in list(current_row.get("prereq_concept_ids") or [])
            if str(value).strip()
        }
        neighbor_ids = set(prereq_ids)
        if correct_id:
            neighbor_ids.update(
                str(row.get("concept_id") or "").strip()
                for row in all_rows
                if correct_id in {
                    str(value).strip()
                    for value in list(row.get("prereq_concept_ids") or [])
                    if str(value).strip()
                }
            )

        same_topic_rows = [
            row
            for row in all_rows
            if str(row.get("topic_id") or "").strip() == current_topic_id
            and str(row.get("concept_label") or "").strip() != correct_title
        ]
        neighboring_rows = [
            row
            for row in all_rows
            if str(row.get("concept_id") or "").strip() in neighbor_ids
            and str(row.get("concept_label") or "").strip() != correct_title
        ]
        fallback_rows = [
            row
            for row in all_rows
            if str(row.get("concept_label") or "").strip() != correct_title
        ]

        rng.shuffle(same_topic_rows)
        rng.shuffle(neighboring_rows)
        rng.shuffle(fallback_rows)

        distractor_titles: list[str] = []
        seen: set[str] = {correct_title}
        for pool in (same_topic_rows, neighboring_rows, fallback_rows):
            for title in self._dedupe_titles(pool):
                if title in seen:
                    continue
                distractor_titles.append(title)
                seen.add(title)
                if len(distractor_titles) == 3:
                    break
            if len(distractor_titles) == 3:
                break

        if len(distractor_titles) < 3:
            raise DiagnosticValidationError("At least four mapped concept labels are required to build a diagnostic question.")

        options = distractor_titles + [correct_title]
        rng.shuffle(options)
        correct_index = options.index(correct_title)
        return options, chr(ord("A") + correct_index)

    @staticmethod
    def _evaluate_answer(*, answer: str, question: dict) -> bool:
        normalized = answer.strip()
        correct_answer = str(question.get("correct_answer", "")).strip()
        if normalized.upper() == correct_answer.upper():
            return True

        options = question.get("options") or []
        if normalized in options and correct_answer.upper() in {"A", "B", "C", "D"}:
            idx = ord(correct_answer.upper()) - ord("A")
            if 0 <= idx < len(options):
                return normalized == options[idx]
        return False

    @staticmethod
    def _unique_concept_titles(concept_rows: list[dict]) -> list[str]:
        titles: list[str] = []
        for row in concept_rows:
            label = str(row.get("concept_label") or "").strip()
            if label and label not in titles:
                titles.append(label)
        return titles

    @staticmethod
    def _select_question_rows(concept_rows: list[dict], *, num_questions: int, rng: random.Random) -> list[dict]:
        if not concept_rows:
            return []
        pool = list(concept_rows)
        selected: list[dict] = []
        while len(selected) < num_questions:
            cycle = list(pool)
            rng.shuffle(cycle)
            for row in cycle:
                selected.append(row)
                if len(selected) == num_questions:
                    break
        return selected

    def _serialize_existing_questions(
        self,
        diagnostic,
        *,
        resumed: bool,
        option_display_lookup: dict[str, str] | None = None,
        option_context_lookup: dict[str, str | None] | None = None,
    ) -> DiagnosticStartOut:
        questions = list(diagnostic.questions or [])
        concept_targets = list(dict.fromkeys(str(item.get("concept_id") or "").strip() for item in questions if str(item.get("concept_id") or "").strip()))
        return DiagnosticStartOut(
            diagnostic_id=diagnostic.id,
            subject=diagnostic.subject,
            sss_level=diagnostic.sss_level,
            term=int(diagnostic.term),
            question_count=len(questions),
            resumed=resumed,
            concept_targets=concept_targets,
            questions=[
                DiagnosticQuestionOut(
                    question_id=str(q["question_id"]),
                    concept_id=str(q["concept_id"]),
                    concept_label=self._readable_concept_label(
                        str(q.get("concept_label") or q["concept_id"]),
                        fallback_topic_title=q.get("topic_title"),
                    ),
                    topic_id=q.get("topic_id"),
                    topic_title=self._display_topic_title(q.get("topic_title")),
                    prompt=self._normalize_prompt(str(q.get("prompt") or ""), topic_title=q.get("topic_title")),
                    options=[
                        self._display_option_text(str(option or ""), option_display_lookup=option_display_lookup)
                        for option in list(q.get("options") or [])
                    ],
                    option_details=[
                        DiagnosticOptionOut(
                            label=self._display_option_text(str(option or ""), option_display_lookup=option_display_lookup),
                            context_title=self._option_context_text(
                                str(option or ""),
                                option_context_lookup=option_context_lookup,
                            ),
                        )
                        for option in list(q.get("options") or [])
                    ],
                )
                for q in questions
            ],
        )

    def create_diagnostic_session(self, db: Session, payload: DiagnosticStartIn) -> DiagnosticStartOut:
        repo = DiagnosticRepository(db)
        if not repo.validate_student_scope(
            student_id=payload.student_id,
            subject=payload.subject,
            sss_level=payload.sss_level,
            term=payload.term,
        ):
            raise DiagnosticValidationError(
                "Student scope is invalid. Ensure profile, level, term, and subject enrollment are correct."
            )

        existing = repo.get_in_progress_diagnostic(
            student_id=payload.student_id,
            subject=payload.subject,
            sss_level=payload.sss_level,
            term=payload.term,
        )
        concept_rows = repo.get_scope_topic_concept_rows(
            subject=payload.subject,
            sss_level=payload.sss_level,
            term=payload.term,
        )
        option_display_lookup = self._build_option_display_lookup(concept_rows)
        option_context_lookup = self._build_option_context_lookup(concept_rows)
        if existing is not None and existing.questions:
            return self._serialize_existing_questions(
                existing,
                resumed=True,
                option_display_lookup=option_display_lookup,
                option_context_lookup=option_context_lookup,
            )
        if not concept_rows:
            raise DiagnosticValidationError(
                "No curriculum concept mappings found for this scope. Ingest and approve mapped curriculum first."
            )

        normalized_rows: list[dict] = []
        for row in concept_rows:
            topic_id = str(row.get("topic_id") or "").strip()
            concept_id = str(row.get("concept_id") or "").strip()
            topic_title = str(row.get("topic_title") or "").strip()
            if not topic_id or not concept_id:
                continue
            normalized_rows.append(
                {
                    "topic_id": topic_id,
                    "topic_title": topic_title,
                    "concept_id": concept_id,
                    "concept_label": self._readable_concept_label(concept_id, fallback_topic_title=topic_title),
                    "is_topic_surrogate": self._is_topic_surrogate_concept(concept_id),
                }
            )
        primary_rows = [row for row in normalized_rows if not row.get("is_topic_surrogate")]
        question_rows = primary_rows if len(self._unique_concept_titles(primary_rows)) >= 4 else normalized_rows
        if len(self._unique_concept_titles(question_rows)) < 4:
            raise DiagnosticValidationError(
                "At least four mapped concepts are required in this scope before the onboarding diagnostic can run."
            )

        rng = random.Random(f"{payload.student_id}:{payload.subject}:{payload.sss_level}:{payload.term}:{payload.num_questions}")
        selected_rows = self._select_question_rows(
            question_rows,
            num_questions=payload.num_questions,
            rng=rng,
        )
        questions: list[dict] = []
        for index, row in enumerate(selected_rows):
            prompt_template = QUESTION_PROMPTS[index % len(QUESTION_PROMPTS)]
            options, correct_answer = self._build_options(
                row,
                question_rows,
                rng=rng,
            )
            questions.append(
                {
                    "question_id": str(uuid4()),
                    "concept_id": row["concept_id"],
                    "concept_label": row["concept_label"],
                    "topic_id": row["topic_id"],
                    "topic_title": self._display_topic_title(row["topic_title"]),
                    "prompt": prompt_template.format(
                        topic_title=self._display_topic_title(row["topic_title"]) or "this topic",
                    ),
                    "options": options,
                    "option_details": [
                        {
                            "label": self._display_option_text(option, option_display_lookup=option_display_lookup),
                            "context_title": self._option_context_text(
                                option,
                                option_context_lookup=option_context_lookup,
                            ),
                        }
                        for option in options
                    ],
                    "correct_answer": correct_answer,
                }
            )

        concept_targets = list(
            dict.fromkeys(
                str(question["concept_id"]).strip()
                for question in questions
                if str(question.get("concept_id") or "").strip()
            )
        )
        if not concept_targets:
            raise DiagnosticValidationError(
                "No mapped concepts are available to build a diagnostic for this scope yet."
            )

        diagnostic = repo.create_diagnostic(
            student_id=payload.student_id,
            subject=payload.subject,
            sss_level=payload.sss_level,
            term=payload.term,
            concept_targets=concept_targets,
            questions=questions,
        )
        db.commit()
        db.refresh(diagnostic)
        return self._serialize_existing_questions(
            diagnostic,
            resumed=False,
            option_display_lookup=option_display_lookup,
            option_context_lookup=option_context_lookup,
        )

    def get_diagnostic_status(self, db: Session, *, student_id: UUID) -> DiagnosticStatusOut:
        repo = DiagnosticRepository(db)
        profile, subjects = repo.get_student_scope_context(student_id=student_id)
        if profile is None:
            raise DiagnosticValidationError("Student profile not found.")
        if not subjects:
            raise DiagnosticValidationError("Student has no enrolled subjects yet.")

        latest_runs = repo.get_latest_scope_diagnostics(
            student_id=student_id,
            sss_level=str(profile.sss_level),
            term=int(profile.active_term),
            subjects=subjects,
        )

        subject_runs: list[DiagnosticSubjectRunOut] = []
        pending_subjects: list[str] = []
        completed_subjects: list[str] = []

        for subject in subjects:
            diagnostic, attempt = latest_runs.get(subject, (None, None))
            if diagnostic is None:
                pending_subjects.append(subject)
                subject_runs.append(
                    DiagnosticSubjectRunOut(subject=subject, status="pending")
                )
                continue

            question_count = len(list(diagnostic.questions or []))
            if diagnostic.status == "submitted" and attempt is not None:
                completed_subjects.append(subject)
                gap_summary = dict(attempt.gap_summary or {})
                weakest = [
                    DiagnosticWeakConceptOut(**item)
                    for item in list(gap_summary.get("weakest_concepts") or [])
                    if isinstance(item, dict)
                ]
                subject_runs.append(
                    DiagnosticSubjectRunOut(
                        subject=subject,
                        status="completed",
                        diagnostic_id=diagnostic.id,
                        question_count=question_count,
                        recommended_start_topic_id=attempt.recommended_start_topic_id,
                        recommended_start_topic_title=attempt.recommended_start_topic_title,
                        weakest_concepts=weakest,
                        blocking_prerequisite_id=gap_summary.get("blocking_prerequisite_id"),
                        blocking_prerequisite_label=gap_summary.get("blocking_prerequisite_label"),
                        completion_timestamp=gap_summary.get("completion_timestamp")
                        or (attempt.created_at.isoformat() if getattr(attempt, "created_at", None) else None),
                    )
                )
            else:
                pending_subjects.append(subject)
                subject_runs.append(
                    DiagnosticSubjectRunOut(
                        subject=subject,
                        status="in_progress",
                        diagnostic_id=diagnostic.id,
                        question_count=question_count,
                    )
                )

        return DiagnosticStatusOut(
            student_id=student_id,
            onboarding_complete=bool(subjects) and len(completed_subjects) == len(subjects),
            pending_subjects=pending_subjects,
            completed_subjects=completed_subjects,
            subject_runs=subject_runs,
        )

    def _weakest_concepts(
        self,
        *,
        concept_targets: list[str],
        mastery_map: dict[str, float],
        topic_lookup: dict[str, str],
        limit: int = 3,
    ) -> list[DiagnosticWeakConceptOut]:
        seen: set[str] = set()
        candidates: list[DiagnosticWeakConceptOut] = []
        for concept_id in concept_targets:
            if concept_id in seen:
                continue
            seen.add(concept_id)
            topic_title = topic_lookup.get(concept_id)
            candidates.append(
                DiagnosticWeakConceptOut(
                    concept_id=concept_id,
                    concept_label=self._readable_concept_label(concept_id, fallback_topic_title=topic_title),
                    mastery_score=round(float(mastery_map.get(concept_id, 0.0)), 4),
                )
            )
        return sorted(candidates, key=lambda item: (item.mastery_score, item.concept_label))[:limit]

    def process_diagnostic_submission(self, db: Session, payload: DiagnosticSubmitIn) -> DiagnosticSubmitOut:
        repo = DiagnosticRepository(db)
        graph_repo = GraphRepository(db)

        diagnostic = repo.get_diagnostic(
            diagnostic_id=payload.diagnostic_id,
            student_id=payload.student_id,
        )
        if not diagnostic:
            raise DiagnosticNotFoundError("Diagnostic session not found for this student.")
        if diagnostic.status == "submitted":
            raise DiagnosticAlreadySubmittedError("Diagnostic session has already been submitted.")

        questions = list(diagnostic.questions or [])
        if not questions:
            raise DiagnosticValidationError("Diagnostic has no question set.")

        expected_by_id = {str(q["question_id"]): q for q in questions if "question_id" in q}
        if not expected_by_id:
            raise DiagnosticValidationError("Diagnostic questions are malformed.")

        submitted_by_id = {str(answer.question_id): answer for answer in payload.answers}
        missing = [question_id for question_id in expected_by_id if question_id not in submitted_by_id]
        if missing:
            raise DiagnosticValidationError("Submission must include all diagnostic questions.")

        concept_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"correct": 0, "total": 0})
        graded_answers: list[dict] = []
        correct_count = 0
        question_topic_lookup: dict[str, str] = {}

        for question_id, question in expected_by_id.items():
            submitted = submitted_by_id.get(question_id)
            if submitted is None:
                continue

            is_correct = self._evaluate_answer(answer=submitted.answer, question=question)
            concept_id = str(question["concept_id"])
            question_topic_lookup[concept_id] = str(question.get("topic_title") or "").strip()
            concept_stats[concept_id]["total"] += 1
            if is_correct:
                concept_stats[concept_id]["correct"] += 1
                correct_count += 1

            graded_answers.append(
                {
                    "question_id": question_id,
                    "answer": submitted.answer,
                    "is_correct": is_correct,
                    "concept_id": concept_id,
                }
            )

        existing_mastery = graph_repo.get_mastery_map(
            student_id=payload.student_id,
            subject=diagnostic.subject,
            sss_level=diagnostic.sss_level,
            term=diagnostic.term,
        )

        baseline_updates: list[BaselineMasteryUpdateOut] = []
        concept_breakdown: list[dict] = []
        for concept_id in diagnostic.concept_targets:
            stats = concept_stats.get(concept_id, {"correct": 0, "total": 0})
            accuracy = (stats["correct"] / stats["total"]) if stats["total"] > 0 else 0.0
            previous = existing_mastery.get(concept_id, 0.0)
            projected = max(0.0, min(1.0, round((previous * 0.35) + (accuracy * 0.65), 4)))
            stored_previous, stored_new = graph_repo.upsert_mastery(
                student_id=payload.student_id,
                subject=diagnostic.subject,
                sss_level=diagnostic.sss_level,
                term=diagnostic.term,
                concept_id=concept_id,
                new_score=projected,
                source="diagnostic",
                evaluated_at=datetime.now(timezone.utc),
            )
            existing_mastery[concept_id] = stored_new
            delta = round(stored_new - stored_previous, 4)
            baseline_updates.append(
                BaselineMasteryUpdateOut(
                    concept_id=concept_id,
                    previous_score=round(stored_previous, 4),
                    new_score=round(stored_new, 4),
                    delta=delta,
                )
            )
            concept_breakdown.append(
                {
                    "concept_id": concept_id,
                    "is_correct": accuracy >= MASTERY_PASS_THRESHOLD,
                    "weight_change": delta,
                }
            )

        recommended_start_topic_id: str | None = None
        recommended_start_topic_title: str | None = None
        blocking_prerequisite_id: str | None = None
        blocking_prerequisite_label: str | None = None
        scope_warning: str | None = None
        weakest_concepts: list[DiagnosticWeakConceptOut] = []
        try:
            next_step = learning_path_service.calculate_next_step(
                db=db,
                payload=PathNextIn(
                    student_id=payload.student_id,
                    subject=diagnostic.subject,  # type: ignore[arg-type]
                    sss_level=diagnostic.sss_level,  # type: ignore[arg-type]
                    term=diagnostic.term,
                ),
            )
            recommended_start_topic_id = next_step.recommended_topic_id
            recommended_start_topic_title = next_step.recommended_topic_title
            blocking_prerequisite_id = next_step.prereq_gaps[0] if next_step.prereq_gaps else None
            blocking_prerequisite_label = next_step.prereq_gap_labels[0] if next_step.prereq_gap_labels else None
            scope_warning = next_step.scope_warning
        except LearningPathValidationError:
            next_step = None

        weakest_concepts = self._weakest_concepts(
            concept_targets=list(diagnostic.concept_targets or []),
            mastery_map=existing_mastery,
            topic_lookup=question_topic_lookup,
        )
        completion_timestamp = datetime.now(timezone.utc).isoformat()
        learning_gap_summary = DiagnosticLearningGapSummaryOut(
            weakest_concepts=weakest_concepts,
            blocking_prerequisite_id=blocking_prerequisite_id,
            blocking_prerequisite_label=blocking_prerequisite_label,
            recommended_start_topic_id=recommended_start_topic_id,
            recommended_start_topic_title=recommended_start_topic_title,
            next_best_action=(
                f"Begin with {recommended_start_topic_title}"
                if recommended_start_topic_title
                else "Open your recommended lesson"
            ),
            rationale=(
                next_step.reason
                if next_step is not None
                else "Use the weakest concept cluster to begin the graph-backed lesson path."
            ),
            question_count=len(questions),
            completion_timestamp=completion_timestamp,
        )

        total_questions = len(expected_by_id)
        score = round((correct_count / total_questions) * 100.0, 2) if total_questions > 0 else 0.0

        attempt = repo.save_attempt(
            diagnostic_id=diagnostic.id,
            student_id=diagnostic.student_id,
            answers=graded_answers,
            baseline_mastery_updates=[item.model_dump() for item in baseline_updates],
            gap_summary=learning_gap_summary.model_dump(),
            recommended_start_topic_id=recommended_start_topic_id,
            recommended_start_topic_title=recommended_start_topic_title,
            score=score,
        )
        graph_repo.record_update_event(
            student_id=payload.student_id,
            quiz_id=None,
            attempt_id=attempt.id,
            subject=diagnostic.subject,
            sss_level=diagnostic.sss_level,
            term=int(diagnostic.term),
            source="diagnostic",
            concept_breakdown=concept_breakdown,
            new_mastery=[item.model_dump() for item in baseline_updates],
        )
        repo.mark_submitted(diagnostic)

        from backend.services.lesson_cockpit_service import LessonCockpitService
        from backend.services.lesson_experience_service import LessonExperienceService
        from backend.services.course_experience_service import CourseExperienceService
        from backend.services.dashboard_experience_service import DashboardExperienceService

        LessonExperienceService.invalidate_topic_snapshot_cache(
            student_id=payload.student_id,
            subject=diagnostic.subject,
            sss_level=diagnostic.sss_level,
            term=int(diagnostic.term),
        )
        LessonCockpitService.invalidate_scope_cache(
            student_id=payload.student_id,
            subject=diagnostic.subject,
            sss_level=diagnostic.sss_level,
            term=int(diagnostic.term),
        )
        CourseExperienceService.invalidate_scope_cache(
            student_id=payload.student_id,
            subject=diagnostic.subject,
            sss_level=diagnostic.sss_level,
            term=int(diagnostic.term),
        )
        DashboardExperienceService.invalidate_student_cache(student_id=payload.student_id)
        db.commit()

        return DiagnosticSubmitOut(
            baseline_mastery_updates=baseline_updates,
            recommended_start_topic_id=recommended_start_topic_id,
            recommended_start_topic_title=recommended_start_topic_title,
            scope_warning=scope_warning,
            weakest_concepts=weakest_concepts,
            blocking_prerequisite_id=blocking_prerequisite_id,
            blocking_prerequisite_label=blocking_prerequisite_label,
            learning_gap_summary=learning_gap_summary,
        )


diagnostic_service = DiagnosticService()
