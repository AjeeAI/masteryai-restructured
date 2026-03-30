"""Reset demo-specific rows (teacher + student) without touching curriculum data.

Usage:
  python -m backend.scripts.reset_demo_state
"""

from __future__ import annotations

import argparse
import os

from sqlalchemy.orm import Session

from backend.core.database import SessionLocal
from backend.models.activity import ActivityLog, DailyActivitySummary, StudentStats
from backend.models.class_enrollment import ClassEnrollment
from backend.models.mastery_update_event import MasteryUpdateEvent
from backend.models.student import StudentProfile, StudentSubject
from backend.models.student_concept_mastery import StudentConceptMastery
from backend.models.teacher_assignment import TeacherAssignment
from backend.models.teacher_class import TeacherClass
from backend.models.teacher_intervention import TeacherIntervention
from backend.models.tutor_message import TutorMessage
from backend.models.tutor_session import TutorSession
from backend.models.user import User


def _env_default(name: str, fallback: str) -> str:
    return (os.getenv(name) or fallback).strip()


def _delete_by_student(db: Session, student_id):
    db.query(ActivityLog).filter(ActivityLog.student_id == student_id).delete(synchronize_session=False)
    db.query(DailyActivitySummary).filter(DailyActivitySummary.student_id == student_id).delete(synchronize_session=False)
    db.query(StudentStats).filter(StudentStats.student_id == student_id).delete(synchronize_session=False)
    db.query(StudentConceptMastery).filter(StudentConceptMastery.student_id == student_id).delete(synchronize_session=False)
    db.query(MasteryUpdateEvent).filter(MasteryUpdateEvent.student_id == student_id).delete(synchronize_session=False)
    db.query(TutorMessage).filter(TutorMessage.student_id == student_id).delete(synchronize_session=False)
    db.query(TutorSession).filter(TutorSession.student_id == student_id).delete(synchronize_session=False)
    db.query(StudentSubject).filter(
        StudentSubject.student_profile_id.in_(
            db.query(StudentProfile.id).filter(StudentProfile.student_id == student_id)
        )
    ).delete(synchronize_session=False)
    db.query(StudentProfile).filter(StudentProfile.student_id == student_id).delete(synchronize_session=False)


def _delete_by_teacher(db: Session, teacher_id):
    class_ids = [row.id for row in db.query(TeacherClass.id).filter(TeacherClass.teacher_id == teacher_id).all()]
    if class_ids:
        db.query(ClassEnrollment).filter(ClassEnrollment.class_id.in_(class_ids)).delete(synchronize_session=False)
        db.query(TeacherAssignment).filter(TeacherAssignment.class_id.in_(class_ids)).delete(synchronize_session=False)
        db.query(TeacherIntervention).filter(TeacherIntervention.class_id.in_(class_ids)).delete(synchronize_session=False)
        db.query(TeacherClass).filter(TeacherClass.id.in_(class_ids)).delete(synchronize_session=False)
    db.query(TeacherAssignment).filter(TeacherAssignment.teacher_id == teacher_id).delete(synchronize_session=False)
    db.query(TeacherIntervention).filter(TeacherIntervention.teacher_id == teacher_id).delete(synchronize_session=False)


def run() -> None:
    parser = argparse.ArgumentParser(description="Remove demo users and related activity/graph data.")
    parser.add_argument("--teacher-email", default=_env_default("DEMO_TEACHER_EMAIL", "demo.teacher@masteryai.local"))
    parser.add_argument("--student-email", default=_env_default("DEMO_STUDENT_EMAIL", "demo.student@masteryai.local"))
    parser.add_argument(
        "--secondary-student-email",
        default=_env_default("DEMO_SECONDARY_STUDENT_EMAIL", "demo.student2@masteryai.local"),
    )
    args = parser.parse_args()

    db: Session = SessionLocal()
    try:
        teacher = db.query(User).filter(User.email == args.teacher_email).first()
        student = db.query(User).filter(User.email == args.student_email).first()
        secondary_student = db.query(User).filter(User.email == args.secondary_student_email).first()

        if student:
            _delete_by_student(db, student.id)
        if secondary_student:
            _delete_by_student(db, secondary_student.id)

        if teacher:
            _delete_by_teacher(db, teacher.id)

        if student:
            db.query(User).filter(User.id == student.id).delete(synchronize_session=False)
        if secondary_student:
            db.query(User).filter(User.id == secondary_student.id).delete(synchronize_session=False)
        if teacher:
            db.query(User).filter(User.id == teacher.id).delete(synchronize_session=False)

        db.commit()

        print("Demo reset complete.")
        print(f"Teacher removed: {bool(teacher)} ({args.teacher_email})")
        print(f"Student removed: {bool(student)} ({args.student_email})")
        print(f"Student 2 removed: {bool(secondary_student)} ({args.secondary_student_email})")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
