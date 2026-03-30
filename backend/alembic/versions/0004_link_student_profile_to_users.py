"""link student_profiles.student_id to users.id

Revision ID: 0004_profile_user_fk
Revises: 0003_create_users_table
Create Date: 2026-02-24
"""

from alembic import op

revision = "0004_profile_user_fk"
down_revision = "0003_create_users_table"
branch_labels = None
depends_on = None


def upgrade():
    # Backfill user rows for any existing student_profiles without a matching user.
    # This keeps shared DB migrations safe and allows FK creation.
    op.execute(
        """
        INSERT INTO users (id, email, password_hash, role, is_active, created_at, updated_at)
        SELECT
            sp.student_id,
            'seed_' || REPLACE(sp.student_id::text, '-', '') || '@masteryai.local',
            '$2b$12$5JY6jsA5q9ODaW6fNfcohOx5l6v3PK2hQd1qi97V6S9bxR5D8Qqbi',
            'student',
            true,
            NOW(),
            NOW()
        FROM student_profiles sp
        LEFT JOIN users u ON u.id = sp.student_id
        WHERE u.id IS NULL
        """
    )

    op.create_foreign_key(
        "fk_student_profiles_student_id_users",
        "student_profiles",
        "users",
        ["student_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade():
    op.drop_constraint("fk_student_profiles_student_id_users", "student_profiles", type_="foreignkey")
