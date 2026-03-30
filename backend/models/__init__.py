"""Model registry imports.

Import all ORM model modules so SQLAlchemy relationship strings
resolve deterministically at runtime.
"""

# Core domain models
from backend.models.user import User  # noqa: F401
from backend.models.subject import Subject  # noqa: F401
from backend.models.topic import Topic  # noqa: F401
from backend.models.lesson import Lesson, LessonBlock  # noqa: F401
from backend.models.personalized_lesson import PersonalizedLesson  # noqa: F401
from backend.models.student import StudentProfile, StudentSubject, LearningPreference  # noqa: F401

# Auth/session/chat
from backend.models.tutor_session import TutorSession  # noqa: F401
from backend.models.tutor_message import TutorMessage  # noqa: F401

# Activity and mastery
from backend.models.activity import ActivityLog, DailyActivitySummary, StudentStats  # noqa: F401
from backend.models.student_concept_mastery import StudentConceptMastery  # noqa: F401
from backend.models.mastery_update_event import MasteryUpdateEvent  # noqa: F401
from backend.models.mastery_snapshot import MasterySnapshot  # noqa: F401
from backend.models.student_badge import StudentBadge  # noqa: F401
from backend.models.prewarm_job import PrewarmJob  # noqa: F401

# Diagnostic and quizzes
from backend.models.diagnostic import Diagnostic  # noqa: F401
from backend.models.diagnostic_attempt import DiagnosticAttempt  # noqa: F401
from backend.models.quiz import Quiz  # noqa: F401
from backend.models.quiz_question import QuizQuestion  # noqa: F401
from backend.models.quiz_attempt import QuizAttempt  # noqa: F401
from backend.models.quiz_answer import QuizAnswer  # noqa: F401
from backend.models.internal_quiz_attempt import InternalQuizAttempt  # noqa: F401

# Teacher/admin governance
from backend.models.teacher_class import TeacherClass  # noqa: F401
from backend.models.class_enrollment import ClassEnrollment  # noqa: F401
from backend.models.teacher_assignment import TeacherAssignment  # noqa: F401
from backend.models.teacher_intervention import TeacherIntervention  # noqa: F401
from backend.models.curriculum_version import CurriculumVersion  # noqa: F401
from backend.models.curriculum_ingestion_job import CurriculumIngestionJob  # noqa: F401
from backend.models.curriculum_topic_map import CurriculumTopicMap  # noqa: F401
from backend.models.governance_hallucination import GovernanceHallucination  # noqa: F401
