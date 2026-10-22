"""Groq requests with safe, actionable errors and no raw provider error output."""

import httpx

BASE_URL = "https://api.groq.com/openai/v1"
GPT_OSS_MODELS = {"openai/gpt-oss-20b", "openai/gpt-oss-120b"}


class GroqFailure(Exception):
    def __init__(self, code, message, status_code=502, upstream_status=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.upstream_status = upstream_status


def status_failure(status):
    failures = {
        401: (
            "GROQ_INVALID_KEY",
            "Groq rejected the server API key. The administrator must update it.",
        ),
        403: (
            "GROQ_PERMISSION_DENIED",
            "Groq denied this request. The administrator must check model and project permissions.",
        ),
        404: (
            "GROQ_MODEL_UNAVAILABLE",
            "The configured Groq model is unavailable. "
            "The administrator must choose an accessible model.",
        ),
        400: (
            "GROQ_REQUEST_REJECTED",
            "Groq rejected the model or request settings. Run the Groq connection check.",
        ),
        413: ("GROQ_CONTEXT_TOO_LARGE", "Too much context was selected. Try fewer records."),
        422: (
            "GROQ_REQUEST_REJECTED",
            "Groq could not process this request. Try a shorter question or fewer records.",
        ),
        429: (
            "GROQ_RATE_LIMIT",
            "Groq's rate or usage limit was reached. "
            "Wait before trying again and check account limits.",
        ),
    }
    code, message = failures.get(
        status,
        ("GROQ_UNAVAILABLE", "The assistant provider is temporarily unavailable. Try again later."),
    )
    return GroqFailure(
        code, message, 429 if status == 429 else 503 if status >= 500 else 502, status
    )


def _request(settings, method, path, payload=None):
    if not settings.groq_api_key:
        raise GroqFailure("GROQ_NOT_CONFIGURED", "The server Groq API key is not configured.", 503)
    headers = {"Authorization": "Bearer " + settings.groq_api_key.get_secret_value()}
    try:
        with httpx.Client(timeout=httpx.Timeout(30, connect=5)) as client:
            if method == "GET":
                response = client.get(BASE_URL + path, headers=headers)
            else:
                response = client.post(BASE_URL + path, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as error:
        # Provider messages may repeat prompts, records or keys. Never forward them.
        raise status_failure(error.response.status_code) from None
    except httpx.TimeoutException:
        raise GroqFailure(
            "GROQ_TIMEOUT", "The assistant took too long to respond. Please try again.", 504
        ) from None
    except httpx.RequestError:
        raise GroqFailure(
            "GROQ_NETWORK", "Groq could not be reached. Check the server's internet connection."
        ) from None
    except ValueError:
        raise GroqFailure(
            "GROQ_INVALID_RESPONSE", "Groq returned an unreadable response."
        ) from None
    if not isinstance(data, dict):
        raise GroqFailure("GROQ_INVALID_RESPONSE", "Groq returned an unreadable response.")
    return data


def available_models(settings):
    data = _request(settings, "GET", "/models")
    rows = data.get("data")
    if not isinstance(rows, list):
        raise GroqFailure("GROQ_INVALID_RESPONSE", "Groq returned an unreadable model list.")
    return {row["id"] for row in rows if isinstance(row, dict) and isinstance(row.get("id"), str)}


def complete(settings, messages):
    payload = {
        "model": settings.groq_model,
        "temperature": 0.2,
        "max_completion_tokens": 1024,
        "messages": messages,
    }
    if settings.groq_model in GPT_OSS_MODELS:
        payload.update(
            max_completion_tokens=2048,
            reasoning_effort="low",
            include_reasoning=False,
            temperature=0.6,
        )
    data = _request(settings, "POST", "/chat/completions", payload)
    try:
        choice = data["choices"][0]
        if choice.get("finish_reason") == "length":
            raise GroqFailure(
                "GROQ_OUTPUT_LIMIT",
                "The reply was cut short. Ask a shorter, more specific question.",
            )
        answer = choice["message"]["content"]
        if not isinstance(answer, str) or not answer.strip() or len(answer) > 6000:
            raise ValueError("Invalid final answer")
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        raise GroqFailure(
            "GROQ_INVALID_RESPONSE", "Groq did not return a usable final answer. Please try again."
        ) from None
    return answer.strip()
