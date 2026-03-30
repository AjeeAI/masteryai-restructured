from __future__ import annotations

import logging
import time
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.core.telemetry import log_timed_event
from backend.repositories.lesson_repo import get_topic_with_subject
from backend.schemas.graph_learning_schema import LessonGraphContextOut, WhyThisTopicOut
from backend.services.lesson_graph_service import LessonGraphValidationError, lesson_graph_service


router = APIRouter(prefix="/learning/graph", tags=["Learning Graph"])
logger = logging.getLogger(__name__)


def _topic_title(db: Session, topic_id: UUID) -> str:
    row = get_topic_with_subject(db, topic_id)
    if not row:
        return "Current Topic"
    title = str(row[0].title or "").strip()
    return title or "Current Topic"


@router.get("/lesson-context", response_model=LessonGraphContextOut)
def get_lesson_graph_context(
    student_id: UUID,
    subject: Literal["math", "english", "civic"],
    sss_level: Literal["SSS1", "SSS2", "SSS3"],
    term: int = Query(..., ge=1, le=3),
    topic_id: UUID = Query(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    started_at = time.perf_counter()
    if student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="student_id must match authenticated user id",
        )
    try:
        response = lesson_graph_service.get_lesson_graph_context(
            db,
            student_id=student_id,
            subject=subject,
            sss_level=sss_level,
            term=term,
            topic_id=topic_id,
        )
        log_timed_event(
            logger,
            "learning.graph.lesson_context",
            started_at,
            outcome="success",
            student_id=student_id,
            topic_id=topic_id,
            subject=subject,
            sss_level=sss_level,
            term=term,
            current_count=len(list(response.current_concepts or [])),
            prereq_count=len(list(response.prerequisite_concepts or [])),
            downstream_count=len(list(response.downstream_concepts or [])),
            node_count=len(list(response.graph_nodes or [])),
            edge_count=len(list(response.graph_edges or [])),
            next_topic_id=response.next_unlock.topic_id if response.next_unlock else None,
        )
        return response
    except LessonGraphValidationError as exc:
        message = str(exc)
        if "approved graph scope" in message:
            fallback = LessonGraphContextOut(
                student_id=student_id,
                subject=subject,  # type: ignore[arg-type]
                sss_level=sss_level,  # type: ignore[arg-type]
                term=term,
                topic_id=str(topic_id),
                topic_title=_topic_title(db, topic_id),
                overall_mastery=0.0,
                status="unavailable",
                unavailable_reason=message,
            )
            log_timed_event(
                logger,
                "learning.graph.lesson_context",
                started_at,
                outcome="unavailable",
                subject=subject,
                sss_level=sss_level,
                term=term,
                topic_id=topic_id,
                error=message,
                log_level=logging.WARNING,
            )
            return fallback
        log_timed_event(
            logger,
            "learning.graph.lesson_context",
            started_at,
            outcome="error",
            subject=subject,
            sss_level=sss_level,
            term=term,
            topic_id=topic_id,
            error=message,
            log_level=logging.WARNING,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message) from exc


@router.get("/why-this-topic", response_model=WhyThisTopicOut)
def explain_why_this_topic(
    student_id: UUID,
    subject: Literal["math", "english", "civic"],
    sss_level: Literal["SSS1", "SSS2", "SSS3"],
    term: int = Query(..., ge=1, le=3),
    topic_id: UUID = Query(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    started_at = time.perf_counter()
    if student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="student_id must match authenticated user id",
        )
    try:
        response = lesson_graph_service.explain_why_this_topic(
            db,
            student_id=student_id,
            subject=subject,
            sss_level=sss_level,
            term=term,
            topic_id=topic_id,
        )
        log_timed_event(
            logger,
            "learning.graph.why_topic",
            started_at,
            outcome="success",
            student_id=student_id,
            topic_id=topic_id,
            subject=subject,
            sss_level=sss_level,
            term=term,
            prereq_labels=len(list(response.prerequisite_labels or [])),
            unlock_labels=len(list(response.unlock_labels or [])),
            next_topic_id=response.recommended_next.topic_id if response.recommended_next else None,
        )
        return response
    except LessonGraphValidationError as exc:
        message = str(exc)
        if "approved graph scope" in message:
            fallback = WhyThisTopicOut(
                student_id=student_id,
                subject=subject,  # type: ignore[arg-type]
                sss_level=sss_level,  # type: ignore[arg-type]
                term=term,
                topic_id=str(topic_id),
                topic_title=_topic_title(db, topic_id),
                status="unavailable",
                unavailable_reason=message,
                explanation=message,
                prerequisite_labels=[],
                unlock_labels=[],
                weakest_prerequisite_label=None,
                recommended_next=None,
            )
            log_timed_event(
                logger,
                "learning.graph.why_topic",
                started_at,
                outcome="unavailable",
                subject=subject,
                sss_level=sss_level,
                term=term,
                topic_id=topic_id,
                error=message,
                log_level=logging.WARNING,
            )
            return fallback
        log_timed_event(
            logger,
            "learning.graph.why_topic",
            started_at,
            outcome="error",
            subject=subject,
            sss_level=sss_level,
            term=term,
            topic_id=topic_id,
            error=message,
            log_level=logging.WARNING,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message) from exc
