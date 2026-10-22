"""Persist experimental maternal assessments and their actual model provenance."""

import sqlalchemy as sa
from alembic import op

revision = "0002_research_assessments"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "model_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("version", sa.String(80), nullable=False),
        sa.Column("artifact_sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "assessments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("patient_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "health_record_id", sa.String(36), sa.ForeignKey("health_records.id"), nullable=False
        ),
        sa.Column(
            "model_version_id", sa.String(36), sa.ForeignKey("model_versions.id"), nullable=False
        ),
        sa.Column("observations_snapshot", sa.JSON(), nullable=False),
        sa.Column("maternal_risk", sa.String(8), nullable=False),
        sa.Column("class_scores", sa.JSON(), nullable=False),
        sa.Column("explanation", sa.JSON(), nullable=False),
        sa.Column("pe_required", sa.Boolean(), nullable=False),
        sa.Column("pe_status", sa.String(24), nullable=False),
        sa.Column("pe_reason", sa.String(500), nullable=False),
        sa.Column("research_only", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "health_record_id", "model_version_id", name="uq_assessment_record_model"
        ),
        sa.CheckConstraint("maternal_risk IN ('LOW', 'MEDIUM', 'HIGH')", name="ck_assessment_risk"),
        sa.CheckConstraint(
            "(maternal_risk = 'LOW' AND pe_required = false AND pe_status = 'NOT_INDICATED') "
            "OR (maternal_risk IN ('MEDIUM', 'HIGH') AND pe_required = true "
            "AND pe_status = 'UNAVAILABLE')",
            name="ck_assessment_pe_gate",
        ),
        sa.CheckConstraint("research_only = true", name="ck_assessment_research_only"),
    )
    op.create_index("ix_assessments_patient_id", "assessments", ["patient_id"])
    op.create_index("ix_assessments_health_record_id", "assessments", ["health_record_id"])


def downgrade():
    op.drop_index("ix_assessments_health_record_id", table_name="assessments")
    op.drop_index("ix_assessments_patient_id", table_name="assessments")
    op.drop_table("assessments")
    op.drop_table("model_versions")
