"""Email action tokens, persisted authentication throttles and session revocation."""

import sqlalchemy as sa
from alembic import op

revision = "0013_account_security"
down_revision = "0012_health_record_removal"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True)))
    op.add_column(
        "users", sa.Column("session_version", sa.Integer(), nullable=False, server_default="0")
    )
    op.create_table(
        "email_action_tokens",
        sa.Column("digest", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("purpose", sa.String(20), nullable=False),
        sa.Column("session_version", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "purpose IN ('VERIFY_EMAIL', 'RESET_PASSWORD')", name="ck_email_purpose"
        ),
    )
    op.create_index("ix_email_action_tokens_user_id", "email_action_tokens", ["user_id"])
    op.create_index("ix_email_action_tokens_expires_at", "email_action_tokens", ["expires_at"])
    op.create_table(
        "auth_rate_buckets",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
    )
    op.create_index("ix_auth_rate_buckets_window_start", "auth_rate_buckets", ["window_start"])


def downgrade():
    raise RuntimeError("Restore a verified matching-version backup to revert account security.")
