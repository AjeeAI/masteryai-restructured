"""create tutor session and internal quiz attempt tables

Revision ID: 0008_tutor_sessions_internal
Revises: 0007_diagnostic_state
Create Date: 2026-02-26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008_tutor_sessions_internal"
down_revision = "0007_diagnostic_state"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "tutor_sessions" not in existing_tables:
        op.create_table(
            "tutor_sessions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "student_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("subject", sa.String(length=50), nullable=False),
            sa.Column("term", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
            sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("duration_seconds", sa.Integer(), nullable=True),
            sa.Column("total_tokens", sa.Integer(), nullable=True),
            sa.Column("prompt_tokens", sa.Integer(), nullable=True),
            sa.Column("completion_tokens", sa.Integer(), nullable=True),
            sa.Column("cost_usd", sa.Numeric(10, 4), nullable=True),
            sa.Column("end_reason", sa.String(length=100), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.CheckConstraint("subject IN ('math','english','civic')", name="ck_tutor_sessions_subject"),
            sa.CheckConstraint("term BETWEEN 1 AND 3", name="ck_tutor_sessions_term"),
            sa.CheckConstraint("status IN ('active','ended')", name="ck_tutor_sessions_status"),
            sa.CheckConstraint("duration_seconds >= 0", name="ck_tutor_sessions_duration"),
            sa.CheckConstraint("total_tokens >= 0", name="ck_tutor_sessions_total_tokens"),
            sa.CheckConstraint("prompt_tokens >= 0", name="ck_tutor_sessions_prompt_tokens"),
            sa.CheckConstraint("completion_tokens >= 0", name="ck_tutor_sessions_completion_tokens"),
            sa.CheckConstraint("cost_usd >= 0", name="ck_tutor_sessions_cost_usd"),
        )
        op.create_index("ix_tutor_sessions_student_id", "tutor_sessions", ["student_id"])
        op.create_index("ix_tutor_sessions_scope", "tutor_sessions", ["subject", "term"])
        op.create_index("ix_tutor_sessions_status", "tutor_sessions", ["status"])

    if "tutor_messages" not in existing_tables:
        op.create_table(
            "tutor_messages",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "session_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("tutor_sessions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("role", sa.String(length=20), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.CheckConstraint("role IN ('student','assistant','system')", name="ck_tutor_messages_role"),
        )
        op.create_index("ix_tutor_messages_session_id", "tutor_messages", ["session_id"])
        op.create_index("ix_tutor_messages_role", "tutor_messages", ["role"])
        op.create_index("ix_tutor_messages_created_at", "tutor_messages", ["created_at"])

    if "internal_quiz_attempts" not in existing_tables:
        op.create_table(
            "internal_quiz_attempts",
            sa.Column("attempt_id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("quiz_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "student_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("subject", sa.String(length=50), nullable=False),
            sa.Column("sss_level", sa.String(length=10), nullable=False),
            sa.Column("term", sa.Integer(), nullable=False),
            sa.Column("answers", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
            sa.Column("time_taken_seconds", sa.Integer(), nullable=False),
            sa.Column("score", sa.Numeric(5, 2), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.CheckConstraint("subject IN ('math','english','civic')", name="ck_internal_quiz_attempts_subject"),
            sa.CheckConstraint("sss_level IN ('SSS1','SSS2','SSS3')", name="ck_internal_quiz_attempts_sss_level"),
            sa.CheckConstraint("term BETWEEN 1 AND 3", name="ck_internal_quiz_attempts_term"),
            sa.CheckConstraint("time_taken_seconds >= 0", name="ck_internal_quiz_attempts_time"),
            sa.CheckConstraint("score >= 0 AND score <= 100", name="ck_internal_quiz_attempts_score"),
        )
        op.create_index("ix_internal_quiz_attempts_quiz_id", "internal_quiz_attempts", ["quiz_id"])
        op.create_index("ix_internal_quiz_attempts_student_id", "internal_quiz_attempts", ["student_id"])
        op.create_index(
            "ix_internal_quiz_attempts_scope",
            "internal_quiz_attempts",
            ["subject", "sss_level", "term"],
        )


def downgrade():
    op.execute("DROP TABLE IF EXISTS internal_quiz_attempts")
    op.execute("DROP TABLE IF EXISTS tutor_messages")
    op.execute("DROP TABLE IF EXISTS tutor_sessions")
