from __future__ import annotations

import os
from uuid import uuid4

import pytest

import app.hal.financial_tools as financial_tools
from app.hal.softdent_draft_models import SoftDentDraftRequest
from app.hal.softdent_draft_service import DRAFT_DISCLAIMER, create_softdent_draft
from app.hal.softdent_read_broker import (
    SOFTDENT_CLINICAL_READ,
    SOFTDENT_LEDGER_READ,
    SOFTDENT_NARRATIVE_DRAFT,
    SOFTDENT_PATIENT_READ,
    SOFTDENT_READ,
    SoftDentAccessError,
)
from app.hal.softdent_read_models import MISSING_SOFTDENT_AR

DRAFT_TYPES = [
    "clinical_note_proposal",
    "insurance_narrative_proposal",
    "claim_follow_up_checklist",
    "missing_document_checklist",
    "payer_appeal_prep_summary",
    "staff_task_recommendation",
    "internal_patient_summary",
]

FULL_ROLES = {
    SOFTDENT_READ,
    SOFTDENT_PATIENT_READ,
    SOFTDENT_CLINICAL_READ,
    SOFTDENT_LEDGER_READ,
    SOFTDENT_NARRATIVE_DRAFT,
}


@pytest.fixture(autouse=True)
def _runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime_dir = os.path.join(os.path.dirname(__file__), ".softdent_draft_service_runtime", uuid4().hex)
    os.environ["HAL_ALLOWED_BASE_PATH"] = runtime_dir
    os.environ["HAL_SQLITE_PATH"] = os.path.join(runtime_dir, "hal_test.sqlite3")
    _patch_exports(monkeypatch)


def _patch_exports(monkeypatch: pytest.MonkeyPatch) -> None:
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
                "ClaimAmount": 915.4,
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
                "NoteDate": "2026-06-01",
                "Procedure": "Crown buildup",
                "ClinicalNote": "Patient has fractured cusp with recurrent decay and documented cold sensitivity.",
            }
        ],
    )
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


@pytest.mark.parametrize("draft_type", DRAFT_TYPES)
def test_authorized_user_can_generate_each_draft_type(draft_type: str) -> None:
    include_clinical = draft_type != "claim_follow_up_checklist"
    artifact = create_softdent_draft(
        SoftDentDraftRequest(
            patient_query="Patient John Doe claim status",
            draft_type=draft_type,  # type: ignore[arg-type]
            include_clinical_context=include_clinical,
        ),
        actor="hal_operator",
        roles=FULL_ROLES,
    )
    assert artifact.draft_type == draft_type
    assert artifact.patient_label == "John Doe"
    assert artifact.review_required is True
    assert artifact.external_action_performed is False
    assert "Draft only" in artifact.body
    assert "Requires human review" in artifact.body
    assert "Not submitted" in artifact.body
    assert "Not written to SoftDent" in artifact.body
    assert DRAFT_DISCLAIMER in artifact.body


def test_operator_only_roles_cannot_generate_patient_draft() -> None:
    with pytest.raises(SoftDentAccessError):
        create_softdent_draft(
            SoftDentDraftRequest(
                patient_query="Patient John Doe claim status",
                draft_type="internal_patient_summary",
            ),
            actor="operator_only",
            roles={"hal:operator"},
        )


def test_clinical_note_proposal_requires_clinical_read_role() -> None:
    roles = {SOFTDENT_READ, SOFTDENT_PATIENT_READ, SOFTDENT_NARRATIVE_DRAFT}
    with pytest.raises(SoftDentAccessError):
        create_softdent_draft(
            SoftDentDraftRequest(
                patient_query="Patient John Doe claim status",
                draft_type="clinical_note_proposal",
            ),
            actor="hal_operator",
            roles=roles,
        )


def test_ledger_context_requires_ledger_read_role() -> None:
    roles = {SOFTDENT_READ, SOFTDENT_PATIENT_READ, SOFTDENT_NARRATIVE_DRAFT, SOFTDENT_CLINICAL_READ}
    with pytest.raises(SoftDentAccessError):
        create_softdent_draft(
            SoftDentDraftRequest(
                patient_query="Patient John Doe claim status",
                draft_type="internal_patient_summary",
                include_ledger_context=True,
            ),
            actor="hal_operator",
            roles=roles,
        )


def test_missing_softdent_ar_remains_unavailable_not_zero() -> None:
    artifact = create_softdent_draft(
        SoftDentDraftRequest(
            patient_query="Patient John Doe claim status",
            draft_type="staff_task_recommendation",
            include_ledger_context=True,
        ),
        actor="hal_operator",
        roles=FULL_ROLES,
    )
    assert MISSING_SOFTDENT_AR in artifact.missing_data_codes
    assert "$0.00" not in artifact.body
    assert "do not state a balance or $0" in " ".join(artifact.limitations).lower()


def test_drafts_use_broker_facts_not_raw_rows() -> None:
    artifact = create_softdent_draft(
        SoftDentDraftRequest(
            patient_query="Patient John Doe claim status",
            draft_type="internal_patient_summary",
        ),
        actor="hal_operator",
        roles=FULL_ROLES,
    )
    combined = f"{artifact.body} {' '.join(artifact.source_fact_refs)}"
    assert "PatientName,MRN,ClaimId" not in combined
    assert any(ref.startswith("claim:") for ref in artifact.source_fact_refs)
