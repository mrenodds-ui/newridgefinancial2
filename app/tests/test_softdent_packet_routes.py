from __future__ import annotations

import json
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.auth import clear_user_registry_cache
from app.main import app

TEST_AUTH_USERS_JSON = json.dumps(
    [
        {
            "username": "operator_full",
            "display_name": "Operator Full",
            "password": "full-password",
            "roles": [
                "dashboard:read",
                "hal:operator",
                "softdent:read",
                "softdent:patient:read",
                "softdent:narrative:draft",
            ],
        },
        {
            "username": "operator_only",
            "display_name": "Operator Only",
            "password": "operator-password",
            "roles": ["dashboard:read", "hal:operator"],
        },
    ]
)

os.environ["APP_AUTH_USERS_JSON"] = TEST_AUTH_USERS_JSON
client = TestClient(app)


def _draft_payload() -> dict:
    return {
        "draft_id": "sdd-route123456",
        "draft_type": "insurance_narrative_proposal",
        "patient_label": "John Doe",
        "title": "Insurance narrative proposal for John Doe",
        "body": "Draft only. Requires human review before any office action.",
        "checklist_items": ["Verify payer details."],
        "source_fact_refs": ["claim:CLM-1001"],
        "missing_data_codes": ["missing_softdent_procedures_export"],
        "limitations": ["Draft for review only."],
        "review_required": True,
        "external_action_performed": False,
    }


def _attestation_payload(**overrides: object) -> dict:
    payload = {
        "approved_by": "billing_lead",
        "approval_note": "Approved for internal office use only.",
        "attestation_checked": True,
        "acknowledged_local_only": True,
        "acknowledged_not_submitted": True,
        "acknowledged_no_softdent_writeback": True,
        "acknowledged_no_external_delivery": True,
    }
    payload.update(overrides)
    return payload


@pytest.fixture(autouse=True)
def _runtime() -> None:
    runtime_dir = os.path.join(os.path.dirname(__file__), ".softdent_packet_routes_runtime", uuid4().hex)
    os.environ["APP_AUTH_USERS_JSON"] = TEST_AUTH_USERS_JSON
    os.environ["HAL_ALLOWED_BASE_PATH"] = runtime_dir
    os.environ["HAL_SQLITE_PATH"] = os.path.join(runtime_dir, "hal_test.sqlite3")
    clear_user_registry_cache()


def test_softdent_local_packets_route_requires_softdent_roles() -> None:
    response = client.post(
        "/api/hal9000/softdent-local-packets",
        auth=("operator_only", "operator-password"),
        json={
            "draft_artifact": _draft_payload(),
            "packet_type": "approved_narrative_packet",
            "approval_attestation": _attestation_payload(),
        },
    )
    assert response.status_code == 403


def test_softdent_local_packets_route_returns_local_only_packet() -> None:
    response = client.post(
        "/api/hal9000/softdent-local-packets",
        auth=("operator_full", "full-password"),
        json={
            "draft_artifact": _draft_payload(),
            "packet_type": "approved_narrative_packet",
            "approval_attestation": _attestation_payload(),
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["submission_status"] == "not_submitted"
    assert payload["external_action_performed"] is False
    assert payload["softdent_writeback_performed"] is False
    assert payload["local_only"] is True
    assert "Local only" in payload["body"]
    assert "Approved for internal office use" in payload["body"]
    assert "Not submitted" in payload["body"]
    assert "Not written to SoftDent" in payload["body"]


def test_softdent_local_packets_route_rejects_missing_attestation() -> None:
    response = client.post(
        "/api/hal9000/softdent-local-packets",
        auth=("operator_full", "full-password"),
        json={
            "draft_artifact": _draft_payload(),
            "packet_type": "approved_narrative_packet",
            "approval_attestation": _attestation_payload(attestation_checked=False),
        },
    )
    assert response.status_code == 400
