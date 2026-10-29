import json
import sys
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from conftest import sign_in
from pydantic import SecretStr
from sqlalchemy import func, select
from test_delivery_scripts import load

from app import groq_service
from app.config import get_settings
from app.database import SessionLocal
from app.models import AssistantTurn

KEY = "fake-key-private-do-not-print"
PRIVATE = "private-provider-body-do-not-print"


def provider(monkeypatch, handler):
    original = httpx.Client
    monkeypatch.setattr(
        groq_service.httpx, "Client",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )


@pytest.fixture
def settings(monkeypatch):
    value = get_settings()
    monkeypatch.setattr(value, "groq_api_key", SecretStr(KEY))
    monkeypatch.setattr(value, "groq_model", "openai/gpt-oss-20b")
    return value


@pytest.mark.parametrize(
    ("status", "result_status", "code"),
    [
        (401, 502, "GROQ_INVALID_KEY"),
        (403, 502, "GROQ_PERMISSION_DENIED"),
        (404, 502, "GROQ_MODEL_UNAVAILABLE"),
        (400, 502, "GROQ_REQUEST_REJECTED"),
        (429, 429, "GROQ_RATE_LIMIT"),
        (500, 503, "GROQ_UNAVAILABLE"),
    ],
)
def test_provider_errors_are_specific_private_and_do_not_sign_patient_out(
    client, accounts, settings, monkeypatch, caplog, status, result_status, code
):
    sign_in(client)
    calls = []

    def fail(request):
        calls.append(request)
        return httpx.Response(status, json={"error": {"message": PRIVATE + KEY}})

    provider(monkeypatch, fail)
    result = client.post(
        "/api/patients/me/assistant",
        json={"question": "Explain records", "consent": True, "request_id": str(uuid4())},
    )
    assert result.status_code == result_status
    assert result.json()["detail"]["code"] == code
    assert PRIVATE not in result.text + caplog.text
    assert KEY not in result.text + caplog.text
    assert code in caplog.text
    assert len(calls) == 1
    assert client.get("/api/auth/me").status_code == 200
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(AssistantTurn)) == 0


@pytest.mark.parametrize("model", ["openai/gpt-oss-20b", "openai/gpt-oss-120b"])
def test_gpt_oss_request_has_budget_for_reasoning_and_returns_only_final_answer(
    settings, monkeypatch, model
):
    monkeypatch.setattr(settings, "groq_model", model)

    def reply(request):
        body = json.loads(request.content)
        assert body["max_completion_tokens"] >= 2048
        assert "max_tokens" not in body
        assert body["reasoning_effort"] == "low"
        assert body["include_reasoning"] is False
        assert "reasoning_format" not in body
        assert request.extensions["timeout"]["connect"] == 5
        return httpx.Response(200, json={"choices": [{
            "finish_reason": "stop",
            "message": {"content": " Final explanation ", "reasoning": PRIVATE},
        }]})

    provider(monkeypatch, reply)
    assert groq_service.complete(settings, [{"role": "user", "content": "Explain"}]) == (
        "Final explanation"
    )


def test_other_text_model_does_not_receive_gpt_oss_specific_parameters(settings, monkeypatch):
    monkeypatch.setattr(settings, "groq_model", "llama-3.3-70b-versatile")

    def reply(request):
        body = json.loads(request.content)
        assert "reasoning_effort" not in body and "include_reasoning" not in body
        return httpx.Response(200, json={"choices": [{"message": {"content": "Final reply"}}]})

    provider(monkeypatch, reply)
    assert groq_service.complete(settings, []) == "Final reply"


@pytest.mark.parametrize(
    ("response", "code"),
    [
        ({"choices": [{"finish_reason": "length", "message": {"content": "Partial"}}]},
         "GROQ_OUTPUT_LIMIT"),
        ({"choices": [{"message": {"content": None, "reasoning": PRIVATE}}]},
         "GROQ_INVALID_RESPONSE"),
        ({"choices": []}, "GROQ_INVALID_RESPONSE"),
    ],
)
def test_truncated_or_missing_answers_are_not_treated_as_success(
    settings, monkeypatch, response, code
):
    provider(monkeypatch, lambda request: httpx.Response(200, json=response))
    with pytest.raises(groq_service.GroqFailure) as error:
        groq_service.complete(settings, [])
    assert error.value.code == code
    assert PRIVATE not in str(error.value)


@pytest.mark.parametrize(
    ("failure", "code", "status"),
    [(httpx.ReadTimeout, "GROQ_TIMEOUT", 504), (httpx.ConnectError, "GROQ_NETWORK", 502)],
)
def test_network_failures_are_safe_and_actionable(settings, monkeypatch, failure, code, status):
    def fail(request):
        raise failure(PRIVATE + KEY, request=request)

    provider(monkeypatch, fail)
    with pytest.raises(groq_service.GroqFailure) as error:
        groq_service.complete(settings, [])
    assert error.value.code == code and error.value.status_code == status
    assert PRIVATE not in str(error.value) and KEY not in str(error.value)


def test_check_uses_only_fixed_test_text_and_requires_a_real_final_answer(
    settings, monkeypatch, capsys
):
    module = load("check_groq")
    paths = []

    def reply(request):
        paths.append(request.url.path)
        if request.method == "GET":
            return httpx.Response(200, json={"data": [{"id": settings.groq_model}]})
        body = json.loads(request.content)
        assert body["messages"] == [
            {"role": "user", "content": "Reply briefly: BloomCare connection OK."}
        ]
        return httpx.Response(200, json={"choices": [{"message": {"content": "Connection OK"}}]})

    provider(monkeypatch, reply)
    assert module.check(settings) == 0
    output = capsys.readouterr().out
    assert "test passed" in output and KEY not in output
    assert paths == ["/openai/v1/models", "/openai/v1/chat/completions"]


def test_check_does_not_send_chat_when_configured_model_is_missing(settings, monkeypatch, capsys):
    module = load("check_groq")
    monkeypatch.setattr(settings, "groq_model", "missing-model")

    def reply(request):
        assert request.method == "GET"
        return httpx.Response(200, json={"data": [{"id": "openai/gpt-oss-20b"}]})

    provider(monkeypatch, reply)
    assert module.check(settings) == 1
    output = capsys.readouterr().out
    assert "GROQ_MODEL_UNAVAILABLE" in output and KEY not in output
    assert settings.groq_model == "missing-model"


def test_check_reports_invalid_key_without_exposing_provider_body(settings, monkeypatch, capsys):
    module = load("check_groq")
    provider(monkeypatch, lambda request: httpx.Response(401, json={"error": PRIVATE + KEY}))
    assert module.check(settings) == 1
    output = capsys.readouterr().out
    assert "GROQ_INVALID_KEY (Groq HTTP 401)" in output
    assert KEY not in output and PRIVATE not in output


def test_check_fails_clearly_when_no_key_is_configured(capsys):
    module = load("check_groq")
    assert module.check(SimpleNamespace(groq_api_key=None)) == 1
    assert "GROQ_NOT_CONFIGURED" in capsys.readouterr().out


def test_model_only_configuration_preserves_key_and_all_other_settings(tmp_path, monkeypatch):
    module = load("configure_integrations")
    env = tmp_path / ".env"
    before = 'DATABASE_URL=existing\nJWT_SECRET=existing-secret\nGROQ_API_KEY="unchanged"\n'
    env.write_text(before + 'GROQ_MODEL="old-model"\n')
    monkeypatch.setattr(module, "ENV", env)
    monkeypatch.setattr(module, "getpass", lambda prompt: pytest.fail("Must keep the existing key"))
    monkeypatch.setattr(sys, "argv", [
        "configure_integrations.py", "groq-model", "--model", "openai/gpt-oss-20b",
    ])
    module.main()
    assert env.read_text() == before + 'GROQ_MODEL="openai/gpt-oss-20b"\n'
