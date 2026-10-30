"""Configuration truth, network modes, credential minimisation and role permissions."""

import json

import pytest
from conftest import sign_in
from pydantic import SecretStr

from app import integration_status
from app.config import get_settings
from app.groq_service import GroqFailure
from app.integration_status import parse_ice_servers, service_configuration


def test_admin_ai_check_is_explicit_private_and_rate_limited(client, accounts, monkeypatch):
    calls = []
    monkeypatch.setattr(
        integration_status, "complete", lambda settings, messages: calls.append(messages) or "OK"
    )
    path = "/api/admin/service-configuration/groq/check"
    assert client.post(path).status_code == 401
    sign_in(client, "patient1")
    assert client.post(path).status_code == 403
    sign_in(client, "doctor1")
    assert client.post(path).status_code == 403
    sign_in(client, "admin")
    client.get("/api/admin/service-configuration")
    assert calls == []
    for _ in range(3):
        response = client.post(path)
        assert response.status_code == 200 and response.json()["ok"] is True
    assert calls == [[{"role": "user", "content": "Reply with OK only."}]] * 3
    assert client.post(path).status_code == 429


def test_admin_ai_check_reports_provider_failure(client, accounts, monkeypatch):
    def fail(*args):
        raise GroqFailure("GROQ_INVALID_KEY", "Groq rejected the server API key.", 502)

    monkeypatch.setattr(integration_status, "complete", fail)
    sign_in(client, "admin")
    response = client.post("/api/admin/service-configuration/groq/check")
    assert response.json() == {
        "ok": False,
        "code": "GROQ_INVALID_KEY",
        "message": "Groq rejected the server API key.",
    }


@pytest.mark.parametrize(
    "raw,mode",
    [
        ("[]", "DIRECT_ONLY"),
        (" [ ] ", "DIRECT_ONLY"),
        ('[{"urls":"stun:example.invalid:3478"}]', "STUN_CONFIGURED"),
        (
            '[{"urls":["turns:example.invalid:5349"],"username":"private-user","credential":"private-turn-password"}]',
            "RELAY_CONFIGURED",
        ),
        ('[{"urls":[]}]', "INVALID"),
        ('[{"urls":"https://example.invalid"}]', "INVALID"),
        ('[{"urls":"turn:"}]', "INVALID"),
        ('{"urls":"stun:example.invalid"}', "INVALID"),
        ("not JSON", "INVALID"),
    ],
)
def test_direct_and_configured_network_modes_are_not_confused(monkeypatch, raw, mode):
    monkeypatch.setattr(get_settings(), "webrtc_ice_servers", raw)
    status = service_configuration()["video"]
    assert status["status"] == mode
    assert status["verified_live"] is False
    assert "private-turn-password" not in json.dumps(status)
    if mode == "INVALID":
        with pytest.raises(ValueError):
            parse_ice_servers(raw)


def test_missing_optional_services_are_actionable_and_hide_config_values(
    client, accounts, monkeypatch
):
    settings = get_settings()
    for key in ["groq_api_key", "twilio_account_sid", "twilio_auth_token", "twilio_whatsapp_from"]:
        monkeypatch.setattr(settings, key, None)
    monkeypatch.setattr(settings, "twilio_allowed_recipients", "")
    monkeypatch.setattr(settings, "webrtc_ice_servers", "[]")
    sign_in(client, "admin")
    response = client.get("/api/admin/service-configuration")
    assert response.status_code == 200, response.text
    data = response.json()["services"]
    assert data["video"]["label"] == "Direct connection mode"
    assert data["whatsapp"]["manual_sharing_available"] is True
    assert data["whatsapp"]["missing"] == [
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_WHATSAPP_FROM",
        "TWILIO_ALLOWED_RECIPIENTS",
    ]
    assert data["groq"]["missing"] == ["GROQ_API_KEY"]
    monkeypatch.setattr(settings, "groq_api_key", SecretStr("private-groq-value"))
    monkeypatch.setattr(settings, "twilio_account_sid", "AC" + "1" * 32)
    monkeypatch.setattr(settings, "twilio_auth_token", SecretStr("private-token"))
    monkeypatch.setattr(settings, "twilio_whatsapp_from", "whatsapp:+15555550100")
    monkeypatch.setattr(settings, "twilio_allowed_recipients", "+923001234567")
    response = client.get("/api/admin/service-configuration")
    assert response.json()["services"]["whatsapp"]["status"] == "CONFIGURED"
    for value in ["private-groq-value", "private-token", "+15555550100", "+923001234567"]:
        assert value not in response.text


@pytest.mark.parametrize("account", ["patient1", "doctor1"])
def test_only_admin_sees_service_details_and_participants_receive_safe_video_readiness(
    client, accounts, account
):
    sign_in(client, account)
    assert client.get("/api/admin/service-configuration").status_code == 403
    response = client.get("/api/consultation-readiness")
    assert response.status_code == 200
    assert set(response.json()) == {"status", "label", "summary", "verified_live"}
