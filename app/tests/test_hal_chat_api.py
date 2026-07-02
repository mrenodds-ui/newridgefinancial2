from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.config import default_dev_auth_users_json
from app.hal_chat import HalChatMessage, HalChatRequest, HalPageContext, generate_hal_chat_response


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
    def fake_call_ollama(messages, settings=None):
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
    def fail_call_ollama(messages, settings=None):
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


def test_generate_hal_chat_response_unit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.hal_chat.load_integration_health_text",
        lambda: "Integration health: OK (5/5 OK).",
    )
    monkeypatch.setattr("app.hal_chat.call_ollama", lambda messages, settings=None: "Ready to help.")
    result = generate_hal_chat_response(
        HalChatRequest(
            message="Explain the dashboard",
            page_context=HalPageContext(route="/", page_title="Dashboard", captured_at="now"),
            history=[HalChatMessage(role="assistant", content="Hi")],
        )
    )
    assert result.mode == "local-ollama"
    assert result.message == "Ready to help."
