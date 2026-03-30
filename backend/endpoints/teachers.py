"""Teacher intelligence endpoints.

Implements section-6 APIs for class management, analytics, and interventions.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.repositories.teacher_repo import TeacherRepository
from backend.schemas.teacher_schema import (
    TeacherAlertsOut,
    TeacherAssignmentCreateIn,
    TeacherAssignmentOutcomeSummaryOut,
    TeacherAssignmentOut,
    TeacherBulkAssignmentCreateIn,
    TeacherBulkAssignmentOut,
    TeacherBulkInterventionCreateIn,
    TeacherBulkInterventionOut,
    TeacherClassCreateIn,
    TeacherConceptCompareOut,
    TeacherClassDashboardOut,
    TeacherConceptStudentDrilldownOut,
    TeacherClassGraphOut,
    TeacherClassEnrollIn,
    TeacherClassEnrollOut,
    TeacherClassHeatmapOut,
    TeacherExportOut,
    TeacherInterventionOutcomeSummaryOut,
    TeacherInterventionQueueOut,
    TeacherClassListOut,
    TeacherNextLessonClusterPlanOut,
    TeacherClassOut,
    TeacherGraphPlaybookOut,
    TeacherInterventionCreateIn,
    TeacherInterventionUpdateIn,
    TeacherInterventionOut,
    TeacherRepeatRiskSummaryOut,
    TeacherRiskMatrixOut,
    TeacherPresentationOut,
    TeacherStudentTimelineOut,
    TeacherStudentConceptTrendOut,
)
from backend.services.teacher_analytics_service import TeacherAnalyticsService
from backend.services.teacher_service import (
    TeacherService,
    TeacherServiceConflictError,
    TeacherServiceNotFoundError,
    TeacherServiceUnauthorizedError,
    TeacherServiceValidationError,
)

router = APIRouter(prefix="/teachers", tags=["Teacher Intelligence"])


def _teacher_service(db: Session) -> TeacherService:
    return TeacherService(TeacherRepository(db))


def _analytics_service(db: Session) -> TeacherAnalyticsService:
    return TeacherAnalyticsService(TeacherRepository(db))


@router.get("/classes", response_model=TeacherClassListOut)
def list_teacher_classes(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List classes owned by the authenticated teacher."""
    try:
        return _teacher_service(db).list_classes(teacher_id=current_user.id)
    except TeacherServiceUnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except TeacherServiceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/classes", response_model=TeacherClassOut, status_code=status.HTTP_201_CREATED)
def create_teacher_class(
    payload: TeacherClassCreateIn,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create a new class/cohort in a strict curriculum scope."""
    try:
        return _teacher_service(db).create_class(teacher_id=current_user.id, payload=payload)
    except TeacherServiceUnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except TeacherServiceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except TeacherServiceConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except TeacherServiceValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/classes/{class_id}/enroll", response_model=TeacherClassEnrollOut)
def enroll_students(
    class_id: UUID,
    payload: TeacherClassEnrollIn,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Enroll students into a teacher-owned class."""
    try:
        return _teacher_service(db).enroll_students(
            teacher_id=current_user.id,
            class_id=class_id,
            payload=payload,
        )
    except TeacherServiceUnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except TeacherServiceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except TeacherServiceValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete("/classes/{class_id}/enroll/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_student_enrollment(
    class_id: UUID,
    student_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Remove an active student enrollment from a class."""
    try:
        deleted = _teacher_service(db).remove_student_enrollment(
            teacher_id=current_user.id,
            class_id=class_id,
            student_id=student_id,
        )
    except TeacherServiceUnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except TeacherServiceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active enrollment not found for student in this class.",
        )
    return None


@router.get("/classes/{class_id}/dashboard", response_model=TeacherClassDashboardOut)
def class_dashboard(
    class_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return class-level KPI dashboard."""
    try:
        return _analytics_service(db).get_class_dashboard(teacher_id=current_user.id, class_id=class_id)
    except TeacherServiceUnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except TeacherServiceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/classes/{class_id}/heatmap", response_model=TeacherClassHeatmapOut)
def class_heatmap(
    class_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return concept-level class heatmap from mastery data."""
    try:
        return _analytics_service(db).get_class_heatmap(teacher_id=current_user.id, class_id=class_id)
    except TeacherServiceUnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except TeacherServiceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/classes/{class_id}/graph-summary", response_model=TeacherClassGraphOut)
def class_graph_summary(
    class_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return graph-backed concept blockers and next class move for a teacher-owned class."""
    try:
        return _analytics_service(db).get_class_graph_summary(teacher_id=current_user.id, class_id=class_id)
    except TeacherServiceUnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except TeacherServiceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/classes/{class_id}/graph-playbook", response_model=TeacherGraphPlaybookOut)
def class_graph_playbook(
    class_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return recommended teacher actions derived from graph blockers, weak clusters, and active alerts."""
    try:
        return _analytics_service(db).get_class_graph_playbook(teacher_id=current_user.id, class_id=class_id)
    except TeacherServiceUnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except TeacherServiceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/classes/{class_id}/intervention-queue", response_model=TeacherInterventionQueueOut)
def class_intervention_queue(
    class_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return a prioritized teacher action queue derived from graph blockers and repeat-risk evidence."""
    try:
        return _analytics_service(db).get_intervention_queue(teacher_id=current_user.id, class_id=class_id)
    except TeacherServiceUnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except TeacherServiceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/classes/{class_id}/next-cluster-plan", response_model=TeacherNextLessonClusterPlanOut)
def class_next_cluster_plan(
    class_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return the next teacher lesson cluster plan derived from graph readiness and blockers."""
    try:
        return _analytics_service(db).get_next_lesson_cluster_plan(teacher_id=current_user.id, class_id=class_id)
    except TeacherServiceUnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except TeacherServiceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/classes/{class_id}/next-cluster-plan/export", response_model=TeacherExportOut)
def class_next_cluster_plan_export(
    class_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return a teacher-ready export package for the graph-derived next lesson cluster plan."""
    try:
        return _analytics_service(db).get_next_cluster_plan_export(teacher_id=current_user.id, class_id=class_id)
    except TeacherServiceUnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except TeacherServiceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/classes/{class_id}/briefing/export", response_model=TeacherExportOut)
def class_briefing_export(
    class_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return a teacher-ready class briefing package with graph signal, plan, and current evidence."""
    try:
        return _analytics_service(db).get_class_briefing_export(teacher_id=current_user.id, class_id=class_id)
    except TeacherServiceUnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except TeacherServiceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/classes/{class_id}/presentation", response_model=TeacherPresentationOut)
def class_presentation(
    class_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return a single presentation-ready teacher payload for demo and briefing flows."""
    try:
        return _analytics_service(db).get_class_presentation(teacher_id=current_user.id, class_id=class_id)
    except TeacherServiceUnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except TeacherServiceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/classes/{class_id}/alerts", response_model=TeacherAlertsOut)
def class_alerts(
    class_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return inactivity/decline/prerequisite-failure alerts for class students."""
    try:
        return _analytics_service(db).get_class_alerts(teacher_id=current_user.id, class_id=class_id)
    except TeacherServiceUnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except TeacherServiceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/classes/{class_id}/intervention-outcomes", response_model=TeacherInterventionOutcomeSummaryOut)
def class_intervention_outcomes(
    class_id: UUID,
    concept_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return whether recent teacher interventions are followed by real mastery movement."""
    try:
        return _analytics_service(db).get_intervention_outcomes(
            teacher_id=current_user.id,
            class_id=class_id,
            concept_id=concept_id,
        )
    except TeacherServiceUnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except TeacherServiceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/classes/{class_id}/assignment-outcomes", response_model=TeacherAssignmentOutcomeSummaryOut)
def class_assignment_outcomes(
    class_id: UUID,
    concept_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return whether recent teacher assignments are followed by activity and mastery movement."""
    try:
        return _analytics_service(db).get_assignment_outcomes(
            teacher_id=current_user.id,
            class_id=class_id,
            concept_id=concept_id,
        )
    except TeacherServiceUnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except TeacherServiceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/classes/{class_id}/repeat-risk", response_model=TeacherRepeatRiskSummaryOut)
def class_repeat_risk(
    class_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return students repeatedly driving blockers or weak concept clusters across the class graph."""
    try:
        return _analytics_service(db).get_repeat_risk_summary(teacher_id=current_user.id, class_id=class_id)
    except TeacherServiceUnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except TeacherServiceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/classes/{class_id}/risk-matrix", response_model=TeacherRiskMatrixOut)
def class_risk_matrix(
    class_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return a class-wide student vs concept comparison matrix for the current blocked and weak graph nodes."""
    try:
        return _analytics_service(db).get_student_risk_matrix(teacher_id=current_user.id, class_id=class_id)
    except TeacherServiceUnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except TeacherServiceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/classes/{class_id}/concept-compare", response_model=TeacherConceptCompareOut)
def class_concept_compare(
    class_id: UUID,
    left_concept_id: str = Query(...),
    right_concept_id: str = Query(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Compare two mapped graph concepts across the same class roster to decide what to reteach first."""
    try:
        return _analytics_service(db).get_concept_compare(
            teacher_id=current_user.id,
            class_id=class_id,
            left_concept_id=left_concept_id,
            right_concept_id=right_concept_id,
        )
    except TeacherServiceUnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except TeacherServiceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except TeacherServiceValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/classes/{class_id}/concept-compare/export", response_model=TeacherExportOut)
def class_concept_compare_export(
    class_id: UUID,
    left_concept_id: str = Query(...),
    right_concept_id: str = Query(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return a teacher-ready export package for a two-concept graph comparison."""
    try:
        return _analytics_service(db).get_concept_compare_export(
            teacher_id=current_user.id,
            class_id=class_id,
            left_concept_id=left_concept_id,
            right_concept_id=right_concept_id,
        )
    except TeacherServiceUnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except TeacherServiceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except TeacherServiceValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/classes/{class_id}/students/{student_id}/timeline", response_model=TeacherStudentTimelineOut)
def student_timeline(
    class_id: UUID,
    student_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return detailed timeline for a student in a class."""
    try:
        return _analytics_service(db).get_student_timeline(
            teacher_id=current_user.id,
            class_id=class_id,
            student_id=student_id,
            limit=limit,
        )
    except TeacherServiceUnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except TeacherServiceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/classes/{class_id}/students/{student_id}/concepts/{concept_id}/trend", response_model=TeacherStudentConceptTrendOut)
def student_concept_trend(
    class_id: UUID,
    student_id: UUID,
    concept_id: str,
    days: int = Query(default=30, ge=7, le=90),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return current concept-path mastery and recent deltas for one student in the class graph."""
    try:
        return _analytics_service(db).get_student_concept_trend(
            teacher_id=current_user.id,
            class_id=class_id,
            student_id=student_id,
            concept_id=concept_id,
            days=days,
        )
    except TeacherServiceUnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except TeacherServiceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/classes/{class_id}/students/{student_id}/concepts/{concept_id}/export", response_model=TeacherExportOut)
def student_concept_export(
    class_id: UUID,
    student_id: UUID,
    concept_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return a teacher-ready export package for one student's focused concept evidence."""
    try:
        return _analytics_service(db).get_student_focus_export(
            teacher_id=current_user.id,
            class_id=class_id,
            student_id=student_id,
            concept_id=concept_id,
        )
    except TeacherServiceUnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except TeacherServiceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/classes/{class_id}/concepts/{concept_id}/students", response_model=TeacherConceptStudentDrilldownOut)
def concept_student_drilldown(
    class_id: UUID,
    concept_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return the students driving a concept blocker or weak node inside the class graph."""
    try:
        return _analytics_service(db).get_concept_student_drilldown(
            teacher_id=current_user.id,
            class_id=class_id,
            concept_id=concept_id,
        )
    except TeacherServiceUnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except TeacherServiceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/assignments", response_model=TeacherAssignmentOut, status_code=status.HTTP_201_CREATED)
def create_assignment(
    payload: TeacherAssignmentCreateIn,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create a teacher assignment for class or student targets."""
    try:
        return _teacher_service(db).create_assignment(teacher_id=current_user.id, payload=payload)
    except TeacherServiceUnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except TeacherServiceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except TeacherServiceValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/assignments/bulk", response_model=TeacherBulkAssignmentOut, status_code=status.HTTP_201_CREATED)
def create_bulk_assignments(
    payload: TeacherBulkAssignmentCreateIn,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create the same assignment across multiple target students in one request."""
    try:
        return _teacher_service(db).create_bulk_assignments(teacher_id=current_user.id, payload=payload)
    except TeacherServiceUnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except TeacherServiceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except TeacherServiceValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/interventions", response_model=TeacherInterventionOut, status_code=status.HTTP_201_CREATED)
def create_intervention(
    payload: TeacherInterventionCreateIn,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create intervention notes/flags for at-risk students."""
    try:
        return _teacher_service(db).create_intervention(teacher_id=current_user.id, payload=payload)
    except TeacherServiceUnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except TeacherServiceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except TeacherServiceValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/interventions/bulk", response_model=TeacherBulkInterventionOut, status_code=status.HTTP_201_CREATED)
def create_bulk_interventions(
    payload: TeacherBulkInterventionCreateIn,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create the same intervention across multiple target students in one request."""
    try:
        return _teacher_service(db).create_bulk_interventions(teacher_id=current_user.id, payload=payload)
    except TeacherServiceUnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except TeacherServiceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except TeacherServiceValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.patch("/interventions/{intervention_id}", response_model=TeacherInterventionOut)
def update_intervention(
    intervention_id: UUID,
    payload: TeacherInterventionUpdateIn,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Resolve or dismiss a teacher intervention."""
    try:
        return _teacher_service(db).update_intervention(
            teacher_id=current_user.id,
            intervention_id=intervention_id,
            payload=payload,
        )
    except TeacherServiceUnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except TeacherServiceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except TeacherServiceValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
