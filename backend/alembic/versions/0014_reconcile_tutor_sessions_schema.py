"""reconcile tutor_sessions columns with app contract

Revision ID: 0014_tutor_sessions_reconcile
Revises: 0013_activity_logs_timestamp_fix
Create Date: 2026-02-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0014_tutor_sessions_reconcile"
down_revision = "0013_activity_logs_timestamp_fix"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _has_index(inspector, table_name: str, index_name: str) -> bool:
    return any(index.get("name") == index_name for index in inspector.get_indexes(table_name))


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "tutor_sessions" not in tables:
        return

    # Add app-contract columns if missing.
    if not _has_column(inspector, "tutor_sessions", "student_id"):
        op.add_column("tutor_sessions", sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=True))

    if not _has_column(inspector, "tutor_sessions", "status"):
        op.add_column(
            "tutor_sessions",
            sa.Column("status", sa.String(length=20), nullable=True, server_default=sa.text("'active'")),
        )

    if not _has_column(inspector, "tutor_sessions", "total_tokens"):
        op.add_column("tutor_sessions", sa.Column("total_tokens", sa.Integer(), nullable=True))

    if not _has_column(inspector, "tutor_sessions", "prompt_tokens"):
        op.add_column("tutor_sessions", sa.Column("prompt_tokens", sa.Integer(), nullable=True))

    if not _has_column(inspector, "tutor_sessions", "completion_tokens"):
        op.add_column("tutor_sessions", sa.Column("completion_tokens", sa.Integer(), nullable=True))

    if not _has_column(inspector, "tutor_sessions", "cost_usd"):
        op.add_column("tutor_sessions", sa.Column("cost_usd", sa.Numeric(10, 4), nullable=True))

    if not _has_column(inspector, "tutor_sessions", "end_reason"):
        op.add_column("tutor_sessions", sa.Column("end_reason", sa.String(length=100), nullable=True))

    # Refresh inspector after adds.
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("tutor_sessions")}

    # Backfill student_id from legacy student_profile_id -> student_profiles.student_id mapping.
    if "student_id" in cols and "student_profile_id" in cols and "student_profiles" in tables:
        op.execute(
            sa.text(
                """
                UPDATE tutor_sessions ts
                SET student_id = sp.student_id
                FROM student_profiles sp
                WHERE ts.student_id IS NULL
                  AND ts.student_profile_id = sp.id
                """
            )
        )

    # Backfill status from legacy is_closed flag when present.
    if "status" in cols and "is_closed" in cols:
        op.execute(
            sa.text(
                """
                UPDATE tutor_sessions
                SET status = CASE WHEN is_closed THEN 'ended' ELSE 'active' END
                WHERE status IS NULL OR status = ''
                """
            )
        )
    elif "status" in cols:
        op.execute(
            sa.text(
                """
                UPDATE tutor_sessions
                SET status = 'active'
                WHERE status IS NULL OR status = ''
                """
            )
        )

    # Backfill cost_usd from legacy cost when present.
    if "cost_usd" in cols and "cost" in cols:
        op.execute(
            sa.text(
                """
                UPDATE tutor_sessions
                SET cost_usd = cost
                WHERE cost_usd IS NULL AND cost IS NOT NULL
                """
            )
        )

    # Keep defaults stable for new inserts.
    if "status" in cols:
        op.alter_column("tutor_sessions", "status", existing_type=sa.String(length=20), server_default="active")

    # Tighten nullability only when safely possible.
    if "status" in cols:
        null_status = bind.execute(
            sa.text("SELECT COUNT(*) FROM tutor_sessions WHERE status IS NULL OR status = ''")
        ).scalar_one()
        if int(null_status) == 0:
            op.alter_column("tutor_sessions", "status", existing_type=sa.String(length=20), nullable=False)

    if "student_id" in cols:
        null_student = bind.execute(
            sa.text("SELECT COUNT(*) FROM tutor_sessions WHERE student_id IS NULL")
        ).scalar_one()
        if int(null_student) == 0:
            op.alter_column("tutor_sessions", "student_id", nullable=False)

    # Add useful indexes if missing.
    inspector = sa.inspect(bind)
    if "student_id" in {c["name"] for c in inspector.get_columns("tutor_sessions")} and not _has_index(
        inspector, "tutor_sessions", "ix_tutor_sessions_student_id"
    ):
        op.create_index("ix_tutor_sessions_student_id", "tutor_sessions", ["student_id"], unique=False)

    if "status" in {c["name"] for c in inspector.get_columns("tutor_sessions")} and not _has_index(
        inspector, "tutor_sessions", "ix_tutor_sessions_status"
    ):
        op.create_index("ix_tutor_sessions_status", "tutor_sessions", ["status"], unique=False)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "tutor_sessions" not in tables:
        return

    columns = {c["name"] for c in inspector.get_columns("tutor_sessions")}

    if "ix_tutor_sessions_status" in {idx["name"] for idx in inspector.get_indexes("tutor_sessions")}:
        op.drop_index("ix_tutor_sessions_status", table_name="tutor_sessions")
    if "ix_tutor_sessions_student_id" in {idx["name"] for idx in inspector.get_indexes("tutor_sessions")}:
        op.drop_index("ix_tutor_sessions_student_id", table_name="tutor_sessions")

    if "end_reason" in columns:
        op.drop_column("tutor_sessions", "end_reason")
    if "cost_usd" in columns:
        op.drop_column("tutor_sessions", "cost_usd")
    if "completion_tokens" in columns:
        op.drop_column("tutor_sessions", "completion_tokens")
    if "prompt_tokens" in columns:
        op.drop_column("tutor_sessions", "prompt_tokens")
    if "total_tokens" in columns:
        op.drop_column("tutor_sessions", "total_tokens")
    if "status" in columns:
        op.drop_column("tutor_sessions", "status")
    if "student_id" in columns:
        op.drop_column("tutor_sessions", "student_id")
