"""create quiz lifecycle tables

Revision ID: 0009_quiz_tables
Revises: 0008_tutor_sessions_internal
Create Date: 2026-02-26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0009_quiz_tables"
down_revision = "0008_tutor_sessions_internal"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # -----------------------------
    # quizzes
    # -----------------------------
    if "quizzes" not in existing_tables:
        op.create_table(
            "quizzes",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "student_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("subject", sa.String(length=50), nullable=False),
            sa.Column("sss_level", sa.String(length=10), nullable=False),
            sa.Column("term", sa.Integer(), nullable=False),
            sa.Column(
                "topic_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("topics.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("purpose", sa.String(length=50), nullable=True),
            sa.Column("difficulty", sa.String(length=20), nullable=True),
            sa.Column("num_questions", sa.Integer(), nullable=False, server_default="10"),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="generated"),
            sa.Column("time_limit_seconds", sa.Integer(), nullable=True),
            sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.CheckConstraint("subject IN ('math','english','civic')", name="ck_quizzes_subject"),
            sa.CheckConstraint("sss_level IN ('SSS1','SSS2','SSS3')", name="ck_quizzes_sss_level"),
            sa.CheckConstraint("term BETWEEN 1 AND 3", name="ck_quizzes_term"),
            sa.CheckConstraint("num_questions > 0", name="ck_quizzes_num_questions"),
            sa.CheckConstraint("status IN ('generated','submitted','archived')", name="ck_quizzes_status"),
            sa.CheckConstraint("(time_limit_seconds IS NULL) OR (time_limit_seconds > 0)", name="ck_quizzes_time_limit"),
        )
        op.create_index("ix_quizzes_student_id", "quizzes", ["student_id"])
        op.create_index("ix_quizzes_topic_id", "quizzes", ["topic_id"])
        op.create_index("ix_quizzes_scope", "quizzes", ["subject", "sss_level", "term"])
        op.create_index("ix_quizzes_status", "quizzes", ["status"])

    # -----------------------------
    # quiz_questions
    # -----------------------------
    if "quiz_questions" not in existing_tables:
        op.create_table(
            "quiz_questions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "quiz_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("quizzes.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("question_number", sa.Integer(), nullable=False),
            sa.Column("question_text", sa.Text(), nullable=False),
            sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
            sa.Column("correct_answer", sa.String(length=255), nullable=True),
            sa.Column("explanation", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.CheckConstraint("question_number > 0", name="ck_quiz_questions_question_number"),
            sa.UniqueConstraint("quiz_id", "question_number", name="uq_quiz_questions_quiz_id_question_number"),
        )
        op.create_index("ix_quiz_questions_quiz_id", "quiz_questions", ["quiz_id"])

    # -----------------------------
    # quiz_attempts
    # -----------------------------
    if "quiz_attempts" not in existing_tables:
        op.create_table(
            "quiz_attempts",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "quiz_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("quizzes.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "student_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("time_taken_seconds", sa.Integer(), nullable=False),
            sa.Column("score", sa.Numeric(5, 2), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="submitted"),
            sa.Column("raw_answers", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.CheckConstraint("time_taken_seconds >= 0", name="ck_quiz_attempts_time_taken"),
            sa.CheckConstraint("(score IS NULL) OR (score >= 0 AND score <= 100)", name="ck_quiz_attempts_score"),
            sa.CheckConstraint("status IN ('submitted','graded')", name="ck_quiz_attempts_status"),
        )
        op.create_index("ix_quiz_attempts_quiz_id", "quiz_attempts", ["quiz_id"])
        op.create_index("ix_quiz_attempts_student_id", "quiz_attempts", ["student_id"])

    # -----------------------------
    # quiz_answers
    # -----------------------------
    if "quiz_answers" not in existing_tables:
        op.create_table(
            "quiz_answers",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "attempt_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("quiz_attempts.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "question_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("quiz_questions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("selected_answer", sa.String(length=255), nullable=True),
            sa.Column("is_correct", sa.Boolean(), nullable=True),
            sa.Column("feedback", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.UniqueConstraint("attempt_id", "question_id", name="uq_quiz_answers_attempt_id_question_id"),
        )
        op.create_index("ix_quiz_answers_attempt_id", "quiz_answers", ["attempt_id"])
        op.create_index("ix_quiz_answers_question_id", "quiz_answers", ["question_id"])


def downgrade():
    op.execute("DROP TABLE IF EXISTS quiz_answers")
    op.execute("DROP TABLE IF EXISTS quiz_attempts")
    op.execute("DROP TABLE IF EXISTS quiz_questions")
    op.execute("DROP TABLE IF EXISTS quizzes")