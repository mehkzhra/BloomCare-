import pytest
from conftest import sign_in
from sqlalchemy import select, text

from app.database import SessionLocal, engine
from app.models import AccessAudit, User


def test_preserved_audit_actor_can_be_unavailable_without_breaking_history(client, accounts):
    with SessionLocal() as db:
        db.add(
            AccessAudit(actor_id="former-account", method="GET", route="/api/demo", status_code=200)
        )
        db.commit()
    sign_in(client, "admin")
    result = client.get("/api/admin/audit")
    assert result.status_code == 200
    assert any(r["actor"] == "Deleted account" for r in result.json())


@pytest.mark.skipif(
    engine.dialect.name != "postgresql", reason="Requires actual PostgreSQL row locks"
)
def test_audit_commits_while_actor_row_is_locked(accounts):
    with SessionLocal() as request_db:
        request_db.scalar(select(User).where(User.id == accounts["patient1"]).with_for_update())
        with SessionLocal() as audit_db:
            audit_db.execute(text("SET LOCAL lock_timeout = '1500ms'"))
            audit_db.add(
                AccessAudit(
                    actor_id=accounts["patient1"], method="GET", route="/api/demo", status_code=200
                )
            )
            audit_db.commit()
        # Request transaction stays locked until after the separate audit commit.
        request_db.rollback()
