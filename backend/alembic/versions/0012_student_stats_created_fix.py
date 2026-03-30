"""reconcile student_stats timestamp columns

Revision ID: 0012_student_stats_created_fix
Revises: 0011_quiz_question_concept_id
Create Date: 2026-02-27
"""

from alembic import op
import sqlalchemy as sa


revision = "0012_student_stats_created_fix"
down_revision = "0011_quiz_question_concept_id"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "student_stats" not in tables:
        return

    if not _has_column(inspector, "student_stats", "created_at"):
        op.add_column(
            "student_stats",
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        )
        op.execute(sa.text("UPDATE student_stats SET created_at = NOW() WHERE created_at IS NULL"))
        op.alter_column("student_stats", "created_at", nullable=False)

    inspector = sa.inspect(bind)
    if not _has_column(inspector, "student_stats", "updated_at"):
        op.add_column(
            "student_stats",
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        )
        op.execute(sa.text("UPDATE student_stats SET updated_at = NOW() WHERE updated_at IS NULL"))
        op.alter_column("student_stats", "updated_at", nullable=False)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "student_stats" not in tables:
        return

    if _has_column(inspector, "student_stats", "created_at"):
        op.drop_column("student_stats", "created_at")

    inspector = sa.inspect(bind)
    if _has_column(inspector, "student_stats", "updated_at"):
        op.drop_column("student_stats", "updated_at")
