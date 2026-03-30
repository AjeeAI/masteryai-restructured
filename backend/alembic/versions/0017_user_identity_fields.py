"""add optional identity profile fields to users

Revision ID: 0017_user_identity_fields
Revises: 0016_activity_fk_reconcile
Create Date: 2026-02-27
"""

from alembic import op
import sqlalchemy as sa


revision = "0017_user_identity_fields"
down_revision = "0016_activity_fk_reconcile"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "users" not in tables:
        return

    if not _has_column(inspector, "users", "first_name"):
        op.add_column("users", sa.Column("first_name", sa.String(length=100), nullable=True))
    if not _has_column(inspector, "users", "last_name"):
        op.add_column("users", sa.Column("last_name", sa.String(length=100), nullable=True))
    if not _has_column(inspector, "users", "display_name"):
        op.add_column("users", sa.Column("display_name", sa.String(length=150), nullable=True))
    if not _has_column(inspector, "users", "avatar_url"):
        op.add_column("users", sa.Column("avatar_url", sa.String(length=500), nullable=True))
    if not _has_column(inspector, "users", "phone"):
        op.add_column("users", sa.Column("phone", sa.String(length=30), nullable=True))

    # Soft backfill display_name from first/last/email where possible.
    op.execute(
        sa.text(
            """
            UPDATE users
            SET display_name = COALESCE(
                NULLIF(TRIM(CONCAT(COALESCE(first_name, ''), ' ', COALESCE(last_name, ''))), ''),
                split_part(email, '@', 1)
            )
            WHERE display_name IS NULL OR TRIM(display_name) = ''
            """
        )
    )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "users" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("users")}
    if "phone" in columns:
        op.drop_column("users", "phone")
    if "avatar_url" in columns:
        op.drop_column("users", "avatar_url")
    if "display_name" in columns:
        op.drop_column("users", "display_name")
    if "last_name" in columns:
        op.drop_column("users", "last_name")
    if "first_name" in columns:
        op.drop_column("users", "first_name")
