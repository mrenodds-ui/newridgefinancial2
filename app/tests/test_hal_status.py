from __future__ import annotations

import json
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.auth import clear_user_registry_cache
from app.ai_local_config import get_backend_base_url, get_backend_model_name, get_frontend_base_url, get_frontend_model_name
import app.hal.orchestrator as hal_orchestrator
from app.tests.lane_routing_test_helpers import (
    BACKEND_LANE_URL,
    FRONTEND_LANE_URL,
    make_ollama_runtime_status_mock,
)


TEST_AUTH_USERS_JSON = json.dumps(
    [
        {
            "username": "hal_operator",
            "display_name": "HAL Operator",
            "password": "hal-password",
            "roles": ["dashboard:read", "hal:operator"],
        }
    ]
)

os.environ["APP_AUTH_USERS_JSON"] = TEST_AUTH_USERS_JSON

from app.main import app


client = TestClient(app)


def setup_function() -> None:
    os.environ["APP_AUTH_USERS_JSON"] = TEST_AUTH_USERS_JSON
    runtime_dir = os.path.join(os.path.dirname(__file__), ".hal_status_runtime", uuid4().hex)
    os.environ["HAL_ALLOWED_BASE_PATH"] = runtime_dir
    os.environ["HAL_SQLITE_PATH"] = os.path.join(runtime_dir, "hal_test.sqlite3")
    os.environ["HAL_CHROMA_PATH"] = os.path.join(runtime_dir, "hal_chroma")
    clear_user_registry_cache()


def operator_auth() -> tuple[str, str]:
    return ("hal_operator", "hal-password")


def _runtime_payload(*, base_url: str, reachable: bool, models: list[str]) -> dict[str, object]:
    return {
        "base_url": base_url,
        "installed": bool(models),
        "running": reachable,
        "api_reachable": reachable,
        "installed_models": models,
        "model_count": len(models),
        "error": None if reachable else "connection refused",
    }


def test_hal_status_operating_picture_reports_frontend_and_backend_lanes(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_runtime_status, calls = make_ollama_runtime_status_mock(
        frontend_reachable=True,
        backend_reachable=False,
    )
    monkeypatch.setattr(hal_orchestrator, "get_ollama_runtime_status", fake_runtime_status)

    response = client.get("/api/hal9000/status", auth=operator_auth())

    assert response.status_code == 200
    operating_picture = response.json()["operating_picture"]
    assert operating_picture["frontend_runtime"]["api_reachable"] is True
    assert operating_picture["backend_runtime"]["api_reachable"] is False
    assert operating_picture["local_runtimes"]["frontend"]["model"] == get_frontend_model_name()
    assert operating_picture["backend_runtime"]["model"] == get_backend_model_name()
    assert "Backend lane is unavailable" in operating_picture["summary"]
    assert operating_picture["model_routing"]["code_help"]["base_url"] == get_backend_base_url()
    assert operating_picture["model_routing"]["code_help"]["model"] == get_backend_model_name()
    assert FRONTEND_LANE_URL in calls[0] or get_frontend_base_url() in calls
    assert any(":11434" in url for url in calls)
    assert any(":11435" in url for url in calls)
    assert all(":11436" not in url for url in calls)


def test_hal_status_reports_backend_lane_up_when_reachable(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_runtime_status, calls = make_ollama_runtime_status_mock(
        frontend_reachable=True,
        backend_reachable=True,
    )
    monkeypatch.setattr(hal_orchestrator, "get_ollama_runtime_status", fake_runtime_status)

    response = client.get("/api/hal9000/status", auth=operator_auth())

    assert response.status_code == 200
    operating_picture = response.json()["operating_picture"]
    assert operating_picture["frontend_runtime"]["api_reachable"] is True
    assert operating_picture["backend_runtime"]["api_reachable"] is True
    assert "Backend lane is reachable" in operating_picture["summary"]
    assert len({url for url in calls if ":11434" in url or get_frontend_base_url() in url}) >= 1
    assert len({url for url in calls if ":11435" in url or get_backend_base_url() in url}) >= 1
