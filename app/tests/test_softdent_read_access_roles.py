from __future__ import annotations

import json
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.hal.financial_tools as financial_tools
from app.auth import clear_user_registry_cache
from app.hal.softdent_read_broker import (
    SOFTDENT_CLINICAL_READ,
    SOFTDENT_LEDGER_READ,
    SOFTDENT_NARRATIVE_DRAFT,
    SOFTDENT_PATIENT_READ,
    SOFTDENT_READ,
    SoftDentAccessError,
    SoftDentReadBroker,
)
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
    runtime_dir = os.path.join(os.path.dirname(__file__), ".softdent_roles_runtime", uuid4().hex)
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


def test_hal_operator_alone_cannot_read_patient_facts_via_broker() -> None:
    broker = SoftDentReadBroker()
    payload = broker.get_legacy_patient_context(
        "Patient John Doe claim status",
        actor="operator_only",
        roles={"hal:operator"},
    )
    assert payload["matched"] is False
    assert payload["access_denied"] is True


def test_softdent_patient_read_allows_patient_name_in_legacy_context() -> None:
    broker = SoftDentReadBroker()
    payload = broker.get_legacy_patient_context(
        "Patient John Doe claim status",
        actor="operator_full",
        roles={SOFTDENT_READ, SOFTDENT_PATIENT_READ},
    )
    assert payload["matched"] is True
    assert payload["summary_fields"]["patient_name"] == "John Doe"


def test_clinical_role_required_for_note_summaries() -> None:
    broker = SoftDentReadBroker()
    with pytest.raises(SoftDentAccessError):
        broker.get_clinical_note_summaries(
            "John Doe",
            actor="operator_full",
            roles={SOFTDENT_READ, SOFTDENT_PATIENT_READ},
        )


def test_ledger_role_required_for_ledger_context() -> None:
    broker = SoftDentReadBroker()
    with pytest.raises(SoftDentAccessError):
        broker.get_ledger_context(
            "John Doe",
            actor="operator_full",
            roles={SOFTDENT_READ, SOFTDENT_PATIENT_READ},
        )


def test_patient_dossier_route_requires_softdent_patient_read() -> None:
    denied = client.post(
        "/api/hal9000/patient-dossier",
        auth=("operator_only", "operator-password"),
        json={"question": "Patient John Doe claim lookup."},
    )
    assert denied.status_code == 403

    allowed = client.post(
        "/api/hal9000/patient-dossier",
        auth=("operator_full", "full-password"),
        json={"question": "Patient John Doe claim lookup."},
    )
    assert allowed.status_code == 200
    assert "John Doe" in allowed.json()["summary"]


def test_insurance_narrative_route_requires_narrative_draft_role() -> None:
    denied = client.post(
        "/api/hal9000/insurance-narrative",
        auth=("operator_only", "operator-password"),
        json={"question": "Patient John Doe needs an insurance narrative."},
    )
    assert denied.status_code == 403

    allowed = client.post(
        "/api/hal9000/insurance-narrative",
        auth=("operator_full", "full-password"),
        json={"question": "Patient John Doe needs an insurance narrative."},
    )
    assert allowed.status_code == 200
    assert allowed.json()["matched"] is True
