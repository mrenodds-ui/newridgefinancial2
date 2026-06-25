"""Typed models for insurance narrative case packets."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SourceType = Literal[
    "softdent",
    "claim",
    "ledger",
    "clinical_note",
    "attachment",
    "payer_denial",
    "quickbooks",
    "manual",
]

MissingDataSeverity = Literal["info", "warning", "critical"]

CASE_PACKET_SCHEMA_VERSION = "1.0.0"
CASE_PACKET_BUILDER_VERSION = "1.0.0"
NARRATIVE_DRAFT_VERSION = "1.0.0"

NarrativeDraftStatus = Literal["draft", "blocked_missing_data", "ready_for_human_review"]


class NarrativeSourceFact(BaseModel):
    fact_id: str
    source_type: SourceType
    source_label: str
    source_date: str | None = None
    text: str
    supports: list[str] = Field(default_factory=list)
    source_strength: str | None = None


class NarrativeMissingDataItem(BaseModel):
    code: str
    label: str
    severity: MissingDataSeverity
    why_it_matters: str
    blocking: bool


class NarrativeAttachmentSummary(BaseModel):
    attachment_id: str
    label: str
    attachment_type: str
    available: bool


class NarrativeAuditMetadata(BaseModel):
    created_at: str
    created_by: str
    builder_version: str = CASE_PACKET_BUILDER_VERSION
    schema_version: str = CASE_PACKET_SCHEMA_VERSION


class PatientCaseSummary(BaseModel):
    patient_ref: str
    chart_ref: str | None = None
    label: str


class ClaimCaseSummary(BaseModel):
    claim_id: str
    status: str | None = None
    payer_name: str | None = None
    billed_amount: float | None = None
    denial_reason: str | None = None


class ProcedureCaseSummary(BaseModel):
    procedure_id: str
    description: str
    code: str | None = None
    tooth: str | None = None
    service_date: str | None = None


class DateRangeSummary(BaseModel):
    start_date: str
    end_date: str


class InsuranceNarrativeCasePacket(BaseModel):
    packet_id: str
    created_at: str
    actor: str
    narrative_type: str
    patient: PatientCaseSummary
    claim: ClaimCaseSummary | None = None
    procedures: list[ProcedureCaseSummary] = Field(default_factory=list)
    date_range: DateRangeSummary | None = None
    payer_name: str | None = None
    source_facts: list[NarrativeSourceFact] = Field(default_factory=list)
    attachments: list[NarrativeAttachmentSummary] = Field(default_factory=list)
    missing_data: list[NarrativeMissingDataItem] = Field(default_factory=list)
    audit_metadata: NarrativeAuditMetadata


class NarrativeDraftCitation(BaseModel):
    fact_id: str
    section_key: str
    excerpt: str


class NarrativeDraftWarning(BaseModel):
    code: str
    message: str
    severity: MissingDataSeverity


class NarrativeDraftSection(BaseModel):
    key: str
    title: str
    body: str


class NarrativeDraftAuditMetadata(BaseModel):
    created_at: str
    created_by: str
    drafter_version: str = NARRATIVE_DRAFT_VERSION


class InsuranceNarrativeDraft(BaseModel):
    draft_id: str
    packet_id: str
    narrative_type: str
    status: NarrativeDraftStatus
    sections: list[NarrativeDraftSection] = Field(default_factory=list)
    citations: list[NarrativeDraftCitation] = Field(default_factory=list)
    warnings: list[NarrativeDraftWarning] = Field(default_factory=list)
    missing_data: list[NarrativeMissingDataItem] = Field(default_factory=list)
    created_at: str
    actor: str
    approval_required: bool = True
    audit_metadata: NarrativeDraftAuditMetadata
