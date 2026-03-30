"""create prewarm jobs table

Revision ID: 0022_prewarm_jobs
Revises: 0021_merge_0019_0020
Create Date: 2026-03-13
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0022_prewarm_jobs"
down_revision = "0021_merge_0019_0020"
branch_labels = None
depends_on = None


def _table_exists(inspector, table_name: str) -> bool:
    return table_name in set(inspector.get_table_names())


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "prewarm_jobs"):
        return

    op.create_table(
        "prewarm_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("job_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("dedupe_key", sa.String(length=96), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.String(length=2000), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "job_type IN ('lesson_related','course_scope')",
            name="ck_prewarm_jobs_job_type",
        ),
        sa.CheckConstraint(
            "status IN ('queued','running','completed','failed')",
            name="ck_prewarm_jobs_status",
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_prewarm_jobs_attempts"),
    )
    op.create_index("ix_prewarm_jobs_job_type", "prewarm_jobs", ["job_type"], unique=False)
    op.create_index("ix_prewarm_jobs_status", "prewarm_jobs", ["status"], unique=False)
    op.create_index("ix_prewarm_jobs_dedupe_key", "prewarm_jobs", ["dedupe_key"], unique=False)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "prewarm_jobs"):
        return
    op.drop_index("ix_prewarm_jobs_dedupe_key", table_name="prewarm_jobs")
    op.drop_index("ix_prewarm_jobs_status", table_name="prewarm_jobs")
    op.drop_index("ix_prewarm_jobs_job_type", table_name="prewarm_jobs")
    op.drop_table("prewarm_jobs")
