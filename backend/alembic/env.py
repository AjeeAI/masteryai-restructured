import sys
from pathlib import Path
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# --- PATH FIX: This allows 'from backend...' to work from any folder ---
# It adds the parent directory of 'backend' to your Python path dynamically
BASE_DIR = Path(__file__).resolve().parents[2]
sys.path.append(str(BASE_DIR))

# Now these imports will work without setting $env:PYTHONPATH
from backend.core.database import Base
from backend.core.config import settings

# Import all models for detection
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
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.
    This configures the context with just a URL and not an Engine.
    Calls to 'run_migrations' will script the SQL to the script output.
    """
    url = settings.database_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode.
    In this scenario we need to create an Engine and associate a connection with the context.
    """
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
            # This helps avoid metadata issues during complex migrations
            render_as_batch=False 
        )

        with context.begin_transaction():
            context.run_migrations()

# Standard Alembic logic to decide which mode to use
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()