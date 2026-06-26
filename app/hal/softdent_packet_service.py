"""SoftDent local packet service for Phase 3 human-approved internal artifacts.

Packets are local-only approved artifacts derived from reviewed Phase 2 drafts.
They never submit to payers, write back to SoftDent, or trigger email/fax/upload/
Gateway/E-Services actions.
"""

from __future__ import annotations

from typing import Iterable
from uuid import uuid4

from .audit import record_softdent_packet_audit
from .softdent_packet_models import (
    SOFTDENT_PACKET_TYPES,
    SoftDentLocalPacketArtifact,
    SoftDentLocalPacketRequest,
    SoftDentPacketApprovalAttestation,
    SoftDentPacketType,
)
from .softdent_draft_models import SoftDentDraftArtifact
from .softdent_read_broker import (
    SOFTDENT_NARRATIVE_DRAFT,
    SOFTDENT_PATIENT_READ,
    SOFTDENT_READ,
    _hash_ref,
    _normalize_roles,
    _require_roles,
)

PACKET_DISCLAIMER = (
    "Local only. Approved for internal office use. "
    "Not submitted. Not written to SoftDent. "
    "No email, fax, upload, or Gateway/E-Services action was performed."
)

_REQUIRED_ATTESTATION_FLAGS = (
    "attestation_checked",
    "acknowledged_local_only",
    "acknowledged_not_submitted",
    "acknowledged_no_softdent_writeback",
    "acknowledged_no_external_delivery",
)


def create_softdent_local_packet(
    request: SoftDentLocalPacketRequest,
    *,
    actor: str,
    roles: Iterable[str],
    approval_attestation: SoftDentPacketApprovalAttestation,
) -> SoftDentLocalPacketArtifact:
    if request.packet_type not in SOFTDENT_PACKET_TYPES:
        raise ValueError(f"Unsupported packet type: {request.packet_type}")

    normalized_roles = _normalize_roles(roles) or set()
    _require_roles(
        normalized_roles,
        {SOFTDENT_READ, SOFTDENT_PATIENT_READ, SOFTDENT_NARRATIVE_DRAFT},
        action="create_softdent_local_packet",
    )

    draft = request.draft_artifact
    _validate_source_draft(draft)
    _validate_approval_attestation(approval_attestation)

    packet = _build_packet_artifact(
        draft=draft,
        packet_type=request.packet_type,
        approval_attestation=approval_attestation,
    )
    _audit_packet(
        packet=packet,
        draft=draft,
        actor=actor,
        roles=normalized_roles,
        approval_attestation=approval_attestation,
    )
    return packet


def _validate_source_draft(draft: SoftDentDraftArtifact) -> None:
    if not str(draft.draft_id or "").strip():
        raise ValueError("Source draft must include a valid draft_id.")
    if not draft.review_required:
        raise ValueError("Source draft must require human review before packet approval.")
    if draft.external_action_performed:
        raise ValueError("Source draft cannot report an external action.")


def _validate_approval_attestation(attestation: SoftDentPacketApprovalAttestation) -> None:
    if not str(attestation.approved_by or "").strip():
        raise ValueError("approved_by is required for local packet approval.")
    if not str(attestation.approval_note or "").strip():
        raise ValueError("approval_note is required for local packet approval.")
    for flag in _REQUIRED_ATTESTATION_FLAGS:
        if not bool(getattr(attestation, flag)):
            raise ValueError(f"Approval attestation requires {flag}=true.")


def _build_packet_artifact(
    *,
    draft: SoftDentDraftArtifact,
    packet_type: SoftDentPacketType,
    approval_attestation: SoftDentPacketApprovalAttestation,
) -> SoftDentLocalPacketArtifact:
    titles = {
        "approved_narrative_packet": f"Approved narrative packet for {draft.patient_label}",
        "appeal_prep_packet": f"Appeal prep packet for {draft.patient_label}",
        "missing_document_checklist_packet": f"Missing document checklist packet for {draft.patient_label}",
        "staff_task_packet": f"Staff task packet for {draft.patient_label}",
        "patient_claim_review_packet": f"Patient claim review packet for {draft.patient_label}",
        "printable_internal_review_artifact": f"Printable internal review for {draft.patient_label}",
        "copied_draft_text_packet": f"Copied draft text packet for {draft.patient_label}",
    }
    body = (
        f"{PACKET_DISCLAIMER} "
        f"Approved by {approval_attestation.approved_by}. "
        f"Approval note: {approval_attestation.approval_note} "
        f"Derived from reviewed draft {draft.draft_id} ({draft.draft_type}). "
        f"{draft.body}"
    )
    limitations = list(draft.limitations)
    limitations.append(PACKET_DISCLAIMER)
    limitations.append("submission_status remains not_submitted.")
    return SoftDentLocalPacketArtifact(
        packet_id=f"sdp-{uuid4().hex[:12]}",
        source_draft_id=draft.draft_id,
        packet_type=packet_type,
        patient_label=draft.patient_label,
        title=titles[packet_type],
        body=body,
        checklist_items=list(draft.checklist_items),
        source_fact_refs=list(draft.source_fact_refs),
        missing_data_codes=list(draft.missing_data_codes),
        limitations=limitations,
        approval_attestation=approval_attestation,
        submission_status="not_submitted",
        external_action_performed=False,
        softdent_writeback_performed=False,
        local_only=True,
    )


def _ids_from_source_refs(refs: list[str], prefix: str) -> list[str]:
    return [ref.split(":", 1)[1] for ref in refs if ref.startswith(f"{prefix}:") and ":" in ref]


def _audit_packet(
    *,
    packet: SoftDentLocalPacketArtifact,
    draft: SoftDentDraftArtifact,
    actor: str,
    roles: set[str],
    approval_attestation: SoftDentPacketApprovalAttestation,
) -> None:
    claim_ids = _ids_from_source_refs(packet.source_fact_refs, "claim")
    note_ids = _ids_from_source_refs(packet.source_fact_refs, "clinical_note")
    ledger_ids = _ids_from_source_refs(packet.source_fact_refs, "ledger")
    record_softdent_packet_audit(
        actor=actor,
        roles_used=sorted(roles),
        packet_type=packet.packet_type,
        source_draft_id=packet.source_draft_id,
        packet_id=packet.packet_id,
        patient_display_name=packet.patient_label,
        patient_ref_hash=_hash_ref(packet.patient_label),
        chart_ref_hash=_hash_ref(packet.patient_label),
        claim_ids=claim_ids,
        clinical_note_ids=note_ids,
        ledger_record_ids=ledger_ids,
        source_fact_refs=packet.source_fact_refs,
        missing_data_codes=packet.missing_data_codes,
        approval_attestation=approval_attestation.model_dump(),
        submission_status="not_submitted",
        external_action_performed=False,
        softdent_writeback_performed=False,
        local_only=True,
    )
