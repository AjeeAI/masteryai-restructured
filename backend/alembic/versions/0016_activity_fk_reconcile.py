"""reconcile activity student_id foreign keys to users.id

Revision ID: 0016_activity_fk_reconcile
Revises: 0015_activity_event_check
Create Date: 2026-02-27
"""

from alembic import op
import sqlalchemy as sa


revision = "0016_activity_fk_reconcile"
down_revision = "0015_activity_event_check"
branch_labels = None
depends_on = None


ACTIVITY_TABLES = (
    "activity_logs",
    "daily_activity_summary",
    "student_stats",
)


def _table_exists(inspector, table_name: str) -> bool:
    return table_name in set(inspector.get_table_names())


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _drop_student_id_fks(inspector, table_name: str) -> None:
    for fk in inspector.get_foreign_keys(table_name):
        constrained_columns = fk.get("constrained_columns") or []
        if constrained_columns == ["student_id"]:
            fk_name = fk.get("name")
            if fk_name:
                op.drop_constraint(fk_name, table_name, type_="foreignkey")


def _add_fk_to_users(table_name: str, fk_name: str) -> None:
    # NOT VALID allows adding constraint on shared DBs that may have legacy rows.
    op.execute(
        sa.text(
            f"""
            ALTER TABLE {table_name}
            ADD CONSTRAINT {fk_name}
            FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE NOT VALID
            """
        )
    )


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "student_profiles"):
        return

    # 1) Drop legacy student_id foreign keys first, so remapping won't violate them.
    for table_name in ACTIVITY_TABLES:
        if not _table_exists(inspector, table_name) or not _has_column(inspector, table_name, "student_id"):
            continue
        _drop_student_id_fks(inspector, table_name)

    inspector = sa.inspect(bind)

    # 2) Backfill legacy profile IDs -> user IDs where needed.
    for table_name in ACTIVITY_TABLES:
        if not _table_exists(inspector, table_name):
            continue
        if not _has_column(inspector, table_name, "student_id"):
            continue

        op.execute(
            sa.text(
                f"""
                UPDATE {table_name} t
                SET student_id = sp.student_id
                FROM student_profiles sp
                WHERE t.student_id = sp.id
                """
            )
        )

    # 3) Recreate FK constraints aligned with ORM model.
    inspector = sa.inspect(bind)
    existing_by_table = {
        table: {fk.get("name") for fk in inspector.get_foreign_keys(table) if fk.get("name")}
        for table in ACTIVITY_TABLES
        if _table_exists(inspector, table)
    }

    desired = {
        "activity_logs": "activity_logs_student_id_fkey",
        "daily_activity_summary": "daily_activity_summary_student_id_fkey",
        "student_stats": "student_stats_student_id_fkey",
    }
    for table_name, fk_name in desired.items():
        if not _table_exists(inspector, table_name):
            continue
        if fk_name not in existing_by_table.get(table_name, set()):
            _add_fk_to_users(table_name, fk_name)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table_name in ACTIVITY_TABLES:
        if not _table_exists(inspector, table_name):
            continue
        for fk in inspector.get_foreign_keys(table_name):
            constrained_columns = fk.get("constrained_columns") or []
            if constrained_columns == ["student_id"]:
                fk_name = fk.get("name")
                if fk_name:
                    op.drop_constraint(fk_name, table_name, type_="foreignkey")
