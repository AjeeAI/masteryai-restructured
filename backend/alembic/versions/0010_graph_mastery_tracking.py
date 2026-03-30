"""create graph mastery tracking tables

Revision ID: 0010_graph_mastery_tracking
Revises: 0009_quiz_tables
Create Date: 2026-02-26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0010_graph_mastery_tracking"
down_revision = "0009_quiz_tables"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "student_concept_mastery" not in existing_tables:
        op.create_table(
            "student_concept_mastery",
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
            sa.Column("concept_id", sa.String(length=128), nullable=False),
            sa.Column("mastery_score", sa.Numeric(5, 4), nullable=False, server_default="0"),
            sa.Column("source", sa.String(length=30), nullable=False, server_default="diagnostic"),
            sa.Column("last_evaluated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.UniqueConstraint(
                "student_id",
                "subject",
                "sss_level",
                "term",
                "concept_id",
                name="uq_student_concept_mastery_scope",
            ),
            sa.CheckConstraint("subject IN ('math','english','civic')", name="ck_student_concept_mastery_subject"),
            sa.CheckConstraint("sss_level IN ('SSS1','SSS2','SSS3')", name="ck_student_concept_mastery_sss_level"),
            sa.CheckConstraint("term BETWEEN 1 AND 3", name="ck_student_concept_mastery_term"),
            sa.CheckConstraint(
                "mastery_score >= 0 AND mastery_score <= 1",
                name="ck_student_concept_mastery_score",
            ),
        )
        op.create_index("ix_student_concept_mastery_student_id", "student_concept_mastery", ["student_id"])
        op.create_index(
            "ix_student_concept_mastery_scope",
            "student_concept_mastery",
            ["subject", "sss_level", "term"],
        )
        op.create_index("ix_student_concept_mastery_concept_id", "student_concept_mastery", ["concept_id"])

    if "mastery_update_events" not in existing_tables:
        op.create_table(
            "mastery_update_events",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "student_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("quiz_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("attempt_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("subject", sa.String(length=50), nullable=False),
            sa.Column("sss_level", sa.String(length=10), nullable=False),
            sa.Column("term", sa.Integer(), nullable=False),
            sa.Column("source", sa.String(length=30), nullable=False),
            sa.Column("concept_breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
            sa.Column("new_mastery", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.CheckConstraint("subject IN ('math','english','civic')", name="ck_mastery_update_events_subject"),
            sa.CheckConstraint("sss_level IN ('SSS1','SSS2','SSS3')", name="ck_mastery_update_events_sss_level"),
            sa.CheckConstraint("term BETWEEN 1 AND 3", name="ck_mastery_update_events_term"),
            sa.CheckConstraint(
                "source IN ('practice','diagnostic','exam_prep')",
                name="ck_mastery_update_events_source",
            ),
        )
        op.create_index("ix_mastery_update_events_student_id", "mastery_update_events", ["student_id"])
        op.create_index("ix_mastery_update_events_created_at", "mastery_update_events", ["created_at"])


def downgrade():
    op.execute("DROP TABLE IF EXISTS mastery_update_events")
    op.execute("DROP TABLE IF EXISTS student_concept_mastery")
