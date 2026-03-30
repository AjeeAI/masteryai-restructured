"""Lesson content delivery endpoints.

Exposes topic lesson retrieval with student-scope authorization checks.
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.schemas.lesson_cockpit_schema import LessonCockpitBootstrapIn, LessonCockpitBootstrapOut
from backend.schemas.lesson_schema import LessonPrewarmIn, LessonPrewarmOut, TopicLessonResponse
from backend.services.course_experience_service import CourseExperienceService
from backend.services.dashboard_experience_service import DashboardExperienceService
from backend.services.lesson_cockpit_service import LessonCockpitService
from backend.services.lesson_experience_service import LessonExperienceService
from backend.services.prewarm_job_service import PrewarmJobService
from backend.services.lesson_service import (
    fetch_topic_lesson,
    LessonNotFound,
    ForbiddenLessonAccess,
    LessonGenerationError,
)

router = APIRouter(prefix="/learning", tags=["Lessons"])


@router.post("/lesson/cockpit", response_model=LessonCockpitBootstrapOut)
def get_lesson_cockpit(
    payload: LessonCockpitBootstrapIn,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if payload.student_id != current_user.id:
        raise HTTPException(status_code=403, detail="student_id must match authenticated user id")

    try:
        return LessonCockpitService(db).bootstrap(payload)
    except LessonNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ForbiddenLessonAccess as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except LessonGenerationError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.get("/topics/{topic_id}/lesson", response_model=TopicLessonResponse)
def get_topic_lesson(
    topic_id: uuid.UUID,
    student_id: uuid.UUID = Query(..., description="Student UUID for curriculum scope enforcement"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return lesson content blocks for a specific topic.

    Access is restricted to topics that are valid for the requesting student's
    configured learning scope.
    """
    if student_id != current_user.id:
        raise HTTPException(status_code=403, detail="student_id must match authenticated user id")
    try:
        return fetch_topic_lesson(db=db, topic_id=topic_id, student_id=student_id)
    except LessonNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ForbiddenLessonAccess as e:
        raise HTTPException(status_code=403, detail=str(e))
    except LessonGenerationError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected server error: {e}")


@router.post("/lesson/prewarm", response_model=LessonPrewarmOut)
def prewarm_lessons(
    payload: LessonPrewarmIn,
    current_user=Depends(get_current_user),
):
    if payload.student_id != current_user.id:
        raise HTTPException(status_code=403, detail="student_id must match authenticated user id")

    result = LessonExperienceService.prewarm_related_topics(
        student_id=payload.student_id,
        subject=payload.subject,
        sss_level=payload.sss_level,
        term=int(payload.term),
        topic_ids=list(payload.topic_ids),
    )
    queued_job_ids: list[str] = []
    queued_lesson_job = PrewarmJobService.enqueue_lesson_related_job(
        student_id=payload.student_id,
        subject=payload.subject,
        sss_level=payload.sss_level,
        term=int(payload.term),
        topic_ids=list(payload.topic_ids),
    )
    if queued_lesson_job:
        queued_job_ids.append(str(queued_lesson_job))
    CourseExperienceService.prewarm_scope(
        student_id=payload.student_id,
        subject=payload.subject,
        term=int(payload.term),
    )
    queued_scope_job = PrewarmJobService.enqueue_course_scope_job(
        student_id=payload.student_id,
        subject=payload.subject,
        term=int(payload.term),
    )
    if queued_scope_job:
        queued_job_ids.append(str(queued_scope_job))
    DashboardExperienceService.prewarm(
        student_id=payload.student_id,
        subject=payload.subject,
    )
    return LessonPrewarmOut(
        requested_topic_ids=[str(topic_id) for topic_id in payload.topic_ids],
        warmed_topic_ids=result["warmed_topic_ids"],
        cache_hit_topic_ids=result["cache_hit_topic_ids"],
        failed_topic_ids=result["failed_topic_ids"],
        queued_job_ids=queued_job_ids,
    )
