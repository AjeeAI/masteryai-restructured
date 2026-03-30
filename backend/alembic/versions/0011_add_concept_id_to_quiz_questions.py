"""add concept_id to quiz_questions

Revision ID: 0011_quiz_question_concept_id
Revises: 0010_graph_mastery_tracking
Create Date: 2026-02-27
"""

from alembic import op
import sqlalchemy as sa


revision = "0011_quiz_question_concept_id"
down_revision = "0010_graph_mastery_tracking"
branch_labels = None
depends_on = None


def _index_exists(inspector, table_name: str, index_name: str) -> bool:
    return any(index.get("name") == index_name for index in inspector.get_indexes(table_name))


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "quiz_questions" not in existing_tables:
        return

    columns = {column["name"] for column in inspector.get_columns("quiz_questions")}
    if "concept_id" not in columns:
        op.add_column("quiz_questions", sa.Column("concept_id", sa.String(length=255), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE quiz_questions
            SET concept_id = id::text
            WHERE concept_id IS NULL OR concept_id = ''
            """
        )
    )

    op.alter_column("quiz_questions", "concept_id", existing_type=sa.String(length=255), nullable=False)

    inspector = sa.inspect(bind)
    if not _index_exists(inspector, "quiz_questions", "ix_quiz_questions_concept_id"):
        op.create_index("ix_quiz_questions_concept_id", "quiz_questions", ["concept_id"], unique=False)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "quiz_questions" not in existing_tables:
        return

    if _index_exists(inspector, "quiz_questions", "ix_quiz_questions_concept_id"):
        op.drop_index("ix_quiz_questions_concept_id", table_name="quiz_questions")

    columns = {column["name"] for column in inspector.get_columns("quiz_questions")}
    if "concept_id" in columns:
        op.drop_column("quiz_questions", "concept_id")
