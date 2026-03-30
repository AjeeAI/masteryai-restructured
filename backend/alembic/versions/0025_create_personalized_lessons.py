"""create personalized lessons cache table

Revision ID: 0025_create_personalized_lessons
Revises: 0024_diagnostic_gap_summary
Create Date: 2026-03-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0025_create_personalized_lessons"
down_revision = "0024_diagnostic_gap_summary"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "personalized_lessons" not in inspector.get_table_names():
        op.create_table(
            "personalized_lessons",
            sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("topic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("topics.id", ondelete="CASCADE"), nullable=False),
            sa.Column("curriculum_version_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("summary", sa.String(length=1200), nullable=True),
            sa.Column("estimated_duration_minutes", sa.Integer(), nullable=True),
            sa.Column("content_blocks", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("source_chunk_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("generation_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.UniqueConstraint("student_id", "topic_id", name="uq_personalized_lesson_student_topic"),
        )

    refreshed = sa.inspect(bind)
    existing_indexes = {index["name"] for index in refreshed.get_indexes("personalized_lessons")}

    if "ix_personalized_lessons_student_id" not in existing_indexes:
        op.create_index("ix_personalized_lessons_student_id", "personalized_lessons", ["student_id"], unique=False)
    if "ix_personalized_lessons_topic_id" not in existing_indexes:
        op.create_index("ix_personalized_lessons_topic_id", "personalized_lessons", ["topic_id"], unique=False)
    if "ix_personalized_lessons_curriculum_version_id" not in existing_indexes:
        op.create_index(
            "ix_personalized_lessons_curriculum_version_id",
            "personalized_lessons",
            ["curriculum_version_id"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "personalized_lessons" not in inspector.get_table_names():
        return

    for index_name in (
        "ix_personalized_lessons_curriculum_version_id",
        "ix_personalized_lessons_topic_id",
        "ix_personalized_lessons_student_id",
    ):
        existing_indexes = {index["name"] for index in sa.inspect(bind).get_indexes("personalized_lessons")}
        if index_name in existing_indexes:
            op.drop_index(index_name, table_name="personalized_lessons")

    op.drop_table("personalized_lessons")
