from __future__ import annotations

import os
from uuid import uuid4

import pytest

import app.hal.financial_tools as financial_tools
from app.hal.softdent_read_broker import (
    SOFTDENT_CLINICAL_READ,
    SOFTDENT_LEDGER_READ,
    SOFTDENT_NARRATIVE_DRAFT,
    SOFTDENT_PATIENT_READ,
    SOFTDENT_READ,
    SoftDentAccessError,
    SoftDentReadBroker,
    SoftDentPatientQuery,
)
from app.hal.softdent_read_models import MISSING_SOFTDENT_AR


@pytest.fixture(autouse=True)
def _runtime_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime_dir = os.path.join(os.path.dirname(__file__), ".softdent_broker_runtime", uuid4().hex)
    os.environ["HAL_ALLOWED_BASE_PATH"] = runtime_dir
    os.environ["HAL_SQLITE_PATH"] = os.path.join(runtime_dir, "hal_test.sqlite3")


def _claim_rows() -> list[dict]:
    return [
        {
            "PatientName": "John Doe",
            "MRN": "778899",
            "ClaimId": "CLM-1001",
            "ClaimStatus": "Denied",
            "Payer": "Delta Dental",
            "Procedure": "Crown buildup",
            "ServiceDate": "2026-06-01",
            "DenialReason": "Additional narrative requested by payer",
            "ClaimAmount": 915.4,
        }
    ]


def _note_rows() -> list[dict]:
    return [
        {
            "PatientName": "John Doe",
            "MRN": "778899",
            "NoteId": "NOTE-1",
            "NoteDate": "2026-06-01",
            "Procedure": "Crown buildup",
            "ClinicalNote": "Patient has fractured cusp with recurrent decay and documented cold sensitivity.",
        }
    ]


def _patch_exports(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(financial_tools, "load_softdent_claim_rows", _claim_rows)
    monkeypatch.setattr(financial_tools, "load_softdent_clinical_note_rows", _note_rows)
    monkeypatch.setattr(financial_tools, "load_softdent_ar_rows", lambda: [])
    monkeypatch.setattr(
        financial_tools,
        "get_softdent_claim_source_status",
        lambda: {
            "available": True,
            "source_backend": "exports",
            "source_file": "softdent_claims_export.csv",
            "modified_at_utc": "2026-06-01T00:00:00+00:00",
        },
    )
    monkeypatch.setattr(
        financial_tools,
        "get_softdent_clinical_note_source_status",
        lambda: {
            "available": True,
            "source_backend": "exports",
            "source_file": "softdent_clinical_notes_export.csv",
            "modified_at_utc": "2026-06-01T00:00:00+00:00",
        },
    )


def test_authorized_patient_context_includes_name_and_claim_facts(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_exports(monkeypatch)
    broker = SoftDentReadBroker()
    roles = {SOFTDENT_READ, SOFTDENT_PATIENT_READ, SOFTDENT_CLINICAL_READ, SOFTDENT_LEDGER_READ}

    context = broker.get_patient_context(
        SoftDentPatientQuery(question="Patient John Doe claim status"),
        actor="hal_operator",
        roles=roles,
        write_audit=False,
    )

    assert context.matched is True
    assert context.display_name == "John Doe"
    assert context.claims[0].claim_id == "CLM-1001"
    assert context.claims[0].payer_name == "Delta Dental"
    assert context.clinical_notes
    assert context.source_metadata


def test_legacy_context_preserves_snippet_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_exports(monkeypatch)
    broker = SoftDentReadBroker()
    roles = {SOFTDENT_READ, SOFTDENT_PATIENT_READ}

    payload = broker.get_legacy_patient_context(
        "Patient John Doe needs claim help",
        actor="hal_operator",
        roles=roles,
    )

    assert payload["matched"] is True
    assert payload["summary_fields"]["patient_name"] == "John Doe"
    assert any(item["source_id"] == "softdent-patient-claims-dossier" for item in payload["snippets"])
    assert "Insurance narrative for John Doe." in payload["narrative"]


def test_operator_only_roles_return_access_denied_legacy_context(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_exports(monkeypatch)
    broker = SoftDentReadBroker()

    payload = broker.get_legacy_patient_context(
        "Patient John Doe claim status",
        actor="hal_operator",
        roles={"hal:operator"},
    )

    assert payload["matched"] is False
    assert payload["access_denied"] is True


def test_clinical_read_role_required_for_note_summaries(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_exports(monkeypatch)
    broker = SoftDentReadBroker()

    with pytest.raises(SoftDentAccessError):
        broker.get_clinical_note_summaries(
            "John Doe",
            actor="hal_operator",
            roles={SOFTDENT_READ, SOFTDENT_PATIENT_READ},
        )


def test_ledger_context_reports_missing_ar_not_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_exports(monkeypatch)
    broker = SoftDentReadBroker()
    roles = {SOFTDENT_READ, SOFTDENT_LEDGER_READ}

    ledger = broker.get_ledger_context("John Doe", actor="hal_operator", roles=roles, write_audit=False)

    assert ledger.available is False
    assert MISSING_SOFTDENT_AR in ledger.missing_data_codes
    assert ledger.patient_balance is None
    assert ledger.total_ar is None


def test_clinical_note_summary_is_bounded_and_rejects_bulk_markers(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_exports(monkeypatch)

    def bulk_note_rows() -> list[dict]:
        return [
            {
                "PatientName": "John Doe",
                "NoteId": "NOTE-BULK",
                "ClinicalNote": "full patient export with unrestricted database dump",
            }
        ]

    monkeypatch.setattr(financial_tools, "load_softdent_clinical_note_rows", bulk_note_rows)
    broker = SoftDentReadBroker()
    roles = {SOFTDENT_READ, SOFTDENT_CLINICAL_READ}

    notes = broker.get_clinical_note_summaries("John Doe", actor="hal_operator", roles=roles)
    assert notes == []


def test_narrative_source_facts_require_draft_role(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_exports(monkeypatch)
    broker = SoftDentReadBroker()

    with pytest.raises(SoftDentAccessError):
        broker.build_narrative_source_facts(
            "John Doe",
            "CLM-1001",
            actor="hal_operator",
            roles={SOFTDENT_READ, SOFTDENT_PATIENT_READ},
        )

    facts = broker.build_narrative_source_facts(
        "John Doe",
        "CLM-1001",
        actor="hal_operator",
        roles={SOFTDENT_READ, SOFTDENT_PATIENT_READ, SOFTDENT_NARRATIVE_DRAFT},
    )
    assert facts.patient_label == "John Doe"
    assert facts.claim_facts
    assert "nothing has been submitted" in " ".join(facts.limitations).lower()


def test_legacy_context_never_emits_raw_csv_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_exports(monkeypatch)
    broker = SoftDentReadBroker()
    roles = {SOFTDENT_READ, SOFTDENT_PATIENT_READ, SOFTDENT_CLINICAL_READ}

    payload = broker.get_legacy_patient_context(
        "Patient John Doe claim status",
        actor="hal_operator",
        roles=roles,
    )
    combined = json_dumps_safe(payload)

    assert "PatientName,MRN,ClaimId" not in combined
    assert "SSN" not in combined


def json_dumps_safe(payload: object) -> str:
    import json

    return json.dumps(payload)
