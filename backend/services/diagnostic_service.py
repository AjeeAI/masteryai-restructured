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

# --- CRITICAL ADDITION: Import your real Neo4j adapter ---
from backend.repositories.neo4j_graph_repo import Neo4jGraphRepository, Neo4jGraphConfig

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

logger = logging.getLogger(__name__)

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
        repo = DiagnosticRepository(db)
        
        if not repo.validate_student_scope(
            student_id=payload.student_id, 
            subject=payload.subject, 
            sss_level=payload.sss_level, 
            term=payload.term
        ):
            raise DiagnosticValidationError("Student scope is invalid.")

        existing = repo.get_in_progress_diagnostic(
            student_id=payload.student_id, 
            subject=payload.subject, 
            sss_level=payload.sss_level, 
            term=payload.term
        )
        if existing and existing.questions:
            return self._serialize_existing_questions(existing, resumed=True)

        concept_rows = repo.get_scope_topic_concept_rows(
            subject=payload.subject, 
            sss_level=payload.sss_level, 
            term=payload.term
        )
        if not concept_rows:
            raise DiagnosticValidationError("No curriculum concepts found for this scope.")

        ai_questions = await self._fetch_ai_questions_from_core(payload, concept_rows)

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
        base_url = settings.ai_core_base_url.rstrip("/")
        
        random.shuffle(concept_rows)
        test_subset = concept_rows[:payload.num_questions]
        
        concepts_data = [
            {
                "concept_id": r["concept_id"],
                "label": self._readable_concept_label(r["concept_id"], fallback_topic_title=r["topic_title"]),
                "topic_title": r["topic_title"]
            } for r in test_subset
        ]

        async with httpx.AsyncClient(timeout=60.0) as client:
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
            
            if response.status_code != 200:
                error_detail = response.text
                logger.error(f"AI CORE FAILURE ({response.status_code}): {error_detail}")
                raise DiagnosticValidationError(f"AI Core rejected request: {error_detail}")

            return response.json()["questions"]

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

    # --- THE FIX: Kept Synchronous, Integrated with Real Neo4j Repo ---
    def process_diagnostic_submission(self, db: Session, payload: DiagnosticSubmitIn) -> DiagnosticSubmitOut:
        repo = DiagnosticRepository(db)
        graph_repo = GraphRepository(db) # The Postgres Repo
        
        diagnostic = repo.get_diagnostic(
            diagnostic_id=payload.diagnostic_id, 
            student_id=payload.student_id
        )
        
        if not diagnostic or diagnostic.status == "submitted":
            raise DiagnosticValidationError("Diagnostic session not found or already submitted.")

        questions = diagnostic.questions or []
        expected = {str(q["question_id"]): q for q in questions}
        baseline_updates = []
        
        existing_mastery = graph_repo.get_mastery_map(
            student_id=payload.student_id, 
            subject=diagnostic.subject, 
            sss_level=diagnostic.sss_level, 
            term=diagnostic.term
        )

        # 1. Initialize the Real Neo4j Connection
        neo4j_repo = None
        if settings.use_neo4j_graph:
            try:
                neo4j_repo = Neo4jGraphRepository(Neo4jGraphConfig(
                    uri=settings.neo4j_uri,
                    user=settings.neo4j_user,
                    password=settings.neo4j_password
                ))
            except Exception as e:
                logger.error(f"Failed to initialize Neo4j for diagnostic sync: {e}")

        try:
            for ans in payload.answers:
                q = expected.get(str(ans.question_id))
                if not q: continue
                
                is_correct = ans.answer.strip().upper() == q["correct_answer"].strip().upper()
                cid = q["concept_id"]
                prev_score = existing_mastery.get(cid, 0.0)
                new_score = 0.7 if is_correct else 0.2 
                
                # 2. Update Postgres
                _, stored_new = graph_repo.upsert_mastery(
                    student_id=payload.student_id, 
                    subject=diagnostic.subject, 
                    sss_level=diagnostic.sss_level, 
                    term=diagnostic.term,
                    concept_id=cid, 
                    new_score=new_score, 
                    source="diagnostic", 
                    evaluated_at=datetime.now(timezone.utc)
                )
                
                # 3. Update Neo4j (Creates Student node and Relationships!)
                if neo4j_repo:
                    try:
                        neo4j_repo.upsert_mastery(
                            student_id=str(payload.student_id),
                            concept_id=cid,
                            score=stored_new,
                            source="diagnostic",
                            evaluated_at=datetime.now(timezone.utc)
                        )
                    except Exception as e:
                        logger.error(f"Neo4j sync failed for concept {cid}: {e}")

                baseline_updates.append(BaselineMasteryUpdateOut(
                    concept_id=cid, 
                    previous_score=prev_score, 
                    new_score=stored_new, 
                    delta=stored_new - prev_score
                ))

            repo.mark_submitted(diagnostic)
            db.commit()

        except Exception as exc:
            db.rollback()
            logger.error(f"DIAGNOSTIC SYNC FAILED for {payload.student_id}: {str(exc)}")
            raise DiagnosticValidationError(f"Could not complete diagnostic: {str(exc)}")
        finally:
            # 4. Clean up connection
            if neo4j_repo:
                neo4j_repo.close()

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

# Instantiation
diagnostic_service = DiagnosticService()