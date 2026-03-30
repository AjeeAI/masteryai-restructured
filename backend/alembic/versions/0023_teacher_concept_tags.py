"""add concept tags to teacher assignments and interventions

Revision ID: 0023_teacher_concept_tags
Revises: 0022_prewarm_jobs
Create Date: 2026-03-14
"""

from alembic import op
import sqlalchemy as sa


revision = "0023_teacher_concept_tags"
down_revision = "0022_prewarm_jobs"
branch_labels = None
depends_on = None


def _column_names(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    assignment_columns = _column_names(inspector, "teacher_assignments")
    if "concept_id" not in assignment_columns:
        op.add_column("teacher_assignments", sa.Column("concept_id", sa.String(length=255), nullable=True))
        op.create_index(
            "ix_teacher_assignments_concept_id",
            "teacher_assignments",
            ["concept_id"],
            unique=False,
        )
    if "concept_label" not in assignment_columns:
        op.add_column("teacher_assignments", sa.Column("concept_label", sa.String(length=255), nullable=True))

    intervention_columns = _column_names(inspector, "teacher_interventions")
    if "concept_id" not in intervention_columns:
        op.add_column("teacher_interventions", sa.Column("concept_id", sa.String(length=255), nullable=True))
        op.create_index(
            "ix_teacher_interventions_concept_id",
            "teacher_interventions",
            ["concept_id"],
            unique=False,
        )
    if "concept_label" not in intervention_columns:
        op.add_column("teacher_interventions", sa.Column("concept_label", sa.String(length=255), nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    intervention_columns = _column_names(inspector, "teacher_interventions")
    if "concept_label" in intervention_columns:
        op.drop_column("teacher_interventions", "concept_label")
    if "concept_id" in intervention_columns:
        op.drop_index("ix_teacher_interventions_concept_id", table_name="teacher_interventions")
        op.drop_column("teacher_interventions", "concept_id")

    assignment_columns = _column_names(inspector, "teacher_assignments")
    if "concept_label" in assignment_columns:
        op.drop_column("teacher_assignments", "concept_label")
    if "concept_id" in assignment_columns:
        op.drop_index("ix_teacher_assignments_concept_id", table_name="teacher_assignments")
        op.drop_column("teacher_assignments", "concept_id")
