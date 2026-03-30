"""Lesson repository (DB queries only)."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.lesson import Lesson, LessonBlock
from backend.models.personalized_lesson import PersonalizedLesson
from backend.models.student import StudentProfile, StudentSubject
from backend.models.subject import Subject
from backend.models.topic import Topic

def get_student_profile(db: Session, student_id: uuid.UUID) -> StudentProfile | None:
    stmt = select(StudentProfile).where(StudentProfile.student_id == student_id)
    return db.execute(stmt).scalar_one_or_none()

def student_enrolled_in_subject(db: Session, student_profile_id: uuid.UUID, subject_id: uuid.UUID) -> bool:
    stmt = select(StudentSubject).where(
        StudentSubject.student_profile_id == student_profile_id,
        StudentSubject.subject_id == subject_id
    )
    return db.execute(stmt).first() is not None

def get_topic_with_subject(db: Session, topic_id: uuid.UUID) -> tuple[Topic, Subject] | None:
    stmt = select(Topic, Subject).join(Subject, Subject.id == Topic.subject_id).where(Topic.id == topic_id)
    row = db.execute(stmt).first()
    if not row:
        return None
    return row[0], row[1]

def get_lesson_with_blocks(db: Session, topic_id: uuid.UUID) -> Lesson | None:
    stmt = select(Lesson).where(Lesson.topic_id == topic_id)
    return db.execute(stmt).scalar_one_or_none()


def upsert_lesson_with_blocks(
    db: Session,
    *,
    topic_id: uuid.UUID,
    title: str,
    summary: str | None,
    estimated_duration_minutes: int | None,
    content_blocks: list[dict[str, Any]],
) -> Lesson:
    row = get_lesson_with_blocks(db, topic_id)
    if row is None:
        row = Lesson(
            topic_id=topic_id,
            title=title,
            summary=summary,
            estimated_duration_minutes=estimated_duration_minutes,
        )
        db.add(row)
        db.flush()
    else:
        row.title = title
        row.summary = summary
        row.estimated_duration_minutes = estimated_duration_minutes

    row.blocks.clear()
    db.flush()

    for order_index, block in enumerate(content_blocks):
        block_type = str(block.get("type") or "").strip().lower()
        if block_type not in {"text", "video", "image", "example", "exercise"}:
            continue

        content: dict[str, Any]
        if block_type in {"video", "image"}:
            url = str(block.get("url") or "").strip()
            if not url:
                continue
            content = {"url": url}
        else:
            value = block.get("value")
            if isinstance(value, dict):
                content = dict(value)
            else:
                text_value = str(value or "").strip()
                if not text_value:
                    continue
                content = {"text": text_value}

            heading = str(block.get("heading") or "").strip()
            if heading:
                content["heading"] = heading

        row.blocks.append(
            LessonBlock(
                block_type=block_type,
                content=content,
                order_index=order_index,
            )
        )

    db.flush()
    return row


def ensure_personalized_lessons_table(db: Session) -> None:
    if db is None:
        return
    bind = db.get_bind()
    PersonalizedLesson.__table__.create(bind=bind, checkfirst=True)


def get_personalized_lesson(
    db: Session,
    *,
    student_id: uuid.UUID,
    topic_id: uuid.UUID,
) -> PersonalizedLesson | None:
    if db is None:
        return None
    stmt = select(PersonalizedLesson).where(
        PersonalizedLesson.student_id == student_id,
        PersonalizedLesson.topic_id == topic_id,
    )
    return db.execute(stmt).scalar_one_or_none()


def upsert_personalized_lesson(
    db: Session,
    *,
    student_id: uuid.UUID,
    topic_id: uuid.UUID,
    curriculum_version_id: uuid.UUID | None,
    title: str,
    summary: str | None,
    estimated_duration_minutes: int | None,
    content_blocks: list,
    source_chunk_ids: list[str],
    generation_metadata: dict,
) -> PersonalizedLesson:
    row = get_personalized_lesson(db, student_id=student_id, topic_id=topic_id)
    if row is None:
        row = PersonalizedLesson(
            student_id=student_id,
            topic_id=topic_id,
            curriculum_version_id=curriculum_version_id,
            title=title,
            summary=summary,
            estimated_duration_minutes=estimated_duration_minutes,
            content_blocks=list(content_blocks or []),
            source_chunk_ids=list(source_chunk_ids or []),
            generation_metadata=dict(generation_metadata or {}),
        )
        db.add(row)
        db.flush()
        return row

    row.curriculum_version_id = curriculum_version_id
    row.title = title
    row.summary = summary
    row.estimated_duration_minutes = estimated_duration_minutes
    row.content_blocks = list(content_blocks or [])
    row.source_chunk_ids = list(source_chunk_ids or [])
    row.generation_metadata = dict(generation_metadata or {})
    db.flush()
    return row
