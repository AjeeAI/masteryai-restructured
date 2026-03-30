"""add diagnostic gap summary fields

Revision ID: 0024_diagnostic_gap_summary
Revises: 0023_teacher_concept_tags
Create Date: 2026-03-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0024_diagnostic_gap_summary"
down_revision = "0023_teacher_concept_tags"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "diagnostic_attempts" not in existing_tables:
        return

    existing_columns = {column["name"] for column in inspector.get_columns("diagnostic_attempts")}

    if "gap_summary" not in existing_columns:
        op.add_column(
            "diagnostic_attempts",
            sa.Column(
                "gap_summary",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )

    if "recommended_start_topic_title" not in existing_columns:
        op.add_column(
            "diagnostic_attempts",
            sa.Column("recommended_start_topic_title", sa.String(length=255), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "diagnostic_attempts" not in existing_tables:
        return

    existing_columns = {column["name"] for column in inspector.get_columns("diagnostic_attempts")}

    if "recommended_start_topic_title" in existing_columns:
        op.drop_column("diagnostic_attempts", "recommended_start_topic_title")

    if "gap_summary" in existing_columns:
        op.drop_column("diagnostic_attempts", "gap_summary")
