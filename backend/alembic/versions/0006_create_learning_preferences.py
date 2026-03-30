"""create learning_preferences table

Revision ID: 0006_learning_preferences
Revises: 0005_activity_tracking
Create Date: 2026-02-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_learning_preferences"
down_revision = "0005_activity_tracking"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "learning_preferences" not in existing_tables:
        op.create_table(
            "learning_preferences",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "student_profile_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("student_profiles.id", ondelete="CASCADE"),
                nullable=False,
                unique=True,
            ),
            sa.Column("explanation_depth", sa.String(length=20), nullable=False, server_default="standard"),
            sa.Column("examples_first", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("pace", sa.String(length=20), nullable=False, server_default="normal"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.UniqueConstraint("student_profile_id", name="uq_student_profile_preference"),
        )


def downgrade():
    op.execute("DROP TABLE IF EXISTS learning_preferences")
