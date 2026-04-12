from __future__ import annotations

import httpx
import logging
from collections import defaultdict
from datetime import datetime, timezone
import random
import re
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from backend.core.config import settings
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

logger = logging.getLogger(__name__)

MASTERY_PASS_THRESHOLD = 0.7
QUESTION_PROMPTS = [
    "For the topic '{topic_title}', which concept should you recognise first?",
    "Which concept best matches the core idea behind '{topic_title}'?",
    "If you begin studying '{topic_title}', which concept is the best starting focus?",
    "Which concept is most central to understanding '{topic_title}'?",
]
_MINOR_WORDS = {"a", "an", "and", "as", "at", "by", "for", "from", "in", "of", "on", "or", "the", "to", "with"}

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
        if not cleaned: return ""
        tokens = cleaned.lower().split(" ")
        normalized: list[str] = []
        for index, token in enumerate(tokens):
            if not token: continue
            if index == 0: normalized.append(token.capitalize())
            elif token in _MINOR_WORDS: normalized.append(token)
            else: normalized.append(token)
        return " ".join(normalized)

    @classmethod
    def _display_text(cls, value: str, *, strip_topic_prefix: bool = False) -> str:
        cleaned = re.sub(r"[_-]+", " ", str(value or "").strip())
        if strip_topic_prefix:
            cleaned = re.sub(r"^\s*topic\s+", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" -:\t\r\n'\"")
        return cls._sentence_case(cleaned) if cleaned else ""

    @classmethod
    def _readable_concept_label(cls, concept_id: str, *, fallback_topic_title: str | None = None) -> str:
        value = str(concept_id or "").strip()
        if not value: return cls._display_text(str(fallback_topic_title or "Untitled Concept"))
        token = value.rsplit(":", 1)[-1].strip().lower()
        if token.startswith("topic-") and fallback_topic_title:
            return cls._display_text(fallback_topic_title)
        token = re.sub(r"-(\d+)$", "", token)
        token = re.sub(r"^\s*topic[-\s]+", "", token)
        token = re.sub(r"[_-]+", " ", token)
        token = re.sub(r"\s+", " ", token).strip()
        return cls._display_text(token) if token else cls._display_text(fallback_topic_title or "Untitled Concept")

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
        return re.sub(r"\s+", " ", raw_prompt).strip()

    @classmethod
    def _build_option_display_lookup(cls, concept_rows: list[dict]) -> dict[str, str]:
        lookup: dict[str, str] = {}
        for row in concept_rows:
            label = cls._readable_concept_label(row.get("concept_id"), fallback_topic_title=row.get("topic_title"))
            lookup[cls._normalize_lookup_key(row.get("concept_id"))] = label
        return lookup

    def _serialize_existing_questions(
        self,
        diagnostic,
        *,
        resumed: bool,
    ) -> DiagnosticStartOut:
        questions = list(diagnostic.questions or [])
        concept_targets = list(dict.fromkeys(str(q.get("concept_id", "")).strip() for q in questions if q.get("concept_id")))
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
                    concept_label=self._readable_concept_label(q.get("concept_label", q["concept_id"]), fallback_topic_title=q.get("topic_title")),
                    topic_id=q.get("topic_id"),
                    topic_title=self._display_topic_title(q.get("topic_title")),
                    prompt=q.get("prompt", ""),
                    options=list(q.get("options", [])),
                    option_details=[DiagnosticOptionOut(label=str(opt)) for opt in list(q.get("options", []))]
                ) for q in questions
            ],
        )

    async def create_diagnostic_session(self, db: Session, payload: DiagnosticStartIn) -> DiagnosticStartOut:
        """Entrypoint for starting onboarding. Now fetches pedagogical questions from AI Core."""
        repo = DiagnosticRepository(db)
        
        # 1. Validation
        if not repo.validate_student_scope(payload.student_id, payload.subject, payload.sss_level, payload.term):
            raise DiagnosticValidationError("Student scope is invalid.")

        # 2. Check Resume
        existing = repo.get_in_progress_diagnostic(payload.student_id, payload.subject, payload.sss_level, payload.term)
        if existing and existing.questions:
            return self._serialize_existing_questions(existing, resumed=True)

        # 3. Get Curriculum context
        concept_rows = repo.get_scope_topic_concept_rows(payload.subject, payload.sss_level, payload.term)
        if not concept_rows:
            raise DiagnosticValidationError("No curriculum concepts found for this scope.")

        # 4. Fetch real questions from AI Core
        ai_questions = await self._fetch_ai_questions_from_core(payload, concept_rows)

        # 5. Save and Return
        concept_targets = list(dict.fromkeys(q["concept_id"] for q in ai_questions))
        diagnostic = repo.create_diagnostic(
            student_id=payload.student_id,
            subject=payload.subject,
            sss_level=payload.sss_level,
            term=payload.term,
            concept_targets=concept_targets,
            questions=ai_questions,
        )
        db.commit()
        db.refresh(diagnostic)

        return self._serialize_existing_questions(diagnostic, resumed=False)

    async def _fetch_ai_questions_from_core(self, payload: DiagnosticStartIn, concept_rows: list[dict]) -> list[dict]:
        """Sends concepts to AI Core to get high-quality assessment questions."""
        base_url = settings.ai_core_base_url.rstrip("/")
        
        # Pick relevant concepts for the diagnostic
        random.shuffle(concept_rows)
        test_subset = concept_rows[:payload.num_questions]
        
        concepts_data = [
            {
                "concept_id": r["concept_id"],
                "label": self._readable_concept_label(r["concept_id"], fallback_topic_title=r["topic_title"]),
                "topic_title": r["topic_title"]
            } for r in test_subset
        ]

        async with httpx.AsyncClient(timeout=45.0) as client:
            try:
                response = await client.post(
                    f"{base_url}/diagnostic/generate",
                    json={
                        "subject": payload.subject,
                        "sss_level": payload.sss_level,
                        "term": payload.term,
                        "concepts": concepts_data
                    },
                    headers={"X-Internal-Service-Key": settings.internal_service_key}
                )
                response.raise_for_status()
                return response.json()["questions"]
            except Exception as e:
                logger.error(f"AI Diagnostic Generation failed: {e}. Falling back to programmatic.")
                return self._programmatic_fallback(test_subset, concept_rows)

    def _programmatic_fallback(self, selected: list[dict], all_pool: list[dict]) -> list[dict]:
        """Emergency fallback if AI Core is down."""
        questions = []
        for i, row in enumerate(selected):
            correct_label = self._readable_concept_label(row["concept_id"], fallback_topic_title=row["topic_title"])
            distractors = [
                self._readable_concept_label(r["concept_id"], fallback_topic_title=r["topic_title"])
                for r in all_pool if r["concept_id"] != row["concept_id"]
            ]
            random.shuffle(distractors)
            options = [correct_label] + distractors[:3]
            random.shuffle(options)
            
            questions.append({
                "question_id": str(uuid4()),
                "concept_id": row["concept_id"],
                "topic_id": row.get("topic_id"),
                "topic_title": row.get("topic_title"),
                "prompt": f"Which concept is most central to understanding {row.get('topic_title', 'this topic')}?",
                "options": options,
                "correct_answer": chr(ord("A") + options.index(correct_label))
            })
        return questions

    def get_diagnostic_status(self, db: Session, *, student_id: UUID) -> DiagnosticStatusOut:
        repo = DiagnosticRepository(db)
        profile, subjects = repo.get_student_scope_context(student_id=student_id)
        if not profile or not subjects:
            raise DiagnosticValidationError("Student profile or subjects missing.")

        latest_runs = repo.get_latest_scope_diagnostics(
            student_id=student_id,
            sss_level=str(profile.sss_level),
            term=int(profile.active_term),
            subjects=subjects
        )

        subject_runs = []
        completed_count = 0
        for sub in subjects:
            diag, attempt = latest_runs.get(sub, (None, None))
            if diag and diag.status == "submitted":
                completed_count += 1
                subject_runs.append(DiagnosticSubjectRunOut(subject=sub, status="completed", diagnostic_id=diag.id))
            else:
                subject_runs.append(DiagnosticSubjectRunOut(subject=sub, status="pending"))

        return DiagnosticStatusOut(
            student_id=student_id,
            onboarding_complete=completed_count == len(subjects),
            pending_subjects=[s for s in subjects if s not in [r.subject for r in subject_runs if r.status == "completed"]],
            completed_subjects=[s for s in subjects if s in [r.subject for r in subject_runs if r.status == "completed"]],
            subject_runs=subject_runs
        )

    def process_diagnostic_submission(self, db: Session, payload: DiagnosticSubmitIn) -> DiagnosticSubmitOut:
        repo = DiagnosticRepository(db)
        graph_repo = GraphRepository(db)
        diagnostic = repo.get_diagnostic(payload.diagnostic_id, payload.student_id)
        
        if not diagnostic or diagnostic.status == "submitted":
            raise DiagnosticValidationError("Diagnostic session not found or already submitted.")

        questions = diagnostic.questions or []
        expected = {str(q["question_id"]): q for q in questions}
        correct_count = 0
        baseline_updates = []
        concept_breakdown = []
        
        existing_mastery = graph_repo.get_mastery_map(payload.student_id, diagnostic.subject, diagnostic.sss_level, diagnostic.term)

        for ans in payload.answers:
            q = expected.get(str(ans.question_id))
            if not q: continue
            
            is_correct = ans.answer.strip().upper() == q["correct_answer"].strip().upper()
            if is_correct: correct_count += 1
            
            cid = q["concept_id"]
            prev_score = existing_mastery.get(cid, 0.0)
            new_score = 0.7 if is_correct else 0.2 # Basic baseline logic
            
            _, stored_new = graph_repo.upsert_mastery(
                payload.student_id, diagnostic.subject, diagnostic.sss_level, diagnostic.term,
                cid, new_score, source="diagnostic", evaluated_at=datetime.now(timezone.utc)
            )
            
            baseline_updates.append(BaselineMasteryUpdateOut(concept_id=cid, previous_score=prev_score, new_score=stored_new, delta=stored_new - prev_score))
            concept_breakdown.append({"concept_id": cid, "is_correct": is_correct, "weight_change": stored_new - prev_score})

        repo.mark_submitted(diagnostic)
        db.commit()

        return DiagnosticSubmitOut(
            baseline_mastery_updates=baseline_updates,
            recommended_start_topic_id=None,
            recommended_start_topic_title="Module 1",
            weakest_concepts=[],
            learning_gap_summary=DiagnosticLearningGapSummaryOut(
                weakest_concepts=[],
                question_count=len(questions),
                completion_timestamp=datetime.now(timezone.utc).isoformat()
            )
        )

diagnostic_service = DiagnosticService()