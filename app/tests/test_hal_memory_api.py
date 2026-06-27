"""HTTP tests for governed HAL knowledge-memory review APIs."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.auth import clear_user_registry_cache
from app.hal.knowledge_memory import APPROVED_STATUS
from app.main import app


TEST_AUTH_USERS_JSON = json.dumps(
    [
        {
            "username": "admin",
            "display_name": "Administrator",
            "password": "password",
            "roles": ["dashboard:read", "hal:operator", "admin"],
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

SAFE_MEMORY_TEXT = (
    "Daily huddle notes should stay local and require staff review before operational use."
)


@pytest.fixture()
def isolated_hal_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HAL_ALLOWED_BASE_PATH", str(tmp_path))
    db_path = tmp_path / "hal_memory_api_test.sqlite3"
    monkeypatch.setenv("HAL_SQLITE_PATH", str(db_path))
    return db_path


@pytest.fixture()
def stash_snapshot() -> list[str]:
    result = subprocess.run(
        ["git", "stash", "list"],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.splitlines()


def setup_function() -> None:
    runtime_dir = Path(__file__).resolve().parent / ".hal_memory_api_runtime" / uuid4().hex
    os.environ["APP_AUTH_USERS_JSON"] = TEST_AUTH_USERS_JSON
    os.environ["HAL_ALLOWED_BASE_PATH"] = str(runtime_dir)
    os.environ["HAL_SQLITE_PATH"] = str(runtime_dir / "hal_test.sqlite3")
    clear_user_registry_cache()


def admin_auth() -> tuple[str, str]:
    return ("admin", "password")


def operator_auth() -> tuple[str, str]:
    return ("hal_operator", "hal-password")


def test_memory_api_unauthenticated_blocked(isolated_hal_storage: Path) -> None:
    list_response = client.get("/api/hal9000/knowledge/memories")
    propose_response = client.post(
        "/api/hal9000/knowledge/memories",
        json={"text": SAFE_MEMORY_TEXT},
    )
    approve_response = client.post("/api/hal9000/knowledge/memories/office-test/approve")
    revoke_response = client.post("/api/hal9000/knowledge/memories/office-test/revoke")

    assert list_response.status_code == 401
    assert propose_response.status_code == 401
    assert approve_response.status_code == 401
    assert revoke_response.status_code == 401


def test_memory_api_operator_cannot_mutate(isolated_hal_storage: Path) -> None:
    list_response = client.get("/api/hal9000/knowledge/memories", auth=operator_auth())
    propose_response = client.post(
        "/api/hal9000/knowledge/memories",
        auth=operator_auth(),
        json={"text": SAFE_MEMORY_TEXT},
    )
    approve_response = client.post(
        "/api/hal9000/knowledge/memories/office-test/approve",
        auth=operator_auth(),
        json={"note": "Should not approve."},
    )
    revoke_response = client.post(
        "/api/hal9000/knowledge/memories/office-test/revoke",
        auth=operator_auth(),
        json={"note": "Should not revoke."},
    )

    assert list_response.status_code == 403
    assert propose_response.status_code == 403
    assert approve_response.status_code == 403
    assert revoke_response.status_code == 403


def test_memory_api_admin_propose_list_approve_revoke(
    isolated_hal_storage: Path,
    stash_snapshot: list[str],
) -> None:
    propose_response = client.post(
        "/api/hal9000/knowledge/memories",
        auth=admin_auth(),
        json={
            "text": SAFE_MEMORY_TEXT,
            "category": "operator_playbooks",
            "source": "memory API test",
        },
    )
    assert propose_response.status_code == 200
    proposed = propose_response.json()
    memory_id = proposed["memory_id"]
    assert proposed["status"] == "proposed"
    assert proposed["proposed_by"] == "admin"

    list_response = client.get(
        "/api/hal9000/knowledge/memories?status=proposed",
        auth=admin_auth(),
    )
    assert list_response.status_code == 200
    listed = list_response.json()
    assert listed["count"] == 1
    assert listed["items"][0]["memory_id"] == memory_id

    approve_response = client.post(
        f"/api/hal9000/knowledge/memories/{memory_id}/approve",
        auth=admin_auth(),
        json={"note": "Approved for governed retrieval."},
    )
    assert approve_response.status_code == 200
    approved = approve_response.json()
    assert approved["status"] == APPROVED_STATUS
    assert approved["approved_by"] == "admin"

    revoke_response = client.post(
        f"/api/hal9000/knowledge/memories/{memory_id}/revoke",
        auth=admin_auth(),
        json={"note": "Revoked after review."},
    )
    assert revoke_response.status_code == 200
    revoked = revoke_response.json()
    assert revoked["status"] == "revoked"

    after_stash = subprocess.run(
        ["git", "stash", "list"],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    assert after_stash == stash_snapshot


def test_memory_api_rejects_unsafe_proposal_text(isolated_hal_storage: Path) -> None:
    phi_response = client.post(
        "/api/hal9000/knowledge/memories",
        auth=admin_auth(),
        json={"text": "Patient Jane Roe should be called after treatment."},
    )
    gateway_response = client.post(
        "/api/hal9000/knowledge/memories",
        auth=admin_auth(),
        json={"text": "Gateway submit is allowed for operators."},
    )

    assert phi_response.status_code == 400
    assert gateway_response.status_code == 400


def test_memory_api_approved_memory_preserves_guardrails(isolated_hal_storage: Path) -> None:
    propose_response = client.post(
        "/api/hal9000/knowledge/memories",
        auth=admin_auth(),
        json={"text": SAFE_MEMORY_TEXT, "category": "known_workflows"},
    )
    memory_id = propose_response.json()["memory_id"]

    approve_response = client.post(
        f"/api/hal9000/knowledge/memories/{memory_id}/approve",
        auth=admin_auth(),
        json={},
    )
    assert approve_response.status_code == 200
    approved = approve_response.json()

    assert approved["scope"] == "hal"
    assert approved["sensitivity_level"] == "internal_safe"
    assert approved["status"] == APPROVED_STATUS
    assert approved["must_not_override"] == [
        "guardrails",
        "auth",
        "runtime_status",
        "hal_ask_request",
    ]
