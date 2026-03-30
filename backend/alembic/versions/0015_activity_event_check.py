"""reconcile activity_logs event_type check for tutor session trigger

Revision ID: 0015_activity_event_check
Revises: 0014_tutor_sessions_reconcile
Create Date: 2026-02-27
"""

from alembic import op
import sqlalchemy as sa


revision = "0015_activity_event_check"
down_revision = "0014_tutor_sessions_reconcile"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "activity_logs" not in tables:
        return

    # Drop any legacy event_type check constraints to avoid conflicts.
    # FIX: Look in the 'public' schema
    rows = bind.execute(
        sa.text(
            """
            SELECT c.conname, pg_get_constraintdef(c.oid) AS definition
            FROM pg_constraint c
            JOIN pg_class t ON t.oid = c.conrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE n.nspname = 'public'
              AND t.relname = 'activity_logs'
              AND c.contype = 'c'
            """
        )
    ).mappings().all()

    for row in rows:
        definition = (row.get("definition") or "").lower()
        if "event_type" in definition:
            conname = str(row["conname"]).replace('"', '""')
            op.execute(sa.text(f'ALTER TABLE activity_logs DROP CONSTRAINT IF EXISTS "{conname}"'))

    op.create_check_constraint(
        "ck_activity_logs_event_type",
        "activity_logs",
        "event_type IN ('lesson_viewed','quiz_submitted','mastery_check_done','tutor_chat','tutor_session')",
    )


def downgrade():
    op.drop_constraint("ck_activity_logs_event_type", "activity_logs", type_="check")
    op.create_check_constraint(
        "activity_logs_event_type_check",
        "activity_logs",
        "event_type IN ('lesson_viewed','quiz_submitted','mastery_check_done','tutor_chat')",
    )