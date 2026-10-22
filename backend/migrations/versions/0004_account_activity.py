"""Account activity and administrator decisions."""

import sqlalchemy as sa
from alembic import op

revision = "0004_account_activity"
down_revision = "0003_appointments_review"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "account_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("subject_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_account_events_actor_id", "account_events", ["actor_id"])


def downgrade():
    op.drop_index("ix_account_events_actor_id", table_name="account_events")
    op.drop_table("account_events")
