"""Keep actor IDs in the audit without locking live user rows."""

import sqlalchemy as sa
from alembic import context, op

revision = "0008_audit_lock_fix"
down_revision = "0007_remaining_workflows"
branch_labels = None
depends_on = None
FK_NAME = "fk_access_audit_actor_id_users"


def audit_table(with_fk):
    metadata = sa.MetaData()
    sa.Table("users", metadata, sa.Column("id", sa.String(36), primary_key=True))
    args = [sa.ForeignKey("users.id", name=FK_NAME)] if with_fk else []
    return sa.Table(
        "access_audit",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor_id", sa.String(36), *args, nullable=True),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("route", sa.String(200), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def upgrade():
    if op.get_context().dialect.name == "sqlite":
        with op.batch_alter_table("access_audit", copy_from=audit_table(True)) as batch:
            batch.drop_constraint(FK_NAME, type_="foreignkey")
    else:
        name = "access_audit_actor_id_fkey"
        if not context.is_offline_mode():
            keys = sa.inspect(op.get_bind()).get_foreign_keys("access_audit")
            matches = [fk for fk in keys if fk["constrained_columns"] == ["actor_id"]]
            if not matches:
                return
            name = matches[0]["name"]
        op.drop_constraint(name, "access_audit", type_="foreignkey")


def downgrade():
    if op.get_context().dialect.name == "sqlite":
        with op.batch_alter_table("access_audit", copy_from=audit_table(False)) as batch:
            batch.create_foreign_key(FK_NAME, "users", ["actor_id"], ["id"])
    else:
        op.create_foreign_key(
            "access_audit_actor_id_fkey", "access_audit", "users", ["actor_id"], ["id"]
        )
