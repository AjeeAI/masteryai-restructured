"""create admin curriculum and governance tables

Revision ID: 0020_admin_curriculum_ops
Revises: 0018_mastery_dashboard_tables
Create Date: 2026-02-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0020_admin_curriculum_ops"
down_revision = "0018_mastery_dashboard_tables"
branch_labels = None
depends_on = None


def _table_exists(inspector, table_name: str) -> bool:
    return table_name in set(inspector.get_table_names())


def _column_exists(inspector, table_name: str, column_name: str) -> bool:
    if table_name not in set(inspector.get_table_names()):
        return False
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "curriculum_versions"):
        op.create_table(
            "curriculum_versions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("version_name", sa.String(length=100), nullable=False),
            sa.Column("subject", sa.String(length=50), nullable=False),
            sa.Column("sss_level", sa.String(length=10), nullable=False),
            sa.Column("term", sa.Integer(), nullable=False),
            sa.Column("source_root", sa.String(length=500), nullable=False),
            sa.Column("source_file_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
            sa.Column(
                "metadata_payload",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "uploaded_by",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "approved_by",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.UniqueConstraint("version_name", name="uq_curriculum_versions_version_name"),
            sa.CheckConstraint("subject IN ('math','english','civic')", name="ck_curriculum_versions_subject"),
            sa.CheckConstraint("sss_level IN ('SSS1','SSS2','SSS3')", name="ck_curriculum_versions_sss_level"),
            sa.CheckConstraint("term BETWEEN 1 AND 3", name="ck_curriculum_versions_term"),
            sa.CheckConstraint(
                "status IN ('draft','ingesting','pending_approval','approved','published','rolled_back','failed')",
                name="ck_curriculum_versions_status",
            ),
        )
        op.create_index("ix_curriculum_versions_version_name", "curriculum_versions", ["version_name"], unique=True)
        op.create_index("ix_curriculum_versions_subject", "curriculum_versions", ["subject"], unique=False)
        op.create_index("ix_curriculum_versions_sss_level", "curriculum_versions", ["sss_level"], unique=False)
        op.create_index("ix_curriculum_versions_term", "curriculum_versions", ["term"], unique=False)
        op.create_index("ix_curriculum_versions_status", "curriculum_versions", ["status"], unique=False)
        op.create_index("ix_curriculum_versions_uploaded_by", "curriculum_versions", ["uploaded_by"], unique=False)
        op.create_index("ix_curriculum_versions_approved_by", "curriculum_versions", ["approved_by"], unique=False)

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "curriculum_ingestion_jobs"):
        op.create_table(
            "curriculum_ingestion_jobs",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "version_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("curriculum_versions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="queued"),
            sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("current_stage", sa.String(length=50), nullable=True),
            sa.Column("processed_files_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("processed_chunks_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_message", sa.String(length=2000), nullable=True),
            sa.Column(
                "logs_payload",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column(
                "created_by",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.CheckConstraint(
                "status IN ('queued','parsing','chunking','embedding','indexing','completed','failed')",
                name="ck_curriculum_ingestion_jobs_status",
            ),
            sa.CheckConstraint("progress_percent BETWEEN 0 AND 100", name="ck_curriculum_ingestion_jobs_progress"),
            sa.CheckConstraint("processed_files_count >= 0", name="ck_curriculum_ingestion_jobs_files_count"),
            sa.CheckConstraint("processed_chunks_count >= 0", name="ck_curriculum_ingestion_jobs_chunks_count"),
        )
        op.create_index("ix_curriculum_ingestion_jobs_version_id", "curriculum_ingestion_jobs", ["version_id"], unique=False)
        op.create_index("ix_curriculum_ingestion_jobs_status", "curriculum_ingestion_jobs", ["status"], unique=False)
        op.create_index(
            "ix_curriculum_ingestion_jobs_created_by",
            "curriculum_ingestion_jobs",
            ["created_by"],
            unique=False,
        )

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "curriculum_topic_maps"):
        op.create_table(
            "curriculum_topic_maps",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "version_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("curriculum_versions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "topic_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("topics.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("concept_id", sa.String(length=128), nullable=False),
            sa.Column(
                "prereq_concept_ids",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column("confidence", sa.Numeric(5, 4), nullable=False, server_default="0.5"),
            sa.Column("is_manual_override", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column(
                "created_by",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.UniqueConstraint("version_id", "topic_id", "concept_id", name="uq_curriculum_topic_maps_triplet"),
            sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_curriculum_topic_maps_confidence"),
        )
        op.create_index("ix_curriculum_topic_maps_version_id", "curriculum_topic_maps", ["version_id"], unique=False)
        op.create_index("ix_curriculum_topic_maps_topic_id", "curriculum_topic_maps", ["topic_id"], unique=False)
        op.create_index("ix_curriculum_topic_maps_concept_id", "curriculum_topic_maps", ["concept_id"], unique=False)
        op.create_index(
            "ix_curriculum_topic_maps_is_manual_override",
            "curriculum_topic_maps",
            ["is_manual_override"],
            unique=False,
        )
        op.create_index("ix_curriculum_topic_maps_created_by", "curriculum_topic_maps", ["created_by"], unique=False)

    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "governance_hallucinations"):
        op.create_table(
            "governance_hallucinations",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "student_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "session_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("tutor_sessions.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("endpoint", sa.String(length=100), nullable=False),
            sa.Column("reason_code", sa.String(length=100), nullable=False),
            sa.Column("severity", sa.String(length=20), nullable=False, server_default="medium"),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
            sa.Column("prompt_excerpt", sa.String(length=2000), nullable=True),
            sa.Column("response_excerpt", sa.String(length=4000), nullable=True),
            sa.Column(
                "citation_ids",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column(
                "evidence_payload",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "reviewer_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("resolution_note", sa.String(length=2000), nullable=True),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.CheckConstraint(
                "severity IN ('low','medium','high')",
                name="ck_governance_hallucinations_severity",
            ),
            sa.CheckConstraint(
                "status IN ('open','quarantined','dismissed','resolved')",
                name="ck_governance_hallucinations_status",
            ),
        )
        op.create_index(
            "ix_governance_hallucinations_student_id",
            "governance_hallucinations",
            ["student_id"],
            unique=False,
        )
        op.create_index(
            "ix_governance_hallucinations_session_id",
            "governance_hallucinations",
            ["session_id"],
            unique=False,
        )
        op.create_index("ix_governance_hallucinations_endpoint", "governance_hallucinations", ["endpoint"], unique=False)
        op.create_index(
            "ix_governance_hallucinations_reason_code",
            "governance_hallucinations",
            ["reason_code"],
            unique=False,
        )
        op.create_index("ix_governance_hallucinations_severity", "governance_hallucinations", ["severity"], unique=False)
        op.create_index("ix_governance_hallucinations_status", "governance_hallucinations", ["status"], unique=False)
        op.create_index(
            "ix_governance_hallucinations_reviewer_id",
            "governance_hallucinations",
            ["reviewer_id"],
            unique=False,
        )

    inspector = sa.inspect(bind)
    if _column_exists(inspector, "topics", "curriculum_version_id"):
        existing_fk_names = {fk.get("name") for fk in inspector.get_foreign_keys("topics")}
        if "fk_topics_curriculum_version_id" not in existing_fk_names:
            op.create_foreign_key(
                "fk_topics_curriculum_version_id",
                "topics",
                "curriculum_versions",
                ["curriculum_version_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _column_exists(inspector, "topics", "curriculum_version_id"):
        existing_fk_names = {fk.get("name") for fk in inspector.get_foreign_keys("topics")}
        if "fk_topics_curriculum_version_id" in existing_fk_names:
            op.drop_constraint("fk_topics_curriculum_version_id", "topics", type_="foreignkey")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "governance_hallucinations"):
        op.drop_index("ix_governance_hallucinations_reviewer_id", table_name="governance_hallucinations")
        op.drop_index("ix_governance_hallucinations_status", table_name="governance_hallucinations")
        op.drop_index("ix_governance_hallucinations_severity", table_name="governance_hallucinations")
        op.drop_index("ix_governance_hallucinations_reason_code", table_name="governance_hallucinations")
        op.drop_index("ix_governance_hallucinations_endpoint", table_name="governance_hallucinations")
        op.drop_index("ix_governance_hallucinations_session_id", table_name="governance_hallucinations")
        op.drop_index("ix_governance_hallucinations_student_id", table_name="governance_hallucinations")
        op.drop_table("governance_hallucinations")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "curriculum_topic_maps"):
        op.drop_index("ix_curriculum_topic_maps_created_by", table_name="curriculum_topic_maps")
        op.drop_index("ix_curriculum_topic_maps_is_manual_override", table_name="curriculum_topic_maps")
        op.drop_index("ix_curriculum_topic_maps_concept_id", table_name="curriculum_topic_maps")
        op.drop_index("ix_curriculum_topic_maps_topic_id", table_name="curriculum_topic_maps")
        op.drop_index("ix_curriculum_topic_maps_version_id", table_name="curriculum_topic_maps")
        op.drop_table("curriculum_topic_maps")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "curriculum_ingestion_jobs"):
        op.drop_index("ix_curriculum_ingestion_jobs_created_by", table_name="curriculum_ingestion_jobs")
        op.drop_index("ix_curriculum_ingestion_jobs_status", table_name="curriculum_ingestion_jobs")
        op.drop_index("ix_curriculum_ingestion_jobs_version_id", table_name="curriculum_ingestion_jobs")
        op.drop_table("curriculum_ingestion_jobs")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "curriculum_versions"):
        op.drop_index("ix_curriculum_versions_approved_by", table_name="curriculum_versions")
        op.drop_index("ix_curriculum_versions_uploaded_by", table_name="curriculum_versions")
        op.drop_index("ix_curriculum_versions_status", table_name="curriculum_versions")
        op.drop_index("ix_curriculum_versions_term", table_name="curriculum_versions")
        op.drop_index("ix_curriculum_versions_sss_level", table_name="curriculum_versions")
        op.drop_index("ix_curriculum_versions_subject", table_name="curriculum_versions")
        op.drop_index("ix_curriculum_versions_version_name", table_name="curriculum_versions")
        op.drop_table("curriculum_versions")
