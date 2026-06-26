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
            "username": "operator_full",
            "display_name": "Operator Full",
            "password": "full-password",
            "roles": [
                "dashboard:read",
                "hal:operator",
                "softdent:read",
                "softdent:patient:read",
                "softdent:clinical:read",
                "softdent:ledger:read",
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


@pytest.fixture(autouse=True)
def _runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime_dir = os.path.join(os.path.dirname(__file__), ".softdent_draft_routes_runtime", uuid4().hex)
    os.environ["APP_AUTH_USERS_JSON"] = TEST_AUTH_USERS_JSON
    os.environ["HAL_ALLOWED_BASE_PATH"] = runtime_dir
    os.environ["HAL_SQLITE_PATH"] = os.path.join(runtime_dir, "hal_test.sqlite3")
    clear_user_registry_cache()
    monkeypatch.setattr(
        financial_tools,
        "load_softdent_claim_rows",
        lambda: [
            {
                "PatientName": "John Doe",
                "ClaimId": "CLM-1001",
                "ClaimStatus": "Denied",
                "Payer": "Delta Dental",
                "Procedure": "Crown buildup",
                "ServiceDate": "2026-06-01",
                "DenialReason": "Additional narrative requested by payer",
            }
        ],
    )
    monkeypatch.setattr(
        financial_tools,
        "load_softdent_clinical_note_rows",
        lambda: [
            {
                "PatientName": "John Doe",
                "NoteId": "NOTE-1",
                "ClinicalNote": "Fractured cusp documented.",
            }
        ],
    )
    monkeypatch.setattr(financial_tools, "load_softdent_ar_rows", lambda: [])


def test_softdent_drafts_route_requires_softdent_roles() -> None:
    denied = client.post(
        "/api/hal9000/softdent-drafts",
        auth=("operator_only", "operator-password"),
        json={
            "patient_query": "Patient John Doe claim status",
            "draft_type": "internal_patient_summary",
        },
    )
    assert denied.status_code == 403


def test_softdent_drafts_route_returns_review_only_artifact() -> None:
    response = client.post(
        "/api/hal9000/softdent-drafts",
        auth=("operator_full", "full-password"),
        json={
            "patient_query": "Patient John Doe claim status",
            "draft_type": "insurance_narrative_proposal",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["patient_label"] == "John Doe"
    assert payload["review_required"] is True
    assert payload["external_action_performed"] is False
    assert "Draft only" in payload["body"]
    assert "Not submitted" in payload["body"]
    assert "Not written to SoftDent" in payload["body"]


def test_clinical_draft_route_requires_clinical_role() -> None:
    limited_user_json = json.dumps(
        [
            {
                "username": "operator_no_clinical",
                "display_name": "Operator No Clinical",
                "password": "no-clinical-password",
                "roles": [
                    "dashboard:read",
                    "hal:operator",
                    "softdent:read",
                    "softdent:patient:read",
                    "softdent:narrative:draft",
                ],
            }
        ]
    )
    os.environ["APP_AUTH_USERS_JSON"] = limited_user_json
    clear_user_registry_cache()

    response = client.post(
        "/api/hal9000/softdent-drafts",
        auth=("operator_no_clinical", "no-clinical-password"),
        json={
            "patient_query": "Patient John Doe claim status",
            "draft_type": "clinical_note_proposal",
        },
    )
    assert response.status_code == 403
