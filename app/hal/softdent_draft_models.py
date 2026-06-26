"""Draft-only SoftDent artifact models for Phase 2 human-review workflows."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SoftDentDraftType = Literal[
    "clinical_note_proposal",
    "insurance_narrative_proposal",
    "claim_follow_up_checklist",
    "missing_document_checklist",
    "payer_appeal_prep_summary",
    "staff_task_recommendation",
    "internal_patient_summary",
]

SOFTDENT_DRAFT_TYPES: frozenset[str] = frozenset(
    {
        "clinical_note_proposal",
        "insurance_narrative_proposal",
        "claim_follow_up_checklist",
        "missing_document_checklist",
        "payer_appeal_prep_summary",
        "staff_task_recommendation",
        "internal_patient_summary",
    }
)

DRAFT_TYPES_REQUIRING_CLINICAL: frozenset[str] = frozenset({"clinical_note_proposal"})


class SoftDentDraftRequest(BaseModel):
    patient_query: str = Field(min_length=3, max_length=2000)
    claim_id: str | None = Field(default=None, max_length=128)
    draft_type: SoftDentDraftType
    workflow_reason: str = Field(default="staff_review", min_length=3, max_length=200)
    include_clinical_context: bool = True
    include_ledger_context: bool = False


class SoftDentDraftArtifact(BaseModel):
    draft_id: str
    draft_type: SoftDentDraftType
    patient_label: str
    title: str
    body: str
    checklist_items: list[str] = Field(default_factory=list)
    source_fact_refs: list[str] = Field(default_factory=list)
    missing_data_codes: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    review_required: bool = True
    external_action_performed: bool = False
