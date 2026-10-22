"""Save the additional PE stage without changing existing maternal results."""

import sqlalchemy as sa
from alembic import op

revision = "0009_pe_screening"
down_revision = "0008_audit_lock_fix"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "pe_screenings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("assessment_id", sa.String(36), sa.ForeignKey("assessments.id"), nullable=False),
        sa.Column("observations_snapshot", sa.JSON(), nullable=False),
        sa.Column("risk", sa.String(8), nullable=False),
        sa.Column("class_scores", sa.JSON(), nullable=False),
        sa.Column("model_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("assessment_id", name="uq_pe_screening_assessment"),
        sa.CheckConstraint("risk IN ('LOW', 'MEDIUM', 'HIGH')", name="ck_pe_screening_risk"),
    )


def downgrade():
    op.drop_table("pe_screenings")
