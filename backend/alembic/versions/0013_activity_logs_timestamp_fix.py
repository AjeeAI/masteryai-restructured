"""reconcile activity_logs timestamp columns

Revision ID: 0013_activity_logs_timestamp_fix
Revises: 0012_student_stats_created_fix
Create Date: 2026-02-27
"""

from alembic import op
import sqlalchemy as sa


revision = "0013_activity_logs_timestamp_fix"
down_revision = "0012_student_stats_created_fix"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _ensure_timestamp_column(table_name: str, column_name: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if table_name not in tables:
        return

    if _has_column(inspector, table_name, column_name):
        return

    op.add_column(
        table_name,
        sa.Column(column_name, sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
    )
    op.execute(
        sa.text(f"UPDATE {table_name} SET {column_name} = NOW() WHERE {column_name} IS NULL")
    )
    op.alter_column(table_name, column_name, nullable=False)


def upgrade():
    _ensure_timestamp_column("activity_logs", "created_at")
    _ensure_timestamp_column("activity_logs", "updated_at")


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "activity_logs" not in tables:
        return

    if _has_column(inspector, "activity_logs", "updated_at"):
        op.drop_column("activity_logs", "updated_at")

    inspector = sa.inspect(bind)
    if _has_column(inspector, "activity_logs", "created_at"):
        op.drop_column("activity_logs", "created_at")
