"""init lessons + curriculum tables

Revision ID: 0001_init
Revises: 
Create Date: 2026-02-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "subjects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("slug", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_subjects_slug", "subjects", ["slug"], unique=True)

    op.create_table(
        "student_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sss_level", sa.String(length=10), nullable=False),
        sa.Column("active_term", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_student_profiles_student_id", "student_profiles", ["student_id"], unique=True)

    op.create_table(
        "student_subjects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("student_profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("student_profile_id", "subject_id", name="uq_student_subject"),
    )
    op.create_index("ix_student_subjects_profile", "student_subjects", ["student_profile_id"])
    op.create_index("ix_student_subjects_subject", "student_subjects", ["subject_id"])

    op.create_table(
        "topics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("sss_level", sa.String(length=10), nullable=False),
        sa.Column("term", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("curriculum_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_approved", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("subject_id", "sss_level", "term", "title", name="uq_topic_scope_title"),
    )
    op.create_index("ix_topics_subject", "topics", ["subject_id"])
    op.create_index("ix_topics_scope", "topics", ["sss_level", "term"])
    op.create_index("ix_topics_approved", "topics", ["is_approved"])

    op.create_table(
        "lessons",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("topics.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.String(length=800), nullable=True),
        sa.Column("estimated_duration_minutes", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("topic_id", name="uq_lesson_topic"),
    )
    op.create_index("ix_lessons_topic", "lessons", ["topic_id"])

    op.create_table(
        "lesson_blocks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("lesson_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("block_type", sa.String(length=30), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_lesson_blocks_lesson", "lesson_blocks", ["lesson_id"])
    op.create_index("ix_lesson_blocks_order", "lesson_blocks", ["lesson_id", "order_index"])
    op.create_index("ix_lesson_blocks_type", "lesson_blocks", ["block_type"])

def downgrade():
    op.drop_table("lesson_blocks")
    op.drop_table("lessons")
    op.drop_table("topics")
    op.drop_table("student_subjects")
    op.drop_table("student_profiles")
    op.drop_table("subjects")