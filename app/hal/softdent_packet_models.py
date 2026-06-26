"""Local approved packet models for Phase 3 human-reviewed office artifacts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .softdent_draft_models import SoftDentDraftArtifact

SoftDentPacketType = Literal[
    "approved_narrative_packet",
    "appeal_prep_packet",
    "missing_document_checklist_packet",
    "staff_task_packet",
    "patient_claim_review_packet",
    "printable_internal_review_artifact",
    "copied_draft_text_packet",
]

SOFTDENT_PACKET_TYPES: frozenset[str] = frozenset(
    {
        "approved_narrative_packet",
        "appeal_prep_packet",
        "missing_document_checklist_packet",
        "staff_task_packet",
        "patient_claim_review_packet",
        "printable_internal_review_artifact",
        "copied_draft_text_packet",
    }
)


class SoftDentPacketApprovalAttestation(BaseModel):
    approved_by: str = Field(min_length=1, max_length=200)
    approval_note: str = Field(min_length=1, max_length=2000)
    reviewed_at_utc: str | None = None
    attestation_checked: bool
    acknowledged_local_only: bool
    acknowledged_not_submitted: bool
    acknowledged_no_softdent_writeback: bool
    acknowledged_no_external_delivery: bool


class SoftDentLocalPacketRequest(BaseModel):
    draft_artifact: SoftDentDraftArtifact
    packet_type: SoftDentPacketType


class SoftDentLocalPacketArtifact(BaseModel):
    packet_id: str
    source_draft_id: str
    packet_type: SoftDentPacketType
    patient_label: str
    title: str
    body: str
    checklist_items: list[str] = Field(default_factory=list)
    source_fact_refs: list[str] = Field(default_factory=list)
    missing_data_codes: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    approval_attestation: SoftDentPacketApprovalAttestation
    submission_status: Literal["not_submitted"] = "not_submitted"
    external_action_performed: bool = False
    softdent_writeback_performed: bool = False
    local_only: bool = True
