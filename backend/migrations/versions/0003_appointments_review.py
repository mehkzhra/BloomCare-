"""Appointment-scoped record grants, transitions, and clinician notes."""

import sqlalchemy as sa
from alembic import op

revision = "0003_appointments_review"
down_revision = "0002_research_assessments"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "appointments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("patient_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("doctor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("access_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('PENDING', 'ACCEPTED', 'REJECTED', 'CANCELLED', 'COMPLETED')",
            name="ck_appointment_status",
        ),
        sa.CheckConstraint("patient_id <> doctor_id", name="ck_appointment_participants"),
        sa.CheckConstraint(
            "(status IN ('PENDING', 'ACCEPTED') AND closed_at IS NULL) OR "
            "(status IN ('REJECTED', 'CANCELLED', 'COMPLETED') AND closed_at IS NOT NULL)",
            name="ck_appointment_closed",
        ),
        sa.CheckConstraint(
            "(accepted_at IS NULL AND access_until IS NULL "
            "AND status IN ('PENDING', 'REJECTED', 'CANCELLED')) OR "
            "(accepted_at IS NOT NULL AND access_until IS NOT NULL "
            "AND status IN ('ACCEPTED', 'CANCELLED', 'COMPLETED'))",
            name="ck_appointment_grant",
        ),
    )
    op.create_index("ix_appointments_patient_id", "appointments", ["patient_id"])
    op.create_index("ix_appointments_doctor_id", "appointments", ["doctor_id"])
    for actor in ("doctor", "patient"):
        op.create_index(
            f"uq_appointment_{actor}_slot",
            "appointments",
            [f"{actor}_id", "scheduled_at"],
            unique=True,
            postgresql_where=sa.text("status IN ('PENDING', 'ACCEPTED')"),
            sqlite_where=sa.text("status IN ('PENDING', 'ACCEPTED')"),
        )
    op.create_table(
        "appointment_records",
        sa.Column(
            "appointment_id", sa.String(36), sa.ForeignKey("appointments.id"), primary_key=True
        ),
        sa.Column(
            "health_record_id",
            sa.String(36),
            sa.ForeignKey("health_records.id"),
            primary_key=True,
        ),
    )
    op.create_table(
        "appointment_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "appointment_id", sa.String(36), sa.ForeignKey("appointments.id"), nullable=False
        ),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("from_status", sa.String(16), nullable=True),
        sa.Column("to_status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_appointment_events_appointment_id", "appointment_events", ["appointment_id"]
    )
    op.create_table(
        "doctor_notes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "appointment_id", sa.String(36), sa.ForeignKey("appointments.id"), nullable=False
        ),
        sa.Column("author_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("body", sa.String(4000), nullable=False),
        sa.Column("patient_visible", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_doctor_notes_appointment_id", "doctor_notes", ["appointment_id"])


def downgrade():
    op.drop_index("ix_doctor_notes_appointment_id", table_name="doctor_notes")
    op.drop_table("doctor_notes")
    op.drop_index("ix_appointment_events_appointment_id", table_name="appointment_events")
    op.drop_table("appointment_events")
    op.drop_table("appointment_records")
    for actor in ("patient", "doctor"):
        op.drop_index(f"uq_appointment_{actor}_slot", table_name="appointments")
        op.drop_index(f"ix_appointments_{actor}_id", table_name="appointments")
    op.drop_table("appointments")
