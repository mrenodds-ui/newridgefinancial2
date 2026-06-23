import builtins
import json
import os
import types

from fastapi.testclient import TestClient

from app.auth import clear_user_registry_cache
from app.hardware_routes import handle_authenticated_hardware_execution
from app.main import app


TEST_AUTH_USERS_JSON = json.dumps(
    [
        {
            "username": "admin",
            "display_name": "Administrator",
            "password": "password",
            "roles": ["dashboard:read", "hal:operator", "hal:index:refresh", "admin"],
        },
        {
            "username": "hal_operator",
            "display_name": "HAL Operator",
            "password": "hal-password",
            "roles": ["dashboard:read", "hal:operator"],
        },
    ]
)

os.environ["APP_AUTH_USERS_JSON"] = TEST_AUTH_USERS_JSON

client = TestClient(app)


def setup_function():
    os.environ["APP_AUTH_USERS_JSON"] = TEST_AUTH_USERS_JSON
    clear_user_registry_cache()


def basic_auth():
    return ("admin", "password")


def operator_auth():
    return ("hal_operator", "hal-password")


def test_hardware_executor_rejects_unconfirmed_payloads():
    result = handle_authenticated_hardware_execution(
        {
            "action_type": "SET_LUMINANCE",
            "target_value": 45,
            "human_review_required": True,
            "status": "pending_confirmation",
            "user_confirmed": False,
        }
    )

    assert result["status"] == "rejected"
    assert "confirmation flag" in str(result["error"])


def test_hardware_executor_invokes_write_on_valid_confirmation(monkeypatch):
    original_import = builtins.__import__

    class FakeMonitor:
        def __init__(self):
            self.applied_values = []

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def set_luminance(self, value):
            self.applied_values.append(value)

    fake_monitor = FakeMonitor()
    fake_module = types.SimpleNamespace(get_monitors=lambda: [fake_monitor])

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "monitorcontrol":
            return fake_module
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    result = handle_authenticated_hardware_execution(
        {
            "action_type": "SET_LUMINANCE",
            "target_value": 75,
            "human_review_required": True,
            "status": "pending_confirmation",
            "user_confirmed": True,
        }
    )

    assert result["status"] == "executed"
    assert result["applied_value"] == 75
    assert fake_monitor.applied_values == [75]


def test_hardware_executor_rejects_invalid_payload_shape():
    result = handle_authenticated_hardware_execution(
        {
            "action_type": "SET_LUMINANCE",
            "target_value": 175,
            "human_review_required": True,
            "status": "pending_confirmation",
            "user_confirmed": True,
        }
    )

    assert result["status"] == "failed"
    assert "validation failed" in str(result["error"])


def test_hardware_route_requires_admin_role():
    response = client.post(
        "/api/hardware/monitor-actions",
        auth=operator_auth(),
        json={
            "action_type": "SET_LUMINANCE",
            "target_value": 30,
            "human_review_required": True,
            "status": "pending_confirmation",
            "user_confirmed": True,
        },
    )

    assert response.status_code == 403
