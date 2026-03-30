"""Merge 0019 and 0020 heads.

Revision ID: 0021_merge_0019_0020
Revises: 0019_teacher_intelligence_tables, 0020_admin_curriculum_ops
Create Date: 2026-03-01 12:05:00.000000
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0021_merge_0019_0020"
down_revision: Union[str, Sequence[str], None] = (
    "0019_teacher_intelligence_tables",
    "0020_admin_curriculum_ops",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Merge migration only; schema changes are in parent revisions.
    pass


def downgrade() -> None:
    # Split merge point; parent revisions remain intact.
    pass
