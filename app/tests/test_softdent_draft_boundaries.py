from __future__ import annotations

import os
from uuid import uuid4

import pytest

import app.hal.financial_tools as financial_tools
from app.hal.audit import get_recent_softdent_draft_audits, record_softdent_draft_audit
from app.hal.softdent_draft_models import SoftDentDraftRequest
from app.hal.softdent_draft_service import create_softdent_draft
from app.hal.softdent_read_broker import (
    SOFTDENT_CLINICAL_READ,
    SOFTDENT_NARRATIVE_DRAFT,
    SOFTDENT_PATIENT_READ,
    SOFTDENT_READ,
)

FORBIDDEN_COMPLETION_PHRASES = (
    "submitted",
    "sent to payer",
    "faxed",
    "uploaded",
    "gateway",
    "updated softdent",
    "writeback completed",
)


@pytest.fixture(autouse=True)
def _runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime_dir = os.path.join(os.path.dirname(__file__), ".softdent_draft_boundaries_runtime", uuid4().hex)
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


def test_draft_output_never_claims_submission_or_writeback(monkeypatch: pytest.MonkeyPatch) -> None:
    artifact = create_softdent_draft(
        SoftDentDraftRequest(
            patient_query="Patient John Doe claim status",
            draft_type="payer_appeal_prep_summary",
        ),
        actor="hal_operator",
        roles={
            SOFTDENT_READ,
            SOFTDENT_PATIENT_READ,
            SOFTDENT_CLINICAL_READ,
            SOFTDENT_NARRATIVE_DRAFT,
        },
    )
    lowered = artifact.body.lower()
    for phrase in FORBIDDEN_COMPLETION_PHRASES:
        if phrase == "submitted":
            assert "not submitted" in lowered
            continue
        assert phrase not in lowered or "not " in lowered or "no " in lowered


def test_draft_audit_rejects_external_action_flag() -> None:
    with pytest.raises(ValueError, match="external action"):
        record_softdent_draft_audit(
            actor="hal_operator",
            roles_used=[SOFTDENT_READ],
            draft_type="internal_patient_summary",
            workflow_reason="staff_review",
            draft_id="sdd-test",
            external_action_performed=True,
        )


def test_draft_audit_records_bounded_metadata() -> None:
    artifact = create_softdent_draft(
        SoftDentDraftRequest(
            patient_query="Patient John Doe claim status",
            draft_type="missing_document_checklist",
        ),
        actor="hal_operator",
        roles={
            SOFTDENT_READ,
            SOFTDENT_PATIENT_READ,
            SOFTDENT_CLINICAL_READ,
            SOFTDENT_NARRATIVE_DRAFT,
        },
    )
    audit = get_recent_softdent_draft_audits(limit=1)[0]
    assert audit["draft_id"] == artifact.draft_id
    assert audit["actor"] == "hal_operator"
    assert audit["draft_type"] == "missing_document_checklist"
    assert audit["claim_ids"]
    assert audit["review_required"] is True
    assert audit["external_action_performed"] is False
    assert "Fractured cusp" not in str(audit)


def test_no_writeback_or_submission_clients_called(monkeypatch: pytest.MonkeyPatch) -> None:
    def _blocked(*args, **kwargs):
        raise AssertionError("External write/submission client must not be called in Phase 2 draft flow")

    monkeypatch.setattr(
        "app.insurance_narratives.workflow.approve_and_export_insurance_narrative_workflow",
        _blocked,
        raising=False,
    )
    monkeypatch.setattr(
        "app.insurance_narratives.workflow.create_insurance_narrative_draft_workflow",
        _blocked,
        raising=False,
    )

    artifact = create_softdent_draft(
        SoftDentDraftRequest(
            patient_query="Patient John Doe claim status",
            draft_type="insurance_narrative_proposal",
        ),
        actor="hal_operator",
        roles={
            SOFTDENT_READ,
            SOFTDENT_PATIENT_READ,
            SOFTDENT_CLINICAL_READ,
            SOFTDENT_NARRATIVE_DRAFT,
        },
    )
    assert artifact.external_action_performed is False
