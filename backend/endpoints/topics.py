"""Topic listing endpoints constrained by student profile scope."""

import uuid
import re
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy import inspect

from backend.core.database import get_db
from backend.models.topic import Topic
from backend.models.subject import Subject
from backend.models.student import StudentProfile, StudentSubject
from backend.models.personalized_lesson import PersonalizedLesson
from backend.repositories.lesson_repo import ensure_personalized_lessons_table
from backend.services.rag_retrieve_service import RagRetrieveService, RagRetrieveServiceError

router = APIRouter(prefix="/learning", tags=["Topics"])


_NOISY_DESCRIPTION_MARKERS = (
    "SECOND TERM E-LEARNING NOTE SUBJECT",
    "SCHEME OF WORK WEEK TOPIC",
    "WEEKEND ASSIGNMENT SECTION",
)


def _clean_topic_description(raw: str | None, topic_title: str) -> str | None:
    text = re.sub(r"\s+", " ", str(raw or "")).strip()
    if not text:
        return None
    if any(marker in text.upper() for marker in _NOISY_DESCRIPTION_MARKERS):
        return None
    if len(text) > 220:
        return f"{text[:217].rstrip()}..."
    return text


def _has_cached_personalized_lesson(lesson: PersonalizedLesson | None) -> bool:
    return bool(lesson and isinstance(lesson.content_blocks, list) and lesson.content_blocks)


def _personalized_lessons_available(db: Session) -> bool:
    bind = db.get_bind()
    inspector = inspect(bind)
    if inspector.has_table("personalized_lessons"):
        return True
    try:
        ensure_personalized_lessons_table(db)
    except Exception:
        return False
    return inspect(bind).has_table("personalized_lessons")

@router.get("/topics")
def list_topics(
    student_id: uuid.UUID = Query(...),
    subject: str | None = Query(None, description="math|english|civic"),
    term: int | None = Query(None),
    include_unready: bool = Query(
        False,
        description="Include topics even when no approved lesson chunks are available for generation.",
    ),
    db: Session = Depends(get_db),
):
    """Return approved topics available to the student in current scope.

    Topic visibility is restricted by student profile level/term/subjects.
    Optional `subject` and `term` query params narrow the result.
    """
    # Fetch student scope
    sp = db.execute(select(StudentProfile).where(StudentProfile.student_id == student_id)).scalar_one_or_none()
    if not sp:
        raise HTTPException(status_code=403, detail="Student profile not found.")

    # Subjects the student is enrolled in
    enrolled_subject_ids = [
        row[0] for row in db.execute(
            select(StudentSubject.subject_id).where(StudentSubject.student_profile_id == sp.id)
        ).all()
    ]

    personalized_lessons_available = _personalized_lessons_available(db)

    if personalized_lessons_available:
        q = (
            select(Topic, PersonalizedLesson, Subject.slug)
            .join(Subject, Subject.id == Topic.subject_id)
            .outerjoin(
                PersonalizedLesson,
                (PersonalizedLesson.topic_id == Topic.id)
                & (PersonalizedLesson.student_id == student_id),
            )
            .where(
                Topic.is_approved.is_(True),
                Topic.sss_level == sp.sss_level,
                Topic.term == (term if term is not None else sp.active_term),
                Topic.subject_id.in_(enrolled_subject_ids),
            )
        )
    else:
        q = (
            select(Topic, Subject.slug)
            .join(Subject, Subject.id == Topic.subject_id)
            .where(
                Topic.is_approved.is_(True),
                Topic.sss_level == sp.sss_level,
                Topic.term == (term if term is not None else sp.active_term),
                Topic.subject_id.in_(enrolled_subject_ids),
            )
        )

    if subject is not None:
        q = q.where(Subject.slug == subject.lower())

    q = q.order_by(Topic.created_at.asc(), Topic.title.asc())
    raw_rows = db.execute(q).all()
    if personalized_lessons_available:
        rows = raw_rows
    else:
        rows = [(topic, None, subject_slug) for topic, subject_slug in raw_rows]
    rag_service = RagRetrieveService()
    payload = []
    readiness_check_failed = False
    readiness_error_detail = ""
    for topic, personalized_lesson, subject_slug in rows:
        lesson_ready = _has_cached_personalized_lesson(personalized_lesson)
        unavailable_reason = None

        if not lesson_ready:
            try:
                lesson_ready = rag_service.topic_has_chunks(
                    subject=str(subject_slug),
                    sss_level=str(topic.sss_level),
                    term=int(topic.term),
                    topic_id=topic.id,
                    approved_only=True,
                    curriculum_version_id=topic.curriculum_version_id,
                )
            except RagRetrieveServiceError as exc:
                lesson_ready = False
                readiness_check_failed = True
                readiness_error_detail = str(exc)
                unavailable_reason = str(exc)

        if not lesson_ready and unavailable_reason is None:
            unavailable_reason = "No approved curriculum chunks found for this topic/scope."

        if not include_unready and not lesson_ready:
            continue

        description = (
            personalized_lesson.summary
            if personalized_lesson and personalized_lesson.summary
            else _clean_topic_description(topic.description, topic.title)
        )
        payload.append(
            {
                "topic_id": str(topic.id),
                "title": topic.title,
                "description": description,
                "lesson_title": personalized_lesson.title if personalized_lesson else None,
                "estimated_duration_minutes": (
                    personalized_lesson.estimated_duration_minutes if personalized_lesson else None
                ),
                "lesson_ready": lesson_ready,
                "lesson_unavailable_reason": unavailable_reason,
                "sss_level": topic.sss_level,
                "term": topic.term,
                "subject_id": str(topic.subject_id),
            }
        )

    if readiness_check_failed and not include_unready and not payload:
        raise HTTPException(status_code=503, detail=f"Lesson readiness check failed: {readiness_error_detail}")

    return payload
