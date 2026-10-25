"""Cloud email, single-origin delivery and safe first-administrator behaviour."""

import importlib.util
import json
import shutil
from pathlib import Path

import anyio
import httpx
import pytest
from app import account_email
from app.auth_limits import peer_identity
from app.cloud_setup import bootstrap_admin
from app.config import Settings, get_settings
from app.database import SessionLocal
from app.models import User
from app.web_frontend import SPAFiles, mount_frontend
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
from sqlalchemy import select
from starlette.exceptions import HTTPException
from starlette.requests import Request


@pytest.mark.parametrize("purpose,path", [
    ("RESET_PASSWORD", "/account/reset"), ("VERIFY_EMAIL", "/account/verify"),
])
def test_https_mail_fixed_endpoint_credential_header_and_private_link(
    monkeypatch, caplog, purpose, path
):
    settings = get_settings()
    for name, value in {
        "email_provider": "brevo", "email_from": "owner@example.com",
        "brevo_api_key": SecretStr("private-brevo-test-key"),
        "public_app_url": "https://care.example.com",
    }.items():
        monkeypatch.setattr(settings, name, value)
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(201, json={"messageId": "synthetic-id"})

    original_client = httpx.Client

    def transport_client(**kwargs):
        assert kwargs == {"timeout": 10, "follow_redirects": False, "trust_env": False}
        return original_client(**kwargs, transport=httpx.MockTransport(respond))

    monkeypatch.setattr(account_email.httpx, "Client", transport_client)
    token = "S" * 43
    account_email.send("patient@example.com", purpose, token)
    assert len(requests) == 1
    request = requests[0]
    assert str(request.url) == "https://api.brevo.com/v3/smtp/email"
    assert request.headers["api-key"] == "private-brevo-test-key"
    payload = json.loads(request.content)
    assert payload["sender"] == {"name": "BloomCare", "email": "owner@example.com"}
    assert payload["to"] == [{"email": "patient@example.com"}]
    assert f"https://care.example.com{path}#token={token}" in payload["textContent"]
    assert "private-brevo-test-key" not in caplog.text and token not in caplog.text
    assert "private-brevo-test-key" not in request.content.decode()


@pytest.mark.parametrize("status,body", [
    (302, {}), (401, {"message": "private-provider-error"}),
    (429, {}), (201, {}), (201, []), (503, {}),
])
def test_https_mail_rejects_unaccepted_responses_without_retry_or_sensitive_error(
    monkeypatch, status, body
):
    settings = get_settings()
    for name, value in {
        "email_provider": "brevo", "email_from": "owner@example.com",
        "brevo_api_key": SecretStr("private-brevo-test-key"),
    }.items():
        monkeypatch.setattr(settings, name, value)
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(status, json=body)

    original_client = httpx.Client
    monkeypatch.setattr(account_email.httpx, "Client", lambda **kw: original_client(
        **kw, transport=httpx.MockTransport(respond)
    ))
    with pytest.raises(ValueError, match="Account email could not be submitted") as error:
        account_email.send("person@example.com", "RESET_PASSWORD", "T" * 43)
    assert len(calls) == 1
    assert "private-" not in str(error.value)


def test_selected_provider_must_be_complete_before_email_enforcement():
    base = dict(
        _env_file=None, database_url="sqlite://",
        jwt_secret="private-secret-abcdefghijklmnopqrstuvwxyz-0123456789",
        auth_require_email_verification=True, email_provider="brevo",
    )
    with pytest.raises(ValidationError):
        Settings(**base, email_from="owner@example.com", brevo_api_key=" ")
    settings = Settings(**base, email_from="owner@example.com", brevo_api_key="private-key")
    assert account_email.configured(settings)
    assert not settings.smtp_host


@pytest.mark.parametrize("scheme", ["postgresql://", "postgres://", "postgresql+psycopg://"])
def test_provider_url_keeps_credentials_ssl_and_options(scheme):
    rest = "user:p%40ss@host.example.com/db?sslmode=require&channel_binding=require"
    assert Settings.restrict_database(scheme + rest) == "postgresql+psycopg://" + rest


def test_same_origin_spa_routes_do_not_swallow_api_or_missing_asset_errors(tmp_path):
    (tmp_path / "index.html").write_text("<html>BloomCare</html>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets/app.js").write_text("/* application asset */")
    app = FastAPI()

    @app.get("/api/health/live")
    def live():
        return {"status": "ok"}

    mount_frontend(app, tmp_path)
    with TestClient(app) as client:
        for path in ["/", "/patient", "/account/reset", "/doctor/appointments/example-id"]:
            response = client.get(path)
            assert response.status_code == 200 and "<html>BloomCare" in response.text
        assert client.get("/api/health/live").json() == {"status": "ok"}
        for path in ["/api", "/api/missing", "/assets/missing.js", "/missing.png"]:
            response = client.get(path)
            assert response.status_code == 404 and "<html>BloomCare" not in response.text
        assert client.get("/assets/app.js").text == "/* application asset */"
        assert client.post("/patient").status_code == 405


@pytest.mark.parametrize("path", [
    "api", "api/missing", r"api\missing", r"api\patients\missing",
])
def test_unknown_api_paths_stay_404_with_posix_and_windows_separators(tmp_path, path):
    (tmp_path / "index.html").write_text("<html>BloomCare</html>")
    frontend = SPAFiles(directory=str(tmp_path))
    scope = {"type": "http", "method": "GET", "path": "/api/missing", "headers": []}
    # StaticFiles.get_path supplies native filesystem separators on Windows.
    # Exercise those paths on every platform so an HTML fallback cannot hide them.
    with pytest.raises(HTTPException) as error:
        anyio.run(frontend.get_response, path, scope)
    assert error.value.status_code == 404


def test_first_admin_requires_mailbox_recovery_and_is_idempotent():
    assert bootstrap_admin("Owner@example.com", "Project Owner") is True
    with SessionLocal() as db:
        owner = db.scalar(select(User))
        before = (owner.id, owner.password_hash)
        assert owner.role == "admin" and owner.email == "owner@example.com"
        assert owner.email_verified_at is None
    assert bootstrap_admin("owner@example.com", "Another Name") is False
    with SessionLocal() as db:
        owner = db.scalar(select(User))
        assert (owner.id, owner.password_hash) == before
        assert owner.full_name == "Project Owner"


def test_cloud_bootstrap_cannot_promote_an_existing_patient_or_add_unexpected_admin():
    with SessionLocal() as db:
        patient = User(
            email="patient@example.com", full_name="Patient", role="patient", password_hash="keep"
        )
        db.add(patient)
        db.commit()
    for email in ["patient@example.com", "another@example.com"]:
        with pytest.raises(ValueError, match="only supports an empty database"):
            bootstrap_admin(email)
    with SessionLocal() as db:
        users = db.scalars(select(User)).all()
        assert len(users) == 1 and users[0].role == "patient" and users[0].password_hash == "keep"


def test_missing_bootstrap_is_only_allowed_after_an_admin_exists():
    with pytest.raises(ValueError, match="BOOTSTRAP_ADMIN_EMAIL"):
        bootstrap_admin(None)
    with SessionLocal() as db:
        assert db.scalar(select(User)) is None
    bootstrap_admin("owner@example.com")
    assert bootstrap_admin(None) is False


def test_bootstrapped_owner_can_establish_password_and_access_admin_through_mailbox(
    client, monkeypatch
):
    settings = get_settings()
    for key, value in {
        "auth_require_email_verification": True, "email_provider": "brevo",
        "email_from": "sender@example.com", "brevo_api_key": SecretStr("synthetic-key"),
    }.items():
        monkeypatch.setattr(settings, key, value)
    mailbox = []
    monkeypatch.setattr(account_email, "send", lambda *args: mailbox.append(args))
    bootstrap_admin("owner@example.com")
    response = client.post("/api/auth/forgot-password", json={"email": "owner@example.com"})
    assert response.status_code == 202 and len(mailbox) == 1
    recipient, purpose, token = mailbox[0]
    assert recipient == "owner@example.com" and purpose == "RESET_PASSWORD"
    password = "ChosenOwnerPassword123!"
    assert client.post("/api/auth/reset-password", json={
        "token": token, "password": password,
    }).status_code == 200
    assert client.post("/api/auth/login", json={
        "email": recipient, "password": password, "role": "admin",
    }).status_code == 200
    assert client.get("/api/admin/workspace").status_code == 200


def test_render_proxy_uses_only_the_edge_overwritten_ip_and_local_ignores_all_headers(monkeypatch):
    request = Request({
        "type": "http", "client": ("10.0.0.4", 80),
        "headers": [(b"cf-connecting-ip", b"192.0.2.4"),
                    (b"x-forwarded-for", b"198.51.100.99, 192.0.2.4")],
    })
    assert peer_identity(request) == "10.0.0.4"
    monkeypatch.setattr(get_settings(), "auth_proxy_header", "render-cloudflare")
    assert peer_identity(request) == "192.0.2.4"
    for value in [b"invalid", b"192.0.2.1, 192.0.2.2", b""]:
        invalid = Request({
            "type": "http", "client": ("10.0.0.4", 80),
            "headers": [(b"cf-connecting-ip", value), (b"x-forwarded-for", b"198.51.100.99")],
        })
        assert peer_identity(invalid) == "10.0.0.4"


def test_cloud_environment_derives_stable_key_from_render_seed_and_keeps_explicit_settings():
    script = Path(__file__).resolve().parents[2] / "deploy/start_cloud.py"
    spec = importlib.util.spec_from_file_location("bloomcare_cloud_start", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = {
        "RENDER": "true", "RENDER_EXTERNAL_URL": "https://care-example.onrender.com",
        "JWT_SECRET_SEED": "B0jrphAPOY7pg92AN0c9MN4yecczLMdwnx4OkA1KFUk=",
    }
    first, second = dict(original), dict(original)
    module.configure_environment(first)
    module.configure_environment(second)
    assert first == second and len(first["JWT_SECRET"]) == 128
    assert first["JWT_SECRET"] != original["JWT_SECRET_SEED"]
    assert first["PUBLIC_APP_URL"] == first["ALLOWED_ORIGINS"] == original["RENDER_EXTERNAL_URL"]
    assert first["AUTH_PROXY_HEADER"] == "render-cloudflare"
    assert Settings.require_real_secret(first["JWT_SECRET"]) == first["JWT_SECRET"]
    explicit = {"JWT_SECRET": "keep-existing-secret", "PUBLIC_APP_URL": "https://custom.example.com"}
    module.configure_environment(explicit)
    assert explicit["JWT_SECRET"] == "keep-existing-secret"
    assert explicit["PUBLIC_APP_URL"] == "https://custom.example.com"
    assert "AUTH_PROXY_HEADER" not in explicit
    with pytest.raises(ValueError, match="session seed"):
        module.configure_environment({"JWT_SECRET_SEED": "insufficient"})


def test_cloud_custom_origin_aligns_csrf_and_recovery_without_trusting_proxy_headers():
    script = Path(__file__).resolve().parents[2] / "deploy/start_cloud.py"
    spec = importlib.util.spec_from_file_location("bloomcare_cloud_start_custom", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    environment = {
        "PUBLIC_APP_URL": "https://bloomcare-example.code.run",
        "JWT_SECRET": "private-secret-abcdefghijklmnopqrstuvwxyz-0123456789",
    }
    module.configure_environment(environment)
    assert environment["PUBLIC_APP_URL"] == environment["ALLOWED_ORIGINS"]
    assert "AUTH_PROXY_HEADER" not in environment
    environment["ALLOWED_ORIGINS"] = "https://explicit.example.com"
    module.configure_environment(environment)
    assert environment["ALLOWED_ORIGINS"] == "https://explicit.example.com"


def test_cloud_private_pe_files_must_exist_and_match_before_serving(tmp_path, monkeypatch):
    from app.pe_model import PEModelUnavailable

    from deploy import prepare_cloud_model

    # This test isolates PE integrity from the separately verified maternal artifact.
    monkeypatch.setattr(prepare_cloud_model, "load_registered_model", lambda *_: None)
    with pytest.raises(PEModelUnavailable):
        prepare_cloud_model.verify_runtime_models(tmp_path)
    relative = Path("ml/artifacts/legacy_pe_v0.7.1")
    source = Path(__file__).resolve().parents[2] / relative
    target = tmp_path / relative
    target.mkdir(parents=True)
    for name in ["forest.json", "manifest.json", "explanation-weights.json"]:
        shutil.copyfile(source / name, target / name)
    prepare_cloud_model.verify_runtime_models(tmp_path)
    assert not (target / "parity-fixtures.json").exists()
    (target / "explanation-weights.json").write_text("{}")
    with pytest.raises(ValueError, match="weights are missing or changed"):
        prepare_cloud_model.verify_runtime_models(tmp_path)
