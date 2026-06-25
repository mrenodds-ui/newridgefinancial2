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
NARRATIVE_REVIEW_VERSION = "1.0.0"
NARRATIVE_EXPORT_VERSION = "1.0.0"
NARRATIVE_WORKFLOW_VERSION = "1.0.0"

NarrativeDraftStatus = Literal["draft", "blocked_missing_data", "ready_for_human_review"]
NarrativeReviewStatus = Literal[
    "pending_review",
    "approved",
    "rejected",
    "revision_requested",
]
NarrativeExportFormat = Literal["plain_text", "markdown"]
NarrativeSubmissionStatus = Literal["not_submitted"]
InsuranceNarrativeWorkflowStatus = Literal[
    "packet_created",
    "draft_created",
    "pending_review",
    "approved",
    "export_created",
    "blocked_missing_data",
    "checker_unavailable",
    "checker_completed",
]


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


class NarrativeReviewerRef(BaseModel):
    reviewer: str


class NarrativeReviewAuditEvent(BaseModel):
    event_type: str
    at: str
    actor: str
    previous_status: NarrativeReviewStatus | None = None
    new_status: NarrativeReviewStatus
    notes: str | None = None


class NarrativeCheckerSummary(BaseModel):
    checker_status: str | None = None
    missing_data_count: int = 0
    citation_issue_count: int = 0
    possible_invented_fact_count: int = 0
    contradiction_count: int = 0
    ready_for_human_review: bool | None = None


class InsuranceNarrativeReviewRecord(BaseModel):
    review_id: str
    packet_id: str
    draft_id: str
    draft_status: NarrativeDraftStatus
    status: NarrativeReviewStatus
    reviewer: str
    reviewed_at: str | None = None
    notes: str | None = None
    required_changes: list[str] = Field(default_factory=list)
    checker_summary: NarrativeCheckerSummary | None = None
    approval_attestation: bool | None = None
    audit_events: list[NarrativeReviewAuditEvent] = Field(default_factory=list)
    created_at: str
    review_version: str = NARRATIVE_REVIEW_VERSION


class NarrativeExportSection(BaseModel):
    key: str
    title: str
    body: str


class NarrativeExportApprovalSummary(BaseModel):
    reviewer: str
    reviewed_at: str
    notes: str | None = None
    attestation_confirmed: bool
    attestation_text: str


class NarrativeExportAuditMetadata(BaseModel):
    created_at: str
    created_by: str
    export_version: str = NARRATIVE_EXPORT_VERSION


class InsuranceNarrativeExport(BaseModel):
    export_id: str
    packet_id: str
    draft_id: str
    review_id: str
    format: NarrativeExportFormat
    title: str
    body: str
    sections: list[NarrativeExportSection] = Field(default_factory=list)
    citations: list[NarrativeDraftCitation] = Field(default_factory=list)
    missing_data_disclosures: list[NarrativeMissingDataItem] = Field(default_factory=list)
    approval_summary: NarrativeExportApprovalSummary
    audit_metadata: NarrativeExportAuditMetadata
    created_at: str
    actor: str
    submission_status: NarrativeSubmissionStatus = "not_submitted"


class NarrativeWorkflowWarning(BaseModel):
    code: str
    message: str


class NarrativeWorkflowAuditEvent(BaseModel):
    event_type: str
    at: str
    actor: str
    detail: str | None = None


class InsuranceNarrativeWorkflowOptions(BaseModel):
    run_checker: bool = False
    export_format: str = "markdown"


class InsuranceNarrativeWorkflowResult(BaseModel):
    packet: InsuranceNarrativeCasePacket
    draft: InsuranceNarrativeDraft
    checker_summary: NarrativeCheckerSummary | None = None
    review: InsuranceNarrativeReviewRecord | None = None
    export: InsuranceNarrativeExport | None = None
    status: InsuranceNarrativeWorkflowStatus
    warnings: list[NarrativeWorkflowWarning] = Field(default_factory=list)
    audit_events: list[NarrativeWorkflowAuditEvent] = Field(default_factory=list)
    workflow_version: str = NARRATIVE_WORKFLOW_VERSION
