from __future__ import annotations

import os
from uuid import uuid4

import pytest

import app.hal.financial_tools as financial_tools
from app.hal.audit import get_recent_softdent_read_audits, record_softdent_read_audit
from app.hal.softdent_read_broker import (
    SOFTDENT_CLINICAL_READ,
    SOFTDENT_PATIENT_READ,
    SOFTDENT_READ,
    SoftDentReadBroker,
)
from app.hal.softdent_read_models import MISSING_SOFTDENT_AR


@pytest.fixture(autouse=True)
def _runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime_dir = os.path.join(os.path.dirname(__file__), ".softdent_audit_runtime", uuid4().hex)
    os.environ["HAL_ALLOWED_BASE_PATH"] = runtime_dir
    os.environ["HAL_SQLITE_PATH"] = os.path.join(runtime_dir, "hal_test.sqlite3")

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


def test_record_softdent_read_audit_persists_bounded_fields() -> None:
    entry = record_softdent_read_audit(
        actor="hal_operator",
        roles_used=[SOFTDENT_READ, SOFTDENT_PATIENT_READ],
        workflow_reason="patient_context",
        response_mode="answer",
        patient_display_name="John Doe",
        patient_ref_hash="sd-abc123",
        chart_ref_hash="sd-abc123",
        claim_ids=["CLM-1001"],
        clinical_note_ids=["NOTE-1"],
        ledger_record_ids=[],
        source_adapter="exports",
        source_metadata=[{"source_adapter": "exports", "source_name": "softdent_claims_export.csv"}],
        missing_data_codes=[MISSING_SOFTDENT_AR],
        external_action_performed=False,
    )

    stored = get_recent_softdent_read_audits(limit=1)[0]
    assert stored["event_id"] == entry["event_id"]
    assert stored["actor"] == "hal_operator"
    assert stored["roles_used"] == [SOFTDENT_READ, SOFTDENT_PATIENT_READ]
    assert stored["claim_ids"] == ["CLM-1001"]
    assert stored["clinical_note_ids"] == ["NOTE-1"]
    assert stored["missing_data_codes"] == [MISSING_SOFTDENT_AR]
    assert stored["external_action_performed"] is False
    assert "Fractured cusp" not in str(stored)


def test_broker_patient_context_writes_record_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    broker = SoftDentReadBroker()
    roles = {SOFTDENT_READ, SOFTDENT_PATIENT_READ, SOFTDENT_CLINICAL_READ}

    broker.get_legacy_patient_context(
        "Patient John Doe claim status",
        actor="hal_operator",
        roles=roles,
    )

    audits = get_recent_softdent_read_audits(limit=1)
    assert audits
    audit = audits[0]
    assert audit["actor"] == "hal_operator"
    assert audit["patient_display_name"] == "John Doe"
    assert audit["claim_ids"]
    assert audit["external_action_performed"] is False


def test_external_action_flag_rejected_in_phase_one() -> None:
    with pytest.raises(ValueError, match="external action"):
        record_softdent_read_audit(
            actor="hal_operator",
            roles_used=[SOFTDENT_READ],
            workflow_reason="patient_context",
            response_mode="answer",
            external_action_performed=True,
        )
