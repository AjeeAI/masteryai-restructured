from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

from backend.core.database import Base
from backend.core.config import settings

# Import models so Alembic can detect them
from backend.models.activity import ActivityLog, DailyActivitySummary, StudentStats
from backend.models.diagnostic import Diagnostic
from backend.models.diagnostic_attempt import DiagnosticAttempt
from backend.models.lesson import Lesson, LessonBlock
from backend.models.student import LearningPreference, StudentProfile, StudentSubject
from backend.models.subject import Subject
from backend.models.topic import Topic
from backend.models.tutor_message import TutorMessage
from backend.models.tutor_session import TutorSession
from backend.models.internal_quiz_attempt import InternalQuizAttempt
from backend.models.user import User

from backend.models.quiz import Quiz
from backend.models.quiz_question import QuizQuestion
from backend.models.quiz_attempt import QuizAttempt
from backend.models.quiz_answer import QuizAnswer
from backend.models.student_concept_mastery import StudentConceptMastery
from backend.models.mastery_update_event import MasteryUpdateEvent
from backend.models.mastery_snapshot import MasterySnapshot
from backend.models.student_badge import StudentBadge
from backend.models.teacher_class import TeacherClass
from backend.models.class_enrollment import ClassEnrollment
from backend.models.teacher_assignment import TeacherAssignment
from backend.models.teacher_intervention import TeacherIntervention

config = context.config
fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_online():
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = settings.database_url

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()
            
run_migrations_online()