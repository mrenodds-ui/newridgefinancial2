from __future__ import annotations

import os
from uuid import uuid4

import pytest

from app.hal.audit import get_recent_softdent_packet_audits, record_softdent_packet_audit
from app.hal.softdent_draft_models import SoftDentDraftArtifact
from app.hal.softdent_packet_models import (
    SOFTDENT_PACKET_TYPES,
    SoftDentLocalPacketRequest,
    SoftDentPacketApprovalAttestation,
)
from app.hal.softdent_packet_service import PACKET_DISCLAIMER, create_softdent_local_packet
from app.hal.softdent_read_broker import (
    SOFTDENT_NARRATIVE_DRAFT,
    SOFTDENT_PATIENT_READ,
    SOFTDENT_READ,
    SoftDentAccessError,
)

FULL_ROLES = {
    SOFTDENT_READ,
    SOFTDENT_PATIENT_READ,
    SOFTDENT_NARRATIVE_DRAFT,
    "softdent:clinical:read",
}


@pytest.fixture(autouse=True)
def _runtime() -> None:
    runtime_dir = os.path.join(os.path.dirname(__file__), ".softdent_packet_service_runtime", uuid4().hex)
    os.environ["HAL_ALLOWED_BASE_PATH"] = runtime_dir
    os.environ["HAL_SQLITE_PATH"] = os.path.join(runtime_dir, "hal_test.sqlite3")


def _valid_attestation(**overrides: object) -> SoftDentPacketApprovalAttestation:
    payload = {
        "approved_by": "billing_lead",
        "approval_note": "Reviewed and approved for internal office use only.",
        "attestation_checked": True,
        "acknowledged_local_only": True,
        "acknowledged_not_submitted": True,
        "acknowledged_no_softdent_writeback": True,
        "acknowledged_no_external_delivery": True,
    }
    payload.update(overrides)
    return SoftDentPacketApprovalAttestation(**payload)


def _sample_draft(**overrides: object) -> SoftDentDraftArtifact:
    payload = {
        "draft_id": "sdd-test123456",
        "draft_type": "insurance_narrative_proposal",
        "patient_label": "John Doe",
        "title": "Insurance narrative proposal for John Doe",
        "body": "Draft only. Requires human review before any office action.",
        "checklist_items": ["Verify payer details."],
        "source_fact_refs": ["claim:CLM-1001", "clinical_note:NOTE-1"],
        "missing_data_codes": ["missing_softdent_procedures_export"],
        "limitations": ["Draft for review only."],
        "review_required": True,
        "external_action_performed": False,
    }
    payload.update(overrides)
    return SoftDentDraftArtifact(**payload)


@pytest.mark.parametrize("packet_type", sorted(SOFTDENT_PACKET_TYPES))
def test_local_packet_can_be_created_from_each_packet_type(packet_type: str) -> None:
    packet = create_softdent_local_packet(
        SoftDentLocalPacketRequest(draft_artifact=_sample_draft(), packet_type=packet_type),  # type: ignore[arg-type]
        actor="hal_operator",
        roles=FULL_ROLES,
        approval_attestation=_valid_attestation(),
    )
    assert packet.packet_type == packet_type
    assert packet.source_draft_id == "sdd-test123456"
    assert packet.submission_status == "not_submitted"
    assert packet.external_action_performed is False
    assert packet.softdent_writeback_performed is False
    assert packet.local_only is True
    assert PACKET_DISCLAIMER in packet.body


def test_packet_requires_phase2_draft_artifact() -> None:
    with pytest.raises(ValueError, match="draft_id"):
        create_softdent_local_packet(
            SoftDentLocalPacketRequest(
                draft_artifact=_sample_draft(draft_id=""),
                packet_type="approved_narrative_packet",
            ),
            actor="hal_operator",
            roles=FULL_ROLES,
            approval_attestation=_valid_attestation(),
        )


def test_missing_approval_attestation_flags_rejected() -> None:
    with pytest.raises(ValueError, match="attestation_checked"):
        create_softdent_local_packet(
            SoftDentLocalPacketRequest(
                draft_artifact=_sample_draft(),
                packet_type="approved_narrative_packet",
            ),
            actor="hal_operator",
            roles=FULL_ROLES,
            approval_attestation=_valid_attestation(attestation_checked=False),
        )


def test_operator_only_roles_cannot_create_packet() -> None:
    with pytest.raises(SoftDentAccessError):
        create_softdent_local_packet(
            SoftDentLocalPacketRequest(
                draft_artifact=_sample_draft(),
                packet_type="approved_narrative_packet",
            ),
            actor="operator_only",
            roles={"hal:operator"},
            approval_attestation=_valid_attestation(),
        )


def test_packet_preserves_source_fact_refs_and_missing_data_codes() -> None:
    packet = create_softdent_local_packet(
        SoftDentLocalPacketRequest(
            draft_artifact=_sample_draft(),
            packet_type="patient_claim_review_packet",
        ),
        actor="hal_operator",
        roles=FULL_ROLES,
        approval_attestation=_valid_attestation(),
    )
    assert packet.source_fact_refs == ["claim:CLM-1001", "clinical_note:NOTE-1"]
    assert packet.missing_data_codes == ["missing_softdent_procedures_export"]
