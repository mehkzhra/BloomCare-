"""Retain a removal audit for erroneous health records and their dependent results."""

import sqlalchemy as sa
from alembic import op

revision = "0012_health_record_removal"
down_revision = "0011_assessment_removal"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "health_records", sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("health_records", sa.Column("removal_reason", sa.String(500), nullable=True))


def downgrade():
    raise RuntimeError("Restore a verified matching-version backup to revert this audit migration.")
