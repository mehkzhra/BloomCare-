"""Independent foundation: accounts, profiles, and patient observations."""

import sqlalchemy as sa
from alembic import op

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('patient', 'doctor', 'admin')", name="ck_role"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table(
        "patient_profiles",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("phone", sa.String(32), nullable=True),
        sa.Column("preferred_language", sa.String(2), nullable=False),
    )
    op.create_table(
        "doctor_profiles",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("specialty", sa.String(120), nullable=False),
        sa.Column("registration_number", sa.String(80), nullable=False, unique=True),
        sa.Column("approved", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "health_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("patient_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("observations", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_health_records_patient_id", "health_records", ["patient_id"])


def downgrade():
    op.drop_index("ix_health_records_patient_id", table_name="health_records")
    op.drop_table("health_records")
    op.drop_table("doctor_profiles")
    op.drop_table("patient_profiles")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
