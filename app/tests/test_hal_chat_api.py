from __future__ import annotations

import asyncio
import os
import json

import pytest
from fastapi.testclient import TestClient

from app.auth import authenticate_credentials, clear_user_registry_cache, load_users
from app.config import clear_settings_cache, default_dev_auth_users_json, load_settings, runtime_warnings
from app.hal_chat import (
    HalChatMessage,
    HalChatRequest,
    HalPageContext,
    build_prompt,
    extract_ollama_text,
    generate_hal_chat_response,
    load_integration_health_text,
)


@pytest.fixture(autouse=True)
def clear_runtime_caches() -> None:
    clear_settings_cache()
    clear_user_registry_cache()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("APP_AUTH_USERS_JSON", default_dev_auth_users_json())
    monkeypatch.setenv("HAL_BROWSER_DEV_AUTH", "1")
    from app.main import app

    return TestClient(app)


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_auth_session_dev(client: TestClient) -> None:
    response = client.get("/api/auth/session")
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "office.manager"
    assert "dashboard:read" in body["roles"]


def test_hal_chat_policy_block(client: TestClient) -> None:
    response = client.post(
        "/api/hal/chat",
        json={"message": "Please email the claim to the payer"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "policy-block"
    assert "external action" in body["message"].lower()


def test_hal_chat_ollama_success(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_call_ollama(messages, settings=None):
        del messages, settings
        return "Collections look stable and the dashboard widgets are healthy."

    monkeypatch.setattr("app.hal_chat.call_ollama", fake_call_ollama)
    monkeypatch.setattr(
        "app.hal_chat.load_integration_health_text",
        lambda: "Integration health: OK (5/5 OK).",
    )

    response = client.post(
        "/api/hal/chat",
        json={
            "message": "Summarize integration health for me",
            "pageContext": {"route": "/admin", "pageTitle": "Admin", "capturedAt": "2026-07-02T00:00:00Z"},
            "history": [{"role": "user", "content": "Hello HAL"}],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "local-ollama"
    assert "Collections look stable" in body["message"]


def test_hal_chat_ollama_fallback(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fail_call_ollama(messages, settings=None):
        del messages, settings
        raise RuntimeError("connection refused")

    monkeypatch.setattr("app.hal_chat.call_ollama", fail_call_ollama)
    monkeypatch.setattr(
        "app.hal_chat.load_integration_health_text",
        lambda: "Integration health: OK (5/5 OK).",
    )

    response = client.post("/api/hal/chat", json={"message": "What can you help with?"})
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "fallback"
    assert body["localAiUnavailable"] == "connection refused"
    assert "Integration health: OK" in body["message"]


def test_extract_ollama_text_empty_content() -> None:
    with pytest.raises(RuntimeError, match="empty response"):
        extract_ollama_text({"message": {"content": ""}, "done_reason": "stop"})


def test_extract_ollama_text_length_error() -> None:
    with pytest.raises(RuntimeError, match="token limit"):
        extract_ollama_text({"message": {"content": ""}, "done_reason": "length"})


def test_extract_ollama_text_success() -> None:
    assert extract_ollama_text({"message": {"content": " Hello "}}) == "Hello"


def test_generate_hal_chat_response_unit(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_call_ollama(messages, settings=None):
        del messages, settings
        return "Ready to help."

    monkeypatch.setattr(
        "app.hal_chat.load_integration_health_text",
        lambda: "Integration health: OK (5/5 OK).",
    )
    monkeypatch.setattr("app.hal_chat.call_ollama", fake_call_ollama)
    result = asyncio.run(generate_hal_chat_response(
        HalChatRequest(
            message="Explain the dashboard",
            page_context=HalPageContext(route="/", page_title="Dashboard", captured_at="now"),
            history=[HalChatMessage(role="assistant", content="Hi")],
        )
    ))
    assert result.mode == "local-ollama"
    assert result.message == "Ready to help."


def test_hal_chat_request_rejects_blank_message() -> None:
    with pytest.raises(ValueError, match="Message cannot be empty"):
        HalChatRequest(message="   ")


def test_build_prompt_limits_and_normalizes_history() -> None:
    history = [HalChatMessage(role="system", content=f" message {index} ") for index in range(10)]

    prompt = build_prompt(
        message="Explain the dashboard",
        history=history,
        page_context=None,
        integration_health="Integration health: OK",
    )

    assert prompt[0]["role"] == "system"
    assert len(prompt) == 10
    assert all(item["role"] in {"system", "user"} for item in prompt[:-1])
    assert prompt[1]["content"] == "message 2"
    assert prompt[-1] == {"role": "user", "content": "Explain the dashboard"}


def test_load_integration_health_text_uses_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    def fake_provider() -> str:
        calls["count"] += 1
        return "Integration health: OK"

    monkeypatch.setattr("app.hal_chat._load_integration_health_provider", lambda: fake_provider)
    monkeypatch.setattr("app.hal_chat._read_integration_health_cache", lambda now=None: None if calls["count"] == 0 else "Integration health: OK")
    monkeypatch.setattr("app.hal_chat._write_integration_health_cache", lambda value, now=None: None)

    first = load_integration_health_text()
    second = load_integration_health_text()

    assert first == "Integration health: OK"
    assert second == "Integration health: OK"
    assert calls["count"] == 1


def test_load_users_caches_hashed_passwords(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_user_registry_cache()
    payload = json.dumps(
        [
            {
                "username": "office.manager",
                "password": "office-manager",
                "roles": ["dashboard:read", "hal:operator"],
            }
        ]
    )
    monkeypatch.setenv("APP_AUTH_USERS_JSON", payload)

    users_first = load_users()
    users_second = load_users()

    assert users_first["office.manager"].password_hash == users_second["office.manager"].password_hash


def test_authenticate_credentials_rejects_wrong_password_with_basic_header(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_user_registry_cache()
    clear_settings_cache()
    monkeypatch.setenv("APP_AUTH_USERS_JSON", default_dev_auth_users_json())

    with pytest.raises(Exception) as exc_info:
        authenticate_credentials("office.manager", "wrong-password")

    exc = exc_info.value
    assert getattr(exc, "status_code", None) == 401
    assert getattr(exc, "headers", {}).get("WWW-Authenticate") == "Basic"


def test_load_settings_uses_cache_until_cleared(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HAL_OLLAMA_MODEL", "hal-chat:8b")
    first = load_settings()

    monkeypatch.setenv("HAL_OLLAMA_MODEL", "hal-chat:9b")
    second = load_settings()
    assert first.ollama_model == second.ollama_model == "hal-chat:8b"

    clear_settings_cache()
    third = load_settings()
    assert third.ollama_model == "hal-chat:9b"


def test_runtime_warnings_flags_dev_auth_without_explicit_session_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HAL_BROWSER_DEV_AUTH", "1")
    monkeypatch.delenv("APP_AUTH_SESSION_SECRET", raising=False)

    settings = load_settings()

    warnings = runtime_warnings(settings)
    assert len(warnings) == 1
    assert "APP_AUTH_SESSION_SECRET" in warnings[0]


def test_auth_session_secret_uses_explicit_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.auth import _session_secret

    monkeypatch.setenv("APP_AUTH_USERS_JSON", default_dev_auth_users_json())
    monkeypatch.setenv("APP_AUTH_SESSION_SECRET", "stable-session-secret")

    clear_settings_cache()
    first = _session_secret()

    monkeypatch.setenv("APP_AUTH_USERS_JSON", "[]")
    clear_settings_cache()
    second = _session_secret()

    assert first == second
