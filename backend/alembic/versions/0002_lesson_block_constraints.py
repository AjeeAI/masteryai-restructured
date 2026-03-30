"""add lesson block integrity constraints

Revision ID: 0002_lesson_block_constraints
Revises: 0001_init
Create Date: 2026-02-24
"""

from alembic import op

revision = "0002_lesson_block_constraints"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint(
        "uq_lesson_block_order",
        "lesson_blocks",
        ["lesson_id", "order_index"],
    )
    op.create_check_constraint(
        "ck_lesson_block_type",
        "lesson_blocks",
        "block_type IN ('text','video','image','example','exercise')",
    )


def downgrade():
    op.drop_constraint("ck_lesson_block_type", "lesson_blocks", type_="check")
    op.drop_constraint("uq_lesson_block_order", "lesson_blocks", type_="unique")
