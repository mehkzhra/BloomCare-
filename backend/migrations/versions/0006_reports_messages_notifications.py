"""Private report uploads, consented episode sharing, messages and notifications."""

import sqlalchemy as sa
from alembic import op

revision = "0006_reports_messages"
down_revision = "0005_patient_care"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "medical_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("patient_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("media_type", sa.String(80), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_medical_reports_patient_id", "medical_reports", ["patient_id"])
    op.create_table(
        "report_shares",
        sa.Column(
            "appointment_id", sa.String(36), sa.ForeignKey("appointments.id"), primary_key=True
        ),
        sa.Column(
            "report_id", sa.String(36), sa.ForeignKey("medical_reports.id"), primary_key=True
        ),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "care_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "appointment_id", sa.String(36), sa.ForeignKey("appointments.id"), nullable=False
        ),
        sa.Column("sender_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("client_message_id", sa.String(36), nullable=False),
        sa.Column("body", sa.String(4000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "appointment_id", "sender_id", "client_message_id", name="uq_message_retry"
        ),
    )
    op.create_index("ix_care_messages_appointment_id", "care_messages", ["appointment_id"])
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("recipient_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(80), nullable=False),
        sa.Column("appointment_id", sa.String(36), sa.ForeignKey("appointments.id"), nullable=True),
        sa.Column("read", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_notifications_recipient_id", "notifications", ["recipient_id"])


def downgrade():
    for table in ("notifications", "care_messages", "report_shares", "medical_reports"):
        op.drop_table(table)
