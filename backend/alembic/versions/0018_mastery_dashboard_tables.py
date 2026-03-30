"""create mastery snapshot and student badge tables

Revision ID: 0018_mastery_dashboard_tables
Revises: 0017_user_identity_fields
Create Date: 2026-02-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0018_mastery_dashboard_tables"
down_revision = "0017_user_identity_fields"
branch_labels = None
depends_on = None


def _table_exists(inspector, table_name: str) -> bool:
    return table_name in set(inspector.get_table_names())


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "mastery_snapshots"):
        op.create_table(
            "mastery_snapshots",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "student_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("subject", sa.String(length=50), nullable=False),
            sa.Column("term", sa.Integer(), nullable=False),
            sa.Column("view", sa.String(length=20), nullable=False),
            sa.Column("snapshot_date", sa.Date(), nullable=False),
            sa.Column("mastery_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
            sa.Column("overall_mastery", sa.Numeric(5, 4), nullable=False, server_default="0"),
            sa.Column("source", sa.String(length=30), nullable=False, server_default="dashboard"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.CheckConstraint("subject IN ('math','english','civic')", name="ck_mastery_snapshots_subject"),
            sa.CheckConstraint("term BETWEEN 1 AND 3", name="ck_mastery_snapshots_term"),
            sa.CheckConstraint("view IN ('concept','topic')", name="ck_mastery_snapshots_view"),
            sa.CheckConstraint("overall_mastery >= 0 AND overall_mastery <= 1", name="ck_mastery_snapshots_overall"),
            sa.UniqueConstraint(
                "student_id",
                "subject",
                "term",
                "view",
                "snapshot_date",
                name="uq_mastery_snapshots_scope_date",
            ),
        )
        op.create_index("ix_mastery_snapshots_student_id", "mastery_snapshots", ["student_id"], unique=False)
        op.create_index("ix_mastery_snapshots_subject", "mastery_snapshots", ["subject"], unique=False)
        op.create_index("ix_mastery_snapshots_term", "mastery_snapshots", ["term"], unique=False)
        op.create_index("ix_mastery_snapshots_view", "mastery_snapshots", ["view"], unique=False)
        op.create_index("ix_mastery_snapshots_snapshot_date", "mastery_snapshots", ["snapshot_date"], unique=False)

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "student_badges"):
        op.create_table(
            "student_badges",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "student_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("badge_code", sa.String(length=100), nullable=False),
            sa.Column("badge_name", sa.String(length=150), nullable=False),
            sa.Column("description", sa.String(length=500), nullable=True),
            sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
            sa.Column("awarded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.UniqueConstraint("student_id", "badge_code", name="uq_student_badges_student_code"),
        )
        op.create_index("ix_student_badges_student_id", "student_badges", ["student_id"], unique=False)
        op.create_index("ix_student_badges_badge_code", "student_badges", ["badge_code"], unique=False)
        op.create_index("ix_student_badges_awarded_at", "student_badges", ["awarded_at"], unique=False)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "student_badges"):
        op.drop_index("ix_student_badges_awarded_at", table_name="student_badges")
        op.drop_index("ix_student_badges_badge_code", table_name="student_badges")
        op.drop_index("ix_student_badges_student_id", table_name="student_badges")
        op.drop_table("student_badges")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "mastery_snapshots"):
        op.drop_index("ix_mastery_snapshots_snapshot_date", table_name="mastery_snapshots")
        op.drop_index("ix_mastery_snapshots_view", table_name="mastery_snapshots")
        op.drop_index("ix_mastery_snapshots_term", table_name="mastery_snapshots")
        op.drop_index("ix_mastery_snapshots_subject", table_name="mastery_snapshots")
        op.drop_index("ix_mastery_snapshots_student_id", table_name="mastery_snapshots")
        op.drop_table("mastery_snapshots")
