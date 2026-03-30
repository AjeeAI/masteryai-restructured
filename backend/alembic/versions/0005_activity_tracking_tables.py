"""create activity tracking tables

Revision ID: 0005_activity_tracking
Revises: 0004_profile_user_fk
Create Date: 2026-02-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_activity_tracking"
down_revision = "0004_profile_user_fk"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "activity_logs" not in existing_tables:
        op.create_table(
            "activity_logs",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "student_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("subject", sa.String(length=50), nullable=False),
            sa.Column("term", sa.Integer(), nullable=False),
            sa.Column("event_type", sa.String(length=50), nullable=False),
            sa.Column("ref_id", sa.String(length=255), nullable=False),
            sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.CheckConstraint("subject IN ('math','english','civic')", name="ck_activity_logs_subject"),
            sa.CheckConstraint("term BETWEEN 1 AND 3", name="ck_activity_logs_term"),
            sa.CheckConstraint(
                "event_type IN ('lesson_viewed','quiz_submitted','mastery_check_done','tutor_chat')",
                name="ck_activity_logs_event_type",
            ),
            sa.CheckConstraint("duration_seconds >= 0", name="ck_activity_logs_duration"),
        )
        op.create_index("ix_activity_logs_student_id", "activity_logs", ["student_id"])
        op.create_index("ix_activity_logs_created_at", "activity_logs", ["created_at"])

    if "daily_activity_summary" not in existing_tables:
        op.create_table(
            "daily_activity_summary",
            sa.Column(
                "student_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                primary_key=True,
                nullable=False,
            ),
            sa.Column("activity_date", sa.Date(), primary_key=True, nullable=False),
            sa.Column("total_duration", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("points_earned", sa.Integer(), nullable=False, server_default="0"),
            sa.CheckConstraint("total_duration >= 0", name="ck_daily_activity_summary_duration"),
            sa.CheckConstraint("points_earned >= 0", name="ck_daily_activity_summary_points"),
        )

    if "student_stats" not in existing_tables:
        op.create_table(
            "student_stats",
            sa.Column(
                "student_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                primary_key=True,
                nullable=False,
            ),
            sa.Column("current_streak", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_streak", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_mastery_points", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_study_time_seconds", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_activity_date", sa.Date(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.CheckConstraint("current_streak >= 0", name="ck_student_stats_current_streak"),
            sa.CheckConstraint("max_streak >= 0", name="ck_student_stats_max_streak"),
            sa.CheckConstraint("total_mastery_points >= 0", name="ck_student_stats_total_mastery_points"),
            sa.CheckConstraint("total_study_time_seconds >= 0", name="ck_student_stats_total_study_time_seconds"),
        )


def downgrade():
    op.execute("DROP TABLE IF EXISTS student_stats")
    op.execute("DROP TABLE IF EXISTS daily_activity_summary")
    op.execute("DROP TABLE IF EXISTS activity_logs")
