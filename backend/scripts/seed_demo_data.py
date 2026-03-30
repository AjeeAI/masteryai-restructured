"""Seed demo-ready teacher/student data for graph-first presentation flows.

Usage:
  python -m backend.scripts.seed_demo_data

Optional flags (also overridable via env vars):
  --subject math|english|civic
  --sss-level SSS1|SSS2|SSS3
  --term 1|2|3
  --teacher-email demo.teacher@masteryai.local
  --student-email demo.student@masteryai.local
  --class-name "Graph-First Cohort"
  --seed-secondary / --no-seed-secondary
  --secondary-student-email demo.student2@masteryai.local
  --secondary-student-name "Demo Student Two"
  --secondary-class-name "Graph-First Cohort B"
  --secondary-student-id <uuid>
  --seed-mastery / --no-seed-mastery
  --seed-assignments / --no-seed-assignments
  --seed-interventions / --no-seed-interventions
  --seed-activity / --no-seed-activity
  --attach-curriculum-version / --no-attach-curriculum-version
"""

from __future__ import annotations

import argparse
import os
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from backend.core.database import SessionLocal
from backend.models.activity import ActivityLog, StudentStats
from backend.models.class_enrollment import ClassEnrollment
from backend.models.curriculum_topic_map import CurriculumTopicMap
from backend.models.curriculum_version import CurriculumVersion
from backend.models.mastery_update_event import MasteryUpdateEvent
from backend.models.student import StudentProfile, StudentSubject
from backend.models.student_concept_mastery import StudentConceptMastery
from backend.models.subject import Subject
from backend.models.teacher_assignment import TeacherAssignment
from backend.models.teacher_class import TeacherClass
from backend.models.teacher_intervention import TeacherIntervention
from backend.models.topic import Topic
from backend.models.user import User
from backend.repositories.graph_repo import GraphRepository


SEED_PASSWORD_HASH = "$2b$12$5JY6jsA5q9ODaW6fNfcohOx5l6v3PK2hQd1qi97V6S9bxR5D8Qqbi"
DEFAULT_MASTER_SCORES = [0.32, 0.52, 0.7, 0.84, 0.61]
SECONDARY_MASTER_SCORES = [max(0.15, score - 0.12) for score in DEFAULT_MASTER_SCORES]


def _env_default(name: str, fallback: str) -> str:
    return (os.getenv(name) or fallback).strip()


def _split_name(display_name: str) -> tuple[str, str]:
    tokens = [token for token in (display_name or "").strip().split() if token]
    if not tokens:
        return "Demo", "User"
    if len(tokens) == 1:
        return tokens[0], "User"
    return tokens[0], " ".join(tokens[1:])


def _readable_concept_label(concept_id: str) -> str:
    value = str(concept_id or "").strip()
    if not value:
        return "Concept"
    try:
        uuid.UUID(value)
        return value
    except ValueError:
        pass
    token = value.rsplit(":", 1)[-1].strip().replace("-", " ").replace("_", " ")
    token = " ".join(token.split())
    return token.title() if token else value


def _upsert_user(db: Session, *, email: str, role: str, display_name: str, user_id: uuid.UUID | None) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user and user_id:
        user = db.query(User).filter(User.id == user_id).first()
    if not user:
        user = User(id=user_id or uuid.uuid4(), email=email, password_hash=SEED_PASSWORD_HASH)
        db.add(user)
        db.flush()

    first_name, last_name = _split_name(display_name)
    user.email = email
    user.password_hash = user.password_hash or SEED_PASSWORD_HASH
    user.first_name = first_name
    user.last_name = last_name
    user.display_name = display_name
    user.role = role
    user.is_active = True
    return user


def _upsert_profile(db: Session, *, student_id: uuid.UUID, sss_level: str, term: int) -> StudentProfile:
    profile = db.query(StudentProfile).filter(StudentProfile.student_id == student_id).first()
    if profile:
        profile.sss_level = sss_level
        profile.active_term = term
        return profile
    profile = StudentProfile(id=uuid.uuid4(), student_id=student_id, sss_level=sss_level, active_term=term)
    db.add(profile)
    db.flush()
    return profile


def _ensure_student_subject(db: Session, *, profile_id: uuid.UUID, subject_id: uuid.UUID) -> None:
    existing = db.query(StudentSubject).filter(
        StudentSubject.student_profile_id == profile_id,
        StudentSubject.subject_id == subject_id,
    ).first()
    if existing:
        return
    db.add(StudentSubject(id=uuid.uuid4(), student_profile_id=profile_id, subject_id=subject_id))


def _upsert_stats(db: Session, *, student_id: uuid.UUID) -> None:
    stats = db.query(StudentStats).filter(StudentStats.student_id == student_id).first()
    if not stats:
        stats = StudentStats(student_id=student_id, current_streak=0, max_streak=0, total_mastery_points=0, total_study_time_seconds=0)
        db.add(stats)
    stats.current_streak = max(stats.current_streak, 6)
    stats.max_streak = max(stats.max_streak, 12)
    stats.total_mastery_points = max(stats.total_mastery_points, 1200)
    stats.total_study_time_seconds = max(stats.total_study_time_seconds, 36000)


def _ensure_activity_log(
    db: Session,
    *,
    student_id: uuid.UUID,
    subject: str,
    term: int,
    event_type: str,
    ref_id: str,
    duration_seconds: int,
) -> None:
    existing = db.query(ActivityLog).filter(
        ActivityLog.student_id == student_id,
        ActivityLog.subject == subject,
        ActivityLog.term == term,
        ActivityLog.event_type == event_type,
        ActivityLog.ref_id == ref_id,
    ).first()
    if existing:
        return
    db.add(
        ActivityLog(
            id=uuid.uuid4(),
            student_id=student_id,
            subject=subject,
            term=term,
            event_type=event_type,
            ref_id=ref_id,
            duration_seconds=duration_seconds,
        )
    )


def _resolve_curriculum_version(db: Session, *, subject: str, sss_level: str, term: int) -> CurriculumVersion | None:
    return (
        db.query(CurriculumVersion)
        .filter(
            CurriculumVersion.subject == subject,
            CurriculumVersion.sss_level == sss_level,
            CurriculumVersion.term == term,
            CurriculumVersion.status.in_(["approved", "published"]),
        )
        .order_by(CurriculumVersion.approved_at.desc().nullslast(), CurriculumVersion.created_at.desc())
        .first()
    )


def _resolve_topics(
    db: Session,
    *,
    subject_id: uuid.UUID,
    sss_level: str,
    term: int,
) -> list[Topic]:
    return (
        db.query(Topic)
        .filter(
            Topic.subject_id == subject_id,
            Topic.sss_level == sss_level,
            Topic.term == term,
            Topic.is_approved.is_(True),
        )
        .order_by(Topic.created_at.asc(), Topic.title.asc())
        .all()
    )


def _group_maps_by_topic(maps: list[CurriculumTopicMap]) -> dict[str, list[CurriculumTopicMap]]:
    grouped: dict[str, list[CurriculumTopicMap]] = {}
    for mapping in maps:
        grouped.setdefault(str(mapping.topic_id), []).append(mapping)
    return grouped


def _pick_focus_topic(topics: list[Topic], maps_by_topic: dict[str, list[CurriculumTopicMap]]) -> Topic:
    if not topics:
        raise RuntimeError("No topics available to seed demo data.")
    scored = sorted(
        topics,
        key=lambda topic: len(maps_by_topic.get(str(topic.id), [])),
        reverse=True,
    )
    return scored[0]


def _seed_mastery(
    db: Session,
    *,
    student_id: uuid.UUID,
    subject: str,
    sss_level: str,
    term: int,
    concept_ids: list[str],
    scores: list[float] | None = None,
) -> tuple[list[dict], list[dict]]:
    repo = GraphRepository(db)
    scores = list(scores) if scores else DEFAULT_MASTER_SCORES
    concept_breakdown: list[dict] = []
    new_mastery: list[dict] = []

    for index, concept_id in enumerate(concept_ids):
        score = scores[index % len(scores)]
        prev_score = max(0.0, score - 0.18)
        repo.upsert_mastery(
            student_id=student_id,
            subject=subject,
            sss_level=sss_level,
            term=term,
            concept_id=concept_id,
            new_score=score,
            source="demo_seed",
            evaluated_at=datetime.now(timezone.utc),
        )
        concept_breakdown.append(
            {
                "concept_id": concept_id,
                "concept_label": _readable_concept_label(concept_id),
                "is_correct": score >= 0.7,
                "weight_change": 0.12 if score >= 0.7 else -0.05,
            }
        )
        new_mastery.append(
            {
                "concept_id": concept_id,
                "score": round(score, 4),
                "delta": round(score - prev_score, 4),
                "previous_score": round(prev_score, 4),
            }
        )

    return concept_breakdown, new_mastery


def _ensure_teacher_class(
    db: Session,
    *,
    teacher_id: uuid.UUID,
    subject: str,
    sss_level: str,
    term: int,
    name: str,
) -> TeacherClass:
    existing = db.query(TeacherClass).filter(
        TeacherClass.teacher_id == teacher_id,
        TeacherClass.subject == subject,
        TeacherClass.sss_level == sss_level,
        TeacherClass.term == term,
        TeacherClass.name == name,
    ).first()
    if existing:
        existing.is_active = True
        return existing
    row = TeacherClass(
        id=uuid.uuid4(),
        teacher_id=teacher_id,
        name=name,
        description=f"{sss_level} {subject.upper()} term {term} demo cohort",
        subject=subject,
        sss_level=sss_level,
        term=term,
        is_active=True,
    )
    db.add(row)
    db.flush()
    return row


def _ensure_enrollment(db: Session, *, class_id: uuid.UUID, student_id: uuid.UUID) -> None:
    existing = db.query(ClassEnrollment).filter(
        ClassEnrollment.class_id == class_id,
        ClassEnrollment.student_id == student_id,
    ).first()
    if existing:
        existing.status = "active"
        return
    db.add(
        ClassEnrollment(
            id=uuid.uuid4(),
            class_id=class_id,
            student_id=student_id,
            status="active",
        )
    )


def _ensure_assignment(
    db: Session,
    *,
    teacher_id: uuid.UUID,
    class_id: uuid.UUID,
    subject: str,
    sss_level: str,
    term: int,
    topic: Topic,
    focus_concept_id: str | None,
) -> None:
    existing = db.query(TeacherAssignment).filter(
        TeacherAssignment.teacher_id == teacher_id,
        TeacherAssignment.class_id == class_id,
        TeacherAssignment.assignment_type == "topic",
        TeacherAssignment.ref_id == str(topic.id),
    ).first()
    if existing:
        existing.status = "assigned"
        return
    db.add(
        TeacherAssignment(
            id=uuid.uuid4(),
            teacher_id=teacher_id,
            class_id=class_id,
            student_id=None,
            assignment_type="topic",
            concept_id=focus_concept_id,
            concept_label=_readable_concept_label(focus_concept_id or ""),
            ref_id=str(topic.id),
            title=f"Review: {topic.title}",
            instructions="Focus on the weakest concept and prepare one example to explain in class.",
            subject=subject,
            sss_level=sss_level,
            term=term,
            due_at=datetime.now(timezone.utc) + timedelta(days=3),
            status="assigned",
        )
    )


def _ensure_intervention(
    db: Session,
    *,
    teacher_id: uuid.UUID,
    class_id: uuid.UUID,
    student_id: uuid.UUID,
    subject: str,
    sss_level: str,
    term: int,
    focus_concept_id: str | None,
) -> None:
    existing = db.query(TeacherIntervention).filter(
        TeacherIntervention.teacher_id == teacher_id,
        TeacherIntervention.class_id == class_id,
        TeacherIntervention.student_id == student_id,
        TeacherIntervention.concept_id == focus_concept_id,
        TeacherIntervention.status == "open",
    ).first()
    if existing:
        return
    db.add(
        TeacherIntervention(
            id=uuid.uuid4(),
            teacher_id=teacher_id,
            class_id=class_id,
            student_id=student_id,
            intervention_type="support_plan",
            concept_id=focus_concept_id,
            concept_label=_readable_concept_label(focus_concept_id or ""),
            severity="medium",
            subject=subject,
            sss_level=sss_level,
            term=term,
            notes="Student is still building confidence on this concept; assign a guided recap and one checkpoint.",
            action_plan="Schedule a 10-minute recap, then have the learner explain one worked example aloud.",
            status="open",
        )
    )


def run() -> None:
    parser = argparse.ArgumentParser(description="Seed demo-ready data for graph-first presentation flows.")
    parser.add_argument("--subject", default=_env_default("DEMO_SUBJECT", "math"))
    parser.add_argument("--sss-level", default=_env_default("DEMO_SSS_LEVEL", "SSS1"))
    parser.add_argument("--term", type=int, default=int(_env_default("DEMO_TERM", "1") or "1"))
    parser.add_argument("--teacher-email", default=_env_default("DEMO_TEACHER_EMAIL", "demo.teacher@masteryai.local"))
    parser.add_argument("--student-email", default=_env_default("DEMO_STUDENT_EMAIL", "demo.student@masteryai.local"))
    parser.add_argument("--teacher-name", default=_env_default("DEMO_TEACHER_NAME", "Demo Teacher"))
    parser.add_argument("--student-name", default=_env_default("DEMO_STUDENT_NAME", "Demo Student"))
    parser.add_argument("--class-name", default=_env_default("DEMO_CLASS_NAME", "Graph-First Cohort"))
    parser.add_argument("--seed-secondary", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--secondary-student-email",
        default=_env_default("DEMO_SECONDARY_STUDENT_EMAIL", "demo.student2@masteryai.local"),
    )
    parser.add_argument(
        "--secondary-student-name",
        default=_env_default("DEMO_SECONDARY_STUDENT_NAME", "Demo Student Two"),
    )
    parser.add_argument(
        "--secondary-class-name",
        default=_env_default("DEMO_SECONDARY_CLASS_NAME", "Graph-First Cohort B"),
    )
    parser.add_argument("--seed-mastery", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--seed-assignments", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--seed-interventions", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--seed-activity", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--attach-curriculum-version", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--teacher-id", default=_env_default("DEMO_TEACHER_ID", ""))
    parser.add_argument("--student-id", default=_env_default("DEMO_STUDENT_ID", ""))
    parser.add_argument("--secondary-student-id", default=_env_default("DEMO_SECONDARY_STUDENT_ID", ""))
    args = parser.parse_args()

    subject_slug = args.subject.strip().lower()
    sss_level = args.sss_level.strip().upper()
    term = int(args.term)

    teacher_id = uuid.UUID(args.teacher_id) if args.teacher_id else None
    student_id = uuid.UUID(args.student_id) if args.student_id else None
    secondary_student_id = uuid.UUID(args.secondary_student_id) if args.secondary_student_id else None

    db: Session = SessionLocal()
    try:
        subject = db.query(Subject).filter(Subject.slug == subject_slug).first()
        if subject is None:
            subject = Subject(id=uuid.uuid4(), slug=subject_slug, name=subject_slug.title())
            db.add(subject)
            db.flush()

        topics = _resolve_topics(db, subject_id=subject.id, sss_level=sss_level, term=term)
        if not topics:
            raise RuntimeError(f"No approved topics found for {subject_slug} {sss_level} term {term}.")

        version = _resolve_curriculum_version(db, subject=subject_slug, sss_level=sss_level, term=term)
        if version is None:
            raise RuntimeError(
                f"No approved curriculum version found for {subject_slug} {sss_level} term {term}. "
                "Run curriculum ingestion/approval first."
            )

        maps = db.query(CurriculumTopicMap).filter(
            CurriculumTopicMap.version_id == version.id,
            CurriculumTopicMap.topic_id.in_([topic.id for topic in topics]),
        ).all()
        if not maps:
            raise RuntimeError(
                "No curriculum topic mappings found for the demo scope. "
                "Ensure ingestion generated concept mappings."
            )

        maps_by_topic = _group_maps_by_topic(maps)
        focus_topic = _pick_focus_topic(topics, maps_by_topic)
        focus_mappings = maps_by_topic.get(str(focus_topic.id), [])
        concept_ids = [str(mapping.concept_id) for mapping in focus_mappings if str(mapping.concept_id).strip()]
        focus_concept_id = concept_ids[0] if concept_ids else None

        if args.attach_curriculum_version:
            for topic in topics:
                if str(topic.id) not in maps_by_topic:
                    continue
                if topic.curriculum_version_id is None or topic.curriculum_version_id != version.id:
                    topic.curriculum_version_id = version.id

        teacher = _upsert_user(
            db,
            email=args.teacher_email,
            role="teacher",
            display_name=args.teacher_name,
            user_id=teacher_id,
        )
        student = _upsert_user(
            db,
            email=args.student_email,
            role="student",
            display_name=args.student_name,
            user_id=student_id,
        )

        secondary_student = None
        if args.seed_secondary:
            secondary_student = _upsert_user(
                db,
                email=args.secondary_student_email,
                role="student",
                display_name=args.secondary_student_name,
                user_id=secondary_student_id,
            )

        profile = _upsert_profile(db, student_id=student.id, sss_level=sss_level, term=term)
        _ensure_student_subject(db, profile_id=profile.id, subject_id=subject.id)
        _upsert_stats(db, student_id=student.id)
        if secondary_student:
            secondary_profile = _upsert_profile(db, student_id=secondary_student.id, sss_level=sss_level, term=term)
            _ensure_student_subject(db, profile_id=secondary_profile.id, subject_id=subject.id)
            _upsert_stats(db, student_id=secondary_student.id)

        teacher_class = _ensure_teacher_class(
            db,
            teacher_id=teacher.id,
            subject=subject_slug,
            sss_level=sss_level,
            term=term,
            name=args.class_name,
        )
        _ensure_enrollment(db, class_id=teacher_class.id, student_id=student.id)
        secondary_class = None
        if secondary_student:
            secondary_class = _ensure_teacher_class(
                db,
                teacher_id=teacher.id,
                subject=subject_slug,
                sss_level=sss_level,
                term=term,
                name=args.secondary_class_name,
            )
            _ensure_enrollment(db, class_id=secondary_class.id, student_id=secondary_student.id)

        if args.seed_assignments:
            _ensure_assignment(
                db,
                teacher_id=teacher.id,
                class_id=teacher_class.id,
                subject=subject_slug,
                sss_level=sss_level,
                term=term,
                topic=focus_topic,
                focus_concept_id=focus_concept_id,
            )
            if secondary_class:
                _ensure_assignment(
                    db,
                    teacher_id=teacher.id,
                    class_id=secondary_class.id,
                    subject=subject_slug,
                    sss_level=sss_level,
                    term=term,
                    topic=focus_topic,
                    focus_concept_id=focus_concept_id,
                )

        if args.seed_interventions:
            _ensure_intervention(
                db,
                teacher_id=teacher.id,
                class_id=teacher_class.id,
                student_id=student.id,
                subject=subject_slug,
                sss_level=sss_level,
                term=term,
                focus_concept_id=focus_concept_id,
            )
            if secondary_student and secondary_class:
                _ensure_intervention(
                    db,
                    teacher_id=teacher.id,
                    class_id=secondary_class.id,
                    student_id=secondary_student.id,
                    subject=subject_slug,
                    sss_level=sss_level,
                    term=term,
                    focus_concept_id=focus_concept_id,
                )

        if args.seed_mastery and concept_ids:
            def _seed_student_mastery(target_student: User, *, scores: list[float]) -> None:
                existing_mastery = db.query(StudentConceptMastery).filter(
                    StudentConceptMastery.student_id == target_student.id,
                    StudentConceptMastery.subject == subject_slug,
                    StudentConceptMastery.sss_level == sss_level,
                    StudentConceptMastery.term == term,
                ).count()
                if existing_mastery:
                    return
                concept_breakdown, new_mastery = _seed_mastery(
                    db,
                    student_id=target_student.id,
                    subject=subject_slug,
                    sss_level=sss_level,
                    term=term,
                    concept_ids=concept_ids[:6],
                    scores=scores,
                )
                db.add(
                    MasteryUpdateEvent(
                        id=uuid.uuid4(),
                        student_id=target_student.id,
                        quiz_id=None,
                        attempt_id=None,
                        subject=subject_slug,
                        sss_level=sss_level,
                        term=term,
                        source="practice",
                        concept_breakdown=concept_breakdown,
                        new_mastery=new_mastery,
                    )
                )

            _seed_student_mastery(student, scores=DEFAULT_MASTER_SCORES)
            if secondary_student:
                _seed_student_mastery(secondary_student, scores=SECONDARY_MASTER_SCORES)

        if args.seed_activity:
            _ensure_activity_log(
                db,
                student_id=student.id,
                subject=subject_slug,
                term=term,
                event_type="lesson_viewed",
                ref_id=str(focus_topic.id),
                duration_seconds=420,
            )
            _ensure_activity_log(
                db,
                student_id=student.id,
                subject=subject_slug,
                term=term,
                event_type="quiz_submitted",
                ref_id=str(focus_topic.id),
                duration_seconds=300,
            )
            if secondary_student:
                _ensure_activity_log(
                    db,
                    student_id=secondary_student.id,
                    subject=subject_slug,
                    term=term,
                    event_type="lesson_viewed",
                    ref_id=str(focus_topic.id),
                    duration_seconds=360,
                )
                _ensure_activity_log(
                    db,
                    student_id=secondary_student.id,
                    subject=subject_slug,
                    term=term,
                    event_type="quiz_submitted",
                    ref_id=str(focus_topic.id),
                    duration_seconds=260,
                )

        db.commit()

        print("Demo seed complete.")
        print(f"Scope: {subject_slug} {sss_level} term {term}")
        print(f"Teacher: {teacher.email} ({teacher.id})")
        print(f"Student: {student.email} ({student.id})")
        if secondary_student:
            print(f"Student 2: {secondary_student.email} ({secondary_student.id})")
        print(f"Class: {teacher_class.name} ({teacher_class.id})")
        if secondary_class:
            print(f"Class 2: {secondary_class.name} ({secondary_class.id})")
        print(f"Focus topic: {focus_topic.title}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
