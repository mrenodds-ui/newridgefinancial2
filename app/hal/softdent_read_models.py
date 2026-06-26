"""Typed internal objects for the SoftDent Read Broker.

These models describe bounded, answer-safe facts that the broker returns to HAL
patient workflows. They never carry raw CSV rows, raw database payloads, or
secrets. Monetary A/R values are only populated when a real A/R source exists;
otherwise the relevant ``missing_*`` code is surfaced instead of a fabricated
``$0`` balance.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# --- Missing-data codes ----------------------------------------------------

MISSING_SOFTDENT_CLAIMS_EXPORT = "missing_softdent_claims_export"
MISSING_SOFTDENT_CLINICAL_NOTES_EXPORT = "missing_softdent_clinical_notes_export"
MISSING_SOFTDENT_AR = "missing_softdent_ar"
MISSING_SOFTDENT_PATIENT_LEDGER_EXPORT = "missing_softdent_patient_ledger_export"
MISSING_SOFTDENT_PROCEDURES_EXPORT = "missing_softdent_procedures_export"
MISSING_SOFTDENT_PAYER_STATUS = "missing_softdent_payer_status"
MISSING_SOFTDENT_APPOINTMENTS_EXPORT = "missing_softdent_appointments_export"
MISSING_SOFTDENT_PATIENT_MATCH = "missing_softdent_patient_match"

SOFTDENT_MISSING_DATA_CODES = frozenset(
    {
        MISSING_SOFTDENT_CLAIMS_EXPORT,
        MISSING_SOFTDENT_CLINICAL_NOTES_EXPORT,
        MISSING_SOFTDENT_AR,
        MISSING_SOFTDENT_PATIENT_LEDGER_EXPORT,
        MISSING_SOFTDENT_PROCEDURES_EXPORT,
        MISSING_SOFTDENT_PAYER_STATUS,
        MISSING_SOFTDENT_APPOINTMENTS_EXPORT,
        MISSING_SOFTDENT_PATIENT_MATCH,
    }
)


# --- Source metadata -------------------------------------------------------

class SoftDentSourceMetadata(BaseModel):
    """Where a bounded fact set came from, without exposing raw rows."""

    source_adapter: Literal["exports"] = "exports"
    source_name: str | None = None
    source_backend: str = "unknown"
    source_modified_at_utc: str | None = None
    loaded_at_utc: str
    row_count: int = 0


# --- Query --------------------------------------------------------------------

class SoftDentPatientQuery(BaseModel):
    """Bounded, server-side patient query. Never raw SQL."""

    question: str | None = None
    patient_ref: str | None = None
    claim_id: str | None = None
    include_clinical_notes: bool = True
    include_ledger: bool = True
    include_narrative_source_facts: bool = False
    note_limit: int = Field(default=5, ge=1, le=20)


# --- Bounded fact objects ---------------------------------------------------

class PatientMatch(BaseModel):
    display_name: str
    patient_ref: str | None = None
    score: int = 0


class ClaimContext(BaseModel):
    claim_id: str | None = None
    status: str | None = None
    payer_name: str | None = None
    procedure_refs: list[str] = Field(default_factory=list)
    service_date: str | None = None
    denial_reason: str | None = None
    claim_amount: float | None = None
    documentation_needed: list[str] = Field(default_factory=list)
    source_record_id: str | None = None


class ProcedureContext(BaseModel):
    procedure_id: str | None = None
    code: str | None = None
    description: str | None = None
    tooth: str | None = None
    service_date: str | None = None
    provider: str | None = None
    claim_id: str | None = None
    source_record_id: str | None = None


class ClinicalNoteSummary(BaseModel):
    note_id: str | None = None
    note_date: str | None = None
    procedure_id: str | None = None
    summary_text: str = ""
    source_record_id: str | None = None


class LedgerContext(BaseModel):
    available: bool = False
    patient_balance: float | None = None
    insurance_balance: float | None = None
    total_ar: float | None = None
    payments: float | None = None
    last_payment_date: str | None = None
    missing_data_codes: list[str] = Field(default_factory=list)


class PayerContext(BaseModel):
    payer_name: str | None = None
    claim_statuses: list[str] = Field(default_factory=list)
    pending_items: list[str] = Field(default_factory=list)
    last_status_date: str | None = None


class DocumentationStatus(BaseModel):
    missing_items: list[str] = Field(default_factory=list)
    available_items: list[str] = Field(default_factory=list)
    needs_review: bool = True
    source_facts: list[str] = Field(default_factory=list)


class NarrativeSourceFacts(BaseModel):
    patient_label: str = ""
    claim_facts: list[str] = Field(default_factory=list)
    procedure_facts: list[str] = Field(default_factory=list)
    clinical_note_facts: list[str] = Field(default_factory=list)
    ledger_facts: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class PatientContext(BaseModel):
    matched: bool = False
    display_name: str = ""
    patient_ref: str | None = None
    chart_ref_hash: str | None = None
    claims: list[ClaimContext] = Field(default_factory=list)
    procedures: list[ProcedureContext] = Field(default_factory=list)
    clinical_notes: list[ClinicalNoteSummary] = Field(default_factory=list)
    ledger: LedgerContext | None = None
    payer_context: list[PayerContext] = Field(default_factory=list)
    documentation_status: DocumentationStatus = Field(default_factory=DocumentationStatus)
    narrative_source_facts: NarrativeSourceFacts | None = None
    missing_data_codes: list[str] = Field(default_factory=list)
    source_metadata: list[SoftDentSourceMetadata] = Field(default_factory=list)


class SoftDentReadSourceStatus(BaseModel):
    claims_available: bool = False
    clinical_notes_available: bool = False
    ar_available: bool = False
    source_metadata: list[SoftDentSourceMetadata] = Field(default_factory=list)
    missing_data_codes: list[str] = Field(default_factory=list)
