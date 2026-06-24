import json
import os
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

import app.control_routes as control_routes_module
from app.auth import clear_user_registry_cache


TEST_AUTH_USERS_JSON = json.dumps(
    [
        {
            "username": "admin",
            "display_name": "Administrator",
            "password": "password",
            "roles": ["dashboard:read", "hal:operator", "hal:index:refresh", "admin"],
        },
        {
            "username": "viewer",
            "display_name": "Viewer",
            "password": "viewer-password",
            "roles": ["dashboard:read"],
        },
    ]
)

os.environ["APP_AUTH_USERS_JSON"] = TEST_AUTH_USERS_JSON

from app.main import app


client = TestClient(app)


def setup_function():
    os.environ["APP_AUTH_USERS_JSON"] = TEST_AUTH_USERS_JSON
    runtime_dir = Path(__file__).resolve().parent / ".control_route_runtime" / uuid4().hex
    os.environ["HAL_ALLOWED_BASE_PATH"] = str(runtime_dir)
    os.environ["HAL_SQLITE_PATH"] = str(runtime_dir / "hal_test.sqlite3")
    os.environ["HAL_CHROMA_PATH"] = str(runtime_dir / "hal_chroma")
    clear_user_registry_cache()


def basic_auth():
    return ("admin", "password")


def viewer_auth():
    return ("viewer", "viewer-password")


class _FakeResponse:
    def __init__(self, payload: dict[str, object], status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise control_routes_module.requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def _fake_tags_payload() -> dict[str, object]:
    return {
        "models": [
            {
                "name": "gpt-oss:120b",
                "capabilities": ["completion", "tools", "thinking"],
                "details": {
                    "family": "gptoss",
                    "parameter_size": "116.8B",
                    "context_length": 131072,
                },
            },
            {
                "name": "qwen3:30b",
                "capabilities": ["completion", "tools", "thinking"],
                "details": {
                    "family": "qwen3moe",
                    "parameter_size": "30.5B",
                    "context_length": 262144,
                },
            },
            {
                "name": "mistral-small3.1:24b",
                "capabilities": ["completion", "tools", "vision"],
                "details": {
                    "family": "mistral3",
                    "parameter_size": "24.0B",
                    "context_length": 131072,
                },
            },
        ]
    }


def _fake_proxy_models_payload() -> dict[str, object]:
    return {
        "data": [
            {"id": "hal-chat-balanced"},
            {"id": "hal-coding"},
            {"id": "hal-analysis"},
            {"id": "hal-second-opinion"},
            {"id": "hal-vision"},
        ]
    }


def test_control_runtime_lists_models_and_suggested_defaults(monkeypatch):
    def fake_get(url, timeout=5):
        if ":11435" in url:
            return _FakeResponse({"models": []}, status_code=503)
        return _FakeResponse(_fake_tags_payload())

    monkeypatch.setattr(control_routes_module.requests, "get", fake_get)

    response = client.get("/api/control/runtime", auth=basic_auth())

    assert response.status_code == 200
    body = response.json()
    assert body["api_reachable"] is True
    assert body["model_count"] == 3
    assert body["suggested_defaults"]["coding"] == "qwen3:30b"
    assert body["suggested_defaults"]["vision"] == "mistral-small3.1:24b"
    assert body["lanes"]["frontend"]["api_reachable"] is True
    assert body["lanes"]["backend"]["api_reachable"] is False
    assert body["lanes"]["backend"]["model"] == control_routes_module.get_backend_model_name()


def test_control_route_prefers_vision_capable_model_when_required(monkeypatch):
    monkeypatch.setattr(control_routes_module.requests, "get", lambda url, timeout=5: _FakeResponse(_fake_tags_payload()))

    response = client.post(
        "/api/control/route",
        auth=basic_auth(),
        json={
            "objective": "Inspect this uploaded screenshot and summarize the UI regression.",
            "task_kind": "vision",
            "requires_vision": True,
            "quality_priority": "balanced",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["selected_model"]["name"] == "mistral-small3.1:24b"
    assert any("vision" in reason.lower() for reason in body["reasoning"])


def test_control_score_flags_missing_required_and_forbidden_terms():
    response = client.post(
        "/api/control/score",
        auth=basic_auth(),
        json={
            "objective": "Summarize the EBITDA variance clearly.",
            "model": "qwen3:30b",
            "response_text": "This weather update is short and skips the actual finance metric.",
            "rubric": {
                "required_terms": ["EBITDA"],
                "forbidden_terms": ["weather"],
                "min_words": 8,
                "minimum_score": 70,
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["passed"] is False
    assert body["missing_required"] == ["EBITDA"]
    assert body["forbidden_hits"] == ["weather"]
    assert body["score"] < 70


def test_control_workflow_preview_includes_human_review_gate(monkeypatch):
    monkeypatch.setattr(control_routes_module.requests, "get", lambda url, timeout=5: _FakeResponse(_fake_tags_payload()))

    response = client.post(
        "/api/control/workflows/preview",
        auth=basic_auth(),
        json={
            "objective": "Route a dashboard anomaly for analysis and publish it only after review.",
            "task_kind": "dashboard",
            "quality_priority": "quality",
            "requires_human_approval": True,
            "score_threshold": 82,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["automation_ready"] is True
    assert body["recommended_model"] == "gpt-oss:120b"
    assert any(step["step_id"] == "human-review" for step in body["steps"])


def test_control_route_returns_litellm_alias(monkeypatch):
    monkeypatch.setattr(control_routes_module.requests, "get", lambda url, timeout=5: _FakeResponse(_fake_tags_payload()))

    response = client.post(
        "/api/control/route",
        auth=basic_auth(),
        json={
            "objective": "Trace a frontend callback bug.",
            "task_kind": "coding",
            "quality_priority": "balanced",
            "requires_tools": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["litellm_model_alias"] == "hal-coding"
    assert body["litellm_proxy_base_url"] == control_routes_module.DEFAULT_LITELLM_PROXY_BASE_URL


def test_control_litellm_config_renders_openai_compatible_proxy_yaml(monkeypatch):
    monkeypatch.setattr(control_routes_module.requests, "get", lambda url, timeout=5: _FakeResponse(_fake_tags_payload()))

    response = client.get("/api/control/litellm/config", auth=basic_auth())

    assert response.status_code == 200
    body = response.json()
    assert body["routing_strategy"] == "simple-shuffle"
    assert body["config_path"].endswith("scripts\\litellm_ollama_router.yaml")
    assert "hal-coding" in body["config_yaml"]
    assert "ollama_chat/qwen3:30b" in body["config_yaml"]
    assert body["openai_compatible_example"]["body"]["model"] == "hal-coding"
    assert 'uv tool run --from "litellm[proxy]" litellm --config' in body["startup_command"]


def test_control_litellm_status_reports_proxy_models(monkeypatch):
    def fake_get(url, timeout=5, headers=None):
        if url.endswith("/api/tags"):
            return _FakeResponse(_fake_tags_payload())
        if url.endswith("/v1/models"):
            return _FakeResponse(_fake_proxy_models_payload())
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(control_routes_module.requests, "get", fake_get)

    response = client.get("/api/control/litellm/status", auth=basic_auth())

    assert response.status_code == 200
    body = response.json()
    assert body["reachable"] is True
    assert "hal-coding" in body["exposed_models"]
    assert any(alias["alias"] == "hal-analysis" for alias in body["configured_aliases"])


def test_control_routes_require_hal_operator_role(monkeypatch):
    monkeypatch.setattr(control_routes_module.requests, "get", lambda url, timeout=5: _FakeResponse(_fake_tags_payload()))

    response = client.get("/api/control/runtime", auth=viewer_auth())

    assert response.status_code == 403
    assert response.json() == {"detail": "Authenticated user does not have the required role for this HAL operation"}