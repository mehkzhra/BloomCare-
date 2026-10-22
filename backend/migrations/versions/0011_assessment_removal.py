"""Retain an audit copy when a patient removes an erroneous assessment."""

import sqlalchemy as sa
from alembic import op

revision = "0011_assessment_removal"
down_revision = "0010_delivery_workflows"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("assessments", sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("assessments", sa.Column("removal_reason", sa.String(500), nullable=True))


def downgrade():
    raise RuntimeError("Restore a verified matching-version backup to revert this audit migration.")
