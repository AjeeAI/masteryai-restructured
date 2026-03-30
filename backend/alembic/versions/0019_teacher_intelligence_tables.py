"""create teacher intelligence tables

Revision ID: 0019_teacher_intelligence_tables
Revises: 0018_mastery_dashboard_tables
Create Date: 2026-02-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0019_teacher_intelligence_tables"
down_revision = "0018_mastery_dashboard_tables"
branch_labels = None
depends_on = None


def _table_exists(inspector, table_name: str) -> bool:
    return table_name in set(inspector.get_table_names())


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "teacher_classes"):
        op.create_table(
            "teacher_classes",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "teacher_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("name", sa.String(length=150), nullable=False),
            sa.Column("description", sa.String(length=500), nullable=True),
            sa.Column("subject", sa.String(length=50), nullable=False),
            sa.Column("sss_level", sa.String(length=10), nullable=False),
            sa.Column("term", sa.Integer(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.UniqueConstraint(
                "teacher_id",
                "name",
                "subject",
                "sss_level",
                "term",
                name="uq_teacher_classes_scope_name",
            ),
            sa.CheckConstraint("subject IN ('math','english','civic')", name="ck_teacher_classes_subject"),
            sa.CheckConstraint("sss_level IN ('SSS1','SSS2','SSS3')", name="ck_teacher_classes_sss_level"),
            sa.CheckConstraint("term BETWEEN 1 AND 3", name="ck_teacher_classes_term"),
        )
        op.create_index("ix_teacher_classes_teacher_id", "teacher_classes", ["teacher_id"], unique=False)
        op.create_index("ix_teacher_classes_subject", "teacher_classes", ["subject"], unique=False)
        op.create_index("ix_teacher_classes_sss_level", "teacher_classes", ["sss_level"], unique=False)
        op.create_index("ix_teacher_classes_term", "teacher_classes", ["term"], unique=False)
        op.create_index("ix_teacher_classes_is_active", "teacher_classes", ["is_active"], unique=False)

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "class_enrollments"):
        op.create_table(
            "class_enrollments",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "class_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("teacher_classes.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "student_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
            sa.Column("enrolled_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.UniqueConstraint("class_id", "student_id", name="uq_class_enrollments_class_student"),
            sa.CheckConstraint("status IN ('active','removed')", name="ck_class_enrollments_status"),
        )
        op.create_index("ix_class_enrollments_class_id", "class_enrollments", ["class_id"], unique=False)
        op.create_index("ix_class_enrollments_student_id", "class_enrollments", ["student_id"], unique=False)
        op.create_index("ix_class_enrollments_status", "class_enrollments", ["status"], unique=False)

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "teacher_assignments"):
        op.create_table(
            "teacher_assignments",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "teacher_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "class_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("teacher_classes.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column(
                "student_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column("assignment_type", sa.String(length=20), nullable=False),
            sa.Column("ref_id", sa.String(length=255), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("instructions", sa.String(length=2000), nullable=True),
            sa.Column("subject", sa.String(length=50), nullable=False),
            sa.Column("sss_level", sa.String(length=10), nullable=False),
            sa.Column("term", sa.Integer(), nullable=False),
            sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="assigned"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.CheckConstraint("assignment_type IN ('topic','quiz','revision')", name="ck_teacher_assignments_type"),
            sa.CheckConstraint("subject IN ('math','english','civic')", name="ck_teacher_assignments_subject"),
            sa.CheckConstraint("sss_level IN ('SSS1','SSS2','SSS3')", name="ck_teacher_assignments_sss_level"),
            sa.CheckConstraint("term BETWEEN 1 AND 3", name="ck_teacher_assignments_term"),
            sa.CheckConstraint("status IN ('assigned','completed','cancelled')", name="ck_teacher_assignments_status"),
            sa.CheckConstraint(
                "(class_id IS NOT NULL) OR (student_id IS NOT NULL)",
                name="ck_teacher_assignments_target_required",
            ),
        )
        op.create_index("ix_teacher_assignments_teacher_id", "teacher_assignments", ["teacher_id"], unique=False)
        op.create_index("ix_teacher_assignments_class_id", "teacher_assignments", ["class_id"], unique=False)
        op.create_index("ix_teacher_assignments_student_id", "teacher_assignments", ["student_id"], unique=False)
        op.create_index("ix_teacher_assignments_type", "teacher_assignments", ["assignment_type"], unique=False)
        op.create_index("ix_teacher_assignments_subject", "teacher_assignments", ["subject"], unique=False)
        op.create_index("ix_teacher_assignments_sss_level", "teacher_assignments", ["sss_level"], unique=False)
        op.create_index("ix_teacher_assignments_term", "teacher_assignments", ["term"], unique=False)
        op.create_index("ix_teacher_assignments_status", "teacher_assignments", ["status"], unique=False)

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "teacher_interventions"):
        op.create_table(
            "teacher_interventions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "teacher_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "class_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("teacher_classes.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column(
                "student_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("intervention_type", sa.String(length=30), nullable=False),
            sa.Column("severity", sa.String(length=20), nullable=False, server_default="medium"),
            sa.Column("subject", sa.String(length=50), nullable=False),
            sa.Column("sss_level", sa.String(length=10), nullable=False),
            sa.Column("term", sa.Integer(), nullable=False),
            sa.Column("notes", sa.String(length=2000), nullable=False),
            sa.Column("action_plan", sa.String(length=2000), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.CheckConstraint(
                "intervention_type IN ('note','flag','support_plan','parent_contact')",
                name="ck_teacher_interventions_type",
            ),
            sa.CheckConstraint("severity IN ('low','medium','high')", name="ck_teacher_interventions_severity"),
            sa.CheckConstraint("subject IN ('math','english','civic')", name="ck_teacher_interventions_subject"),
            sa.CheckConstraint("sss_level IN ('SSS1','SSS2','SSS3')", name="ck_teacher_interventions_sss_level"),
            sa.CheckConstraint("term BETWEEN 1 AND 3", name="ck_teacher_interventions_term"),
            sa.CheckConstraint("status IN ('open','resolved','dismissed')", name="ck_teacher_interventions_status"),
        )
        op.create_index("ix_teacher_interventions_teacher_id", "teacher_interventions", ["teacher_id"], unique=False)
        op.create_index("ix_teacher_interventions_class_id", "teacher_interventions", ["class_id"], unique=False)
        op.create_index("ix_teacher_interventions_student_id", "teacher_interventions", ["student_id"], unique=False)
        op.create_index(
            "ix_teacher_interventions_type",
            "teacher_interventions",
            ["intervention_type"],
            unique=False,
        )
        op.create_index(
            "ix_teacher_interventions_severity",
            "teacher_interventions",
            ["severity"],
            unique=False,
        )
        op.create_index("ix_teacher_interventions_subject", "teacher_interventions", ["subject"], unique=False)
        op.create_index("ix_teacher_interventions_sss_level", "teacher_interventions", ["sss_level"], unique=False)
        op.create_index("ix_teacher_interventions_term", "teacher_interventions", ["term"], unique=False)
        op.create_index("ix_teacher_interventions_status", "teacher_interventions", ["status"], unique=False)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "teacher_interventions"):
        op.drop_index("ix_teacher_interventions_status", table_name="teacher_interventions")
        op.drop_index("ix_teacher_interventions_term", table_name="teacher_interventions")
        op.drop_index("ix_teacher_interventions_sss_level", table_name="teacher_interventions")
        op.drop_index("ix_teacher_interventions_subject", table_name="teacher_interventions")
        op.drop_index("ix_teacher_interventions_severity", table_name="teacher_interventions")
        op.drop_index("ix_teacher_interventions_type", table_name="teacher_interventions")
        op.drop_index("ix_teacher_interventions_student_id", table_name="teacher_interventions")
        op.drop_index("ix_teacher_interventions_class_id", table_name="teacher_interventions")
        op.drop_index("ix_teacher_interventions_teacher_id", table_name="teacher_interventions")
        op.drop_table("teacher_interventions")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "teacher_assignments"):
        op.drop_index("ix_teacher_assignments_status", table_name="teacher_assignments")
        op.drop_index("ix_teacher_assignments_term", table_name="teacher_assignments")
        op.drop_index("ix_teacher_assignments_sss_level", table_name="teacher_assignments")
        op.drop_index("ix_teacher_assignments_subject", table_name="teacher_assignments")
        op.drop_index("ix_teacher_assignments_type", table_name="teacher_assignments")
        op.drop_index("ix_teacher_assignments_student_id", table_name="teacher_assignments")
        op.drop_index("ix_teacher_assignments_class_id", table_name="teacher_assignments")
        op.drop_index("ix_teacher_assignments_teacher_id", table_name="teacher_assignments")
        op.drop_table("teacher_assignments")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "class_enrollments"):
        op.drop_index("ix_class_enrollments_status", table_name="class_enrollments")
        op.drop_index("ix_class_enrollments_student_id", table_name="class_enrollments")
        op.drop_index("ix_class_enrollments_class_id", table_name="class_enrollments")
        op.drop_table("class_enrollments")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "teacher_classes"):
        op.drop_index("ix_teacher_classes_is_active", table_name="teacher_classes")
        op.drop_index("ix_teacher_classes_term", table_name="teacher_classes")
        op.drop_index("ix_teacher_classes_sss_level", table_name="teacher_classes")
        op.drop_index("ix_teacher_classes_subject", table_name="teacher_classes")
        op.drop_index("ix_teacher_classes_teacher_id", table_name="teacher_classes")
        op.drop_table("teacher_classes")
