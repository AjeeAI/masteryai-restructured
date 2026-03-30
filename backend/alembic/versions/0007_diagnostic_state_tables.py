"""create diagnostics state tables

Revision ID: 0007_diagnostic_state
Revises: 0006_learning_preferences
Create Date: 2026-02-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_diagnostic_state"
down_revision = "0006_learning_preferences"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "diagnostics" not in existing_tables:
        op.create_table(
            "diagnostics",
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
            sa.Column("status", sa.String(length=20), nullable=False, server_default="started"),
            sa.Column("concept_targets", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
            sa.Column("questions", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.CheckConstraint("subject IN ('math','english','civic')", name="ck_diagnostics_subject"),
            sa.CheckConstraint("sss_level IN ('SSS1','SSS2','SSS3')", name="ck_diagnostics_sss_level"),
            sa.CheckConstraint("term BETWEEN 1 AND 3", name="ck_diagnostics_term"),
            sa.CheckConstraint("status IN ('started','submitted')", name="ck_diagnostics_status"),
        )
        op.create_index("ix_diagnostics_student_id", "diagnostics", ["student_id"])
        op.create_index("ix_diagnostics_scope", "diagnostics", ["subject", "sss_level", "term"])

    if "diagnostic_attempts" not in existing_tables:
        op.create_table(
            "diagnostic_attempts",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "diagnostic_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("diagnostics.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "student_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("answers", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
            sa.Column(
                "baseline_mastery_updates",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default="[]",
            ),
            sa.Column("recommended_start_topic_id", sa.String(length=64), nullable=True),
            sa.Column("score", sa.Numeric(5, 2), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.UniqueConstraint("diagnostic_id", name="uq_diagnostic_attempt_diagnostic"),
        )
        op.create_index("ix_diagnostic_attempts_diagnostic_id", "diagnostic_attempts", ["diagnostic_id"])
        op.create_index("ix_diagnostic_attempts_student_id", "diagnostic_attempts", ["student_id"])


def downgrade():
    op.execute("DROP TABLE IF EXISTS diagnostic_attempts")
    op.execute("DROP TABLE IF EXISTS diagnostics")
