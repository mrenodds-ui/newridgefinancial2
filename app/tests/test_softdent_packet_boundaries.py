from __future__ import annotations

import os
from uuid import uuid4

import pytest

from app.hal.audit import get_recent_softdent_packet_audits, record_softdent_packet_audit
from app.hal.softdent_draft_models import SoftDentDraftArtifact
from app.hal.softdent_packet_models import SoftDentLocalPacketRequest
from app.hal.softdent_packet_service import create_softdent_local_packet
from app.hal.softdent_read_broker import (
    SOFTDENT_NARRATIVE_DRAFT,
    SOFTDENT_PATIENT_READ,
    SOFTDENT_READ,
)

FORBIDDEN_COMPLETION_PHRASES = (
    "was submitted",
    "sent to payer",
    "faxed to",
    "uploaded to",
    "gateway action was completed",
    "updated softdent",
    "writeback completed",
)


@pytest.fixture(autouse=True)
def _runtime() -> None:
    runtime_dir = os.path.join(os.path.dirname(__file__), ".softdent_packet_boundaries_runtime", uuid4().hex)
    os.environ["HAL_ALLOWED_BASE_PATH"] = runtime_dir
    os.environ["HAL_SQLITE_PATH"] = os.path.join(runtime_dir, "hal_test.sqlite3")


def _valid_attestation() -> dict:
    return {
        "approved_by": "billing_lead",
        "approval_note": "Approved for internal office use only.",
        "attestation_checked": True,
        "acknowledged_local_only": True,
        "acknowledged_not_submitted": True,
        "acknowledged_no_softdent_writeback": True,
        "acknowledged_no_external_delivery": True,
    }


def _sample_draft() -> SoftDentDraftArtifact:
    return SoftDentDraftArtifact(
        draft_id="sdd-boundary123",
        draft_type="payer_appeal_prep_summary",
        patient_label="John Doe",
        title="Appeal prep for John Doe",
        body="Draft only. Requires human review before any office action.",
        checklist_items=["Confirm payer appeal rules."],
        source_fact_refs=["claim:CLM-1001", "clinical_note:NOTE-1"],
        missing_data_codes=["missing_softdent_ar"],
        limitations=["Draft for review only."],
        review_required=True,
        external_action_performed=False,
    )


def test_packet_text_states_local_internal_not_submitted_no_external_action() -> None:
    from app.hal.softdent_packet_models import SoftDentPacketApprovalAttestation

    packet = create_softdent_local_packet(
        SoftDentLocalPacketRequest(
            draft_artifact=_sample_draft(),
            packet_type="appeal_prep_packet",
        ),
        actor="hal_operator",
        roles={SOFTDENT_READ, SOFTDENT_PATIENT_READ, SOFTDENT_NARRATIVE_DRAFT},
        approval_attestation=SoftDentPacketApprovalAttestation(**_valid_attestation()),
    )
    lowered = packet.body.lower()
    assert "local only" in lowered
    assert "approved for internal office use" in lowered
    assert "not submitted" in lowered
    assert "not written to softdent" in lowered
    assert "no email, fax, upload, or gateway/e-services action was performed" in lowered
    for phrase in FORBIDDEN_COMPLETION_PHRASES:
        assert phrase not in lowered


def test_packet_audit_rejects_external_write_or_submitted_status() -> None:
    with pytest.raises(ValueError, match="external action"):
        record_softdent_packet_audit(
            actor="hal_operator",
            roles_used=[SOFTDENT_READ],
            packet_type="appeal_prep_packet",
            source_draft_id="sdd-boundary123",
            packet_id="sdp-test",
            external_action_performed=True,
        )
    with pytest.raises(ValueError, match="writeback"):
        record_softdent_packet_audit(
            actor="hal_operator",
            roles_used=[SOFTDENT_READ],
            packet_type="appeal_prep_packet",
            source_draft_id="sdd-boundary123",
            packet_id="sdp-test",
            softdent_writeback_performed=True,
        )
    with pytest.raises(ValueError, match="submission_status"):
        record_softdent_packet_audit(
            actor="hal_operator",
            roles_used=[SOFTDENT_READ],
            packet_type="appeal_prep_packet",
            source_draft_id="sdd-boundary123",
            packet_id="sdp-test",
            submission_status="submitted",
        )


def test_packet_audit_records_bounded_metadata() -> None:
    from app.hal.softdent_packet_models import SoftDentPacketApprovalAttestation

    packet = create_softdent_local_packet(
        SoftDentLocalPacketRequest(
            draft_artifact=_sample_draft(),
            packet_type="appeal_prep_packet",
        ),
        actor="hal_operator",
        roles={SOFTDENT_READ, SOFTDENT_PATIENT_READ, SOFTDENT_NARRATIVE_DRAFT},
        approval_attestation=SoftDentPacketApprovalAttestation(**_valid_attestation()),
    )
    audit = get_recent_softdent_packet_audits(limit=1)[0]
    assert audit["packet_id"] == packet.packet_id
    assert audit["source_draft_id"] == packet.source_draft_id
    assert audit["actor"] == "hal_operator"
    assert audit["packet_type"] == "appeal_prep_packet"
    assert audit["claim_ids"] == ["CLM-1001"]
    assert audit["clinical_note_ids"] == ["NOTE-1"]
    assert audit["source_fact_refs"] == packet.source_fact_refs
    assert audit["missing_data_codes"] == packet.missing_data_codes
    assert audit["approval_attestation"]["approved_by"] == "billing_lead"
    assert audit["submission_status"] == "not_submitted"
    assert audit["external_action_performed"] is False
    assert audit["softdent_writeback_performed"] is False
    assert audit["local_only"] is True
    assert "Draft only" not in str(audit)


def test_no_export_submission_writeback_clients_called(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.hal.softdent_packet_models import SoftDentPacketApprovalAttestation

    def _blocked(*args, **kwargs):
        raise AssertionError("External write/submission client must not be called in Phase 3 packet flow")

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

    packet = create_softdent_local_packet(
        SoftDentLocalPacketRequest(
            draft_artifact=_sample_draft(),
            packet_type="copied_draft_text_packet",
        ),
        actor="hal_operator",
        roles={SOFTDENT_READ, SOFTDENT_PATIENT_READ, SOFTDENT_NARRATIVE_DRAFT},
        approval_attestation=SoftDentPacketApprovalAttestation(**_valid_attestation()),
    )
    assert packet.external_action_performed is False
    assert packet.softdent_writeback_performed is False
