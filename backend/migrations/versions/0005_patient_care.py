"""Patient symptoms and medication records."""

import sqlalchemy as sa
from alembic import op

revision = "0005_patient_care"
down_revision = "0004_account_activity"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "symptom_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("patient_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("description", sa.String(1000), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_symptom_entries_patient_id", "symptom_entries", ["patient_id"])
    op.create_table(
        "medication_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("patient_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("dose", sa.String(120), nullable=False),
        sa.Column("schedule", sa.String(200), nullable=False),
        sa.Column("prescriber", sa.String(120), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_medication_entries_patient_id", "medication_entries", ["patient_id"])


def downgrade():
    op.drop_table("medication_entries")
    op.drop_table("symptom_entries")
