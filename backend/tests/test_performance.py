from conftest import sign_in
from sqlalchemy import event

from app.database import engine
from app.main import app
from app.web_frontend import mount_frontend


def test_readiness_checks_required_tables_in_one_statement(client):
    statements = []

    def record(_conn, _cursor, statement, _params, _context, _many):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        assert client.get("/api/health/ready").status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", record)
    selects = [s for s in statements if s.startswith("SELECT")]
    assert len(selects) == 1
    assert "auth_rate_buckets" in selects[0] and "users" in selects[0]


def test_public_assets_cache_but_accounts_and_html_do_not(client, accounts, tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>BloomCare</html>")
    (tmp_path / "assets/app-abcdefgh.js").write_text("console.log('BloomCare');" * 100)
    original_routes = list(app.router.routes)
    mount_frontend(app, tmp_path)
    try:
        asset = client.get("/assets/app-abcdefgh.js", headers={"Accept-Encoding": "gzip"})
        assert "immutable" in asset.headers["Cache-Control"]
        assert asset.headers["Content-Encoding"] == "gzip"
        assert client.get("/patient").headers["Cache-Control"] == "no-store"
        sign_in(client)
        assert client.get("/api/auth/me").headers["Cache-Control"] == "no-store"
        assert client.get("/api/missing").status_code == 404
        assert client.get("/assets/missing-abcdefgh.js").status_code == 404
    finally:
        app.router.routes[:] = original_routes


def test_notification_references_are_batched_and_patient_scoped(client, accounts):
    from app.database import SessionLocal
    from app.models import Assessment, HealthRecord, ModelVersion, Notification, utc_now

    with SessionLocal() as db:
        model = ModelVersion(
            id="synthetic", version="synthetic", artifact_sha256="0" * 64, manifest={}
        )
        db.add(model)
        db.flush()
        for i in range(12):
            owner = accounts["patient2"] if i == 10 else accounts["patient1"]
            record = HealthRecord(patient_id=owner, observations={})
            db.add(record)
            db.flush()
            assessment = Assessment(
                patient_id=owner,
                health_record_id=record.id,
                model_version_id=model.id,
                observations_snapshot={},
                maternal_risk="LOW",
                class_scores={},
                explanation={},
                pe_required=False,
                pe_status="NOT_INDICATED",
                pe_reason="Synthetic test",
                removed_at=utc_now() if i == 11 else None,
            )
            db.add(assessment)
            db.flush()
            db.add(
                Notification(
                    recipient_id=accounts["patient1"], assessment_id=assessment.id, kind=str(i)
                )
            )
        db.commit()
    sign_in(client)
    statements = []

    def record_query(_conn, _cursor, statement, _params, _context, _many):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record_query)
    try:
        response = client.get("/api/notifications")
    finally:
        event.remove(engine, "before_cursor_execute", record_query)
    assert response.status_code == 200
    items = {r["kind"]: r for r in response.json()["items"]}
    assert len(items) == 12
    assert all(items[str(i)]["health_record_id"] for i in range(10))
    assert items["10"]["health_record_id"] is None
    assert items["11"]["health_record_id"] is None
    assert len([s for s in statements if "FROM assessments" in s]) == 1
