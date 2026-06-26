from __future__ import annotations

import json
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.hal.financial_tools as financial_tools
from app.auth import clear_user_registry_cache
from app.main import app

TEST_AUTH_USERS_JSON = json.dumps(
    [
        {
            "username": "office_manager",
            "display_name": "Office Manager",
            "password": "office-password",
            "roles": ["dashboard:read", "hal:operator"],
        },
        {
            "username": "viewer_only",
            "display_name": "Viewer Only",
            "password": "viewer-password",
            "roles": ["dashboard:read"],
        },
    ]
)

os.environ["APP_AUTH_USERS_JSON"] = TEST_AUTH_USERS_JSON
client = TestClient(app)


@pytest.fixture(autouse=True)
def _runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime_dir = os.path.join(os.path.dirname(__file__), ".office_manager_runtime", uuid4().hex)
    os.environ["APP_AUTH_USERS_JSON"] = TEST_AUTH_USERS_JSON
    os.environ["HAL_ALLOWED_BASE_PATH"] = runtime_dir
    os.environ["HAL_SQLITE_PATH"] = os.path.join(runtime_dir, "hal_test.sqlite3")
    clear_user_registry_cache()
    monkeypatch.setattr(
        financial_tools,
        "get_financial_source_status",
        lambda: {
            "softdent": {"status": "available", "summary": "SoftDent exports available."},
            "quickbooks": {"status": "available", "summary": "QuickBooks summary available."},
        },
    )


def office_manager_auth() -> tuple[str, str]:
    return ("office_manager", "office-password")


def test_office_manager_attention_requires_hal_operator() -> None:
    response = client.get("/api/hal9000/office-manager/attention", auth=("viewer_only", "viewer-password"))
    assert response.status_code == 403


def test_office_manager_attention_returns_safe_items() -> None:
    response = client.get("/api/hal9000/office-manager/attention", auth=office_manager_auth())
    assert response.status_code == 200
    payload = response.json()
    assert payload["submission_status"] == "not_submitted"
    assert payload["local_only"] is True
    assert payload["external_action_performed"] is False
    assert payload["softdent_writeback_performed"] is False
    assert payload["items"]
    assert any(item["category"] == "treatment_plan" for item in payload["items"])
    assert any("missing_treatment_plan_export" in item.get("missing_data_codes", []) for item in payload["items"])


def test_office_manager_task_create_list_update() -> None:
    create_response = client.post(
        "/api/hal9000/office-manager/tasks",
        auth=office_manager_auth(),
        json={
            "title": "Review denial packet",
            "description": "Local review only.",
            "category": "claim",
            "priority": "high",
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["task_id"].startswith("omt-")
    assert created["local_only"] is True
    assert created["external_action_performed"] is False
    assert created["softdent_writeback_performed"] is False
    assert created["status"] == "open"

    list_response = client.get("/api/hal9000/office-manager/tasks", auth=office_manager_auth())
    assert list_response.status_code == 200
    listed = list_response.json()
    assert listed["submission_status"] == "not_submitted"
    assert listed["total_count"] >= 1

    update_response = client.patch(
        f"/api/hal9000/office-manager/tasks/{created['task_id']}",
        auth=office_manager_auth(),
        json={"status": "in_progress"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "in_progress"

    metrics_response = client.get("/api/hal9000/office-manager/tasks/metrics", auth=office_manager_auth())
    assert metrics_response.status_code == 200
    metrics = metrics_response.json()
    assert metrics["in_progress_count"] >= 1
    assert metrics["local_only"] is True


def test_office_manager_task_update_missing_returns_404() -> None:
    response = client.patch(
        "/api/hal9000/office-manager/tasks/omt-missing",
        auth=office_manager_auth(),
        json={"status": "completed"},
    )
    assert response.status_code == 404
