"""Clinical review, care plans, consented alerts and assessment input snapshots."""

import sqlalchemy as sa
from alembic import op

revision = "0010_delivery_workflows"
down_revision = "0009_pe_screening"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("health_records", sa.Column("clinical_indicators", sa.JSON(), nullable=True))
    with op.batch_alter_table("health_records") as batch:
        batch.add_column(sa.Column("client_request_id", sa.String(36), nullable=True))
        batch.create_unique_constraint(
            "uq_health_record_request", ["patient_id", "client_request_id"]
        )
    op.add_column("assessments", sa.Column("clinical_snapshot", sa.JSON(), nullable=True))
    op.add_column("pe_screenings", sa.Column("explanation", sa.JSON(), nullable=True))
    with op.batch_alter_table("notifications") as batch:
        batch.add_column(sa.Column("assessment_id", sa.String(36), nullable=True))
        batch.create_foreign_key(
            "fk_notification_assessment", "assessments", ["assessment_id"], ["id"]
        )
    with op.batch_alter_table("assessments") as batch:
        batch.drop_constraint("ck_assessment_pe_gate", type_="check")
        batch.create_check_constraint(
            "ck_assessment_pe_gate",
            "(pe_required = false AND pe_status = 'NOT_INDICATED') OR "
            "(pe_required = true AND pe_status = 'UNAVAILABLE')",
        )
    with op.batch_alter_table("doctor_notes") as batch:
        batch.add_column(sa.Column("assessment_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("supersedes_id", sa.String(36), nullable=True))
        batch.create_foreign_key(
            "fk_doctor_note_assessment", "assessments", ["assessment_id"], ["id"]
        )
        batch.create_foreign_key(
            "fk_doctor_note_supersedes", "doctor_notes", ["supersedes_id"], ["id"]
        )
        batch.create_unique_constraint("uq_doctor_note_supersedes", ["supersedes_id"])

    op.create_table(
        "assessment_care_plans",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "assessment_id", sa.String(length=36), sa.ForeignKey("assessments.id"), nullable=False
        ),
        sa.Column("context_sha256", sa.String(length=64), nullable=False),
        sa.Column("context_snapshot", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("content", sa.String(length=6000), nullable=True),
        sa.Column("provider_model", sa.String(length=120), nullable=False),
        sa.Column("language", sa.String(length=2), nullable=False),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('GENERATING', 'READY', 'FAILED')", name="ck_care_plan_status"
        ),
        sa.UniqueConstraint("assessment_id", "context_sha256", name="uq_care_plan_context"),
    )
    op.create_index(
        "ix_assessment_care_plans_assessment_id", "assessment_care_plans", ["assessment_id"]
    )
    op.create_table(
        "clinical_reviews",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "assessment_id", sa.String(length=36), sa.ForeignKey("assessments.id"), nullable=False
        ),
        sa.Column(
            "appointment_id", sa.String(length=36), sa.ForeignKey("appointments.id"), nullable=False
        ),
        sa.Column("doctor_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=False),
        sa.Column("follow_up_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('PENDING', 'REVIEWED', 'URGENT_FOLLOW_UP')",
            name="ck_clinical_review_status",
        ),
        sa.CheckConstraint("version >= 1", name="ck_clinical_review_version"),
        sa.UniqueConstraint("assessment_id", name="uq_clinical_review_assessment"),
    )
    op.create_table(
        "clinical_review_events",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "review_id", sa.String(length=36), sa.ForeignKey("clinical_reviews.id"), nullable=False
        ),
        sa.Column("doctor_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "appointment_id", sa.String(length=36), sa.ForeignKey("appointments.id"), nullable=False
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("review_id", "version", name="uq_review_event_version"),
    )
    op.create_index("ix_clinical_review_events_review_id", "clinical_review_events", ["review_id"])
    op.create_table(
        "follow_up_proposals",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "appointment_id", sa.String(length=36), sa.ForeignKey("appointments.id"), nullable=False
        ),
        sa.Column(
            "assessment_id", sa.String(length=36), sa.ForeignKey("assessments.id"), nullable=False
        ),
        sa.Column("patient_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("doctor_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_id", sa.String(length=36), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "accepted_appointment_id",
            sa.String(length=36),
            sa.ForeignKey("appointments.id"),
            nullable=True,
        ),
        sa.Column("declined", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("doctor_id", "request_id", name="uq_follow_up_request"),
    )
    op.create_index("ix_follow_up_proposals_patient_id", "follow_up_proposals", ["patient_id"])
    op.create_table(
        "whatsapp_alerts",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("patient_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "assessment_id", sa.String(length=36), sa.ForeignKey("assessments.id"), nullable=False
        ),
        sa.Column("request_id", sa.String(length=36), nullable=False),
        sa.Column("recipient", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("provider_sid", sa.String(length=64), nullable=True),
        sa.Column("detail", sa.String(length=200), nullable=True),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("patient_id", "request_id", name="uq_whatsapp_request"),
    )
    op.create_index("ix_whatsapp_alerts_patient_id", "whatsapp_alerts", ["patient_id"])


def downgrade():
    raise RuntimeError(
        "This data-preserving delivery migration is forward-only. "
        "Restore a verified backup to revert."
    )
