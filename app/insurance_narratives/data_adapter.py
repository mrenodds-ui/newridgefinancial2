"""Scoped data adapters for insurance narrative case packets."""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, Field

from app.insurance_narratives.schemas import (
    ClaimCaseSummary,
    DateRangeSummary,
    NarrativeAttachmentSummary,
    NarrativeMissingDataItem,
    NarrativeSourceFact,
    PatientCaseSummary,
    ProcedureCaseSummary,
)

# Deterministic de-identified fixture catalog for tests and local development.
# Keys are patient_ref values. No real PHI — synthetic refs only.
FIXTURE_CATALOG: dict[str, dict[str, Any]] = {
    "CHART-A": {
        "patient_label": "Patient ref CHART-A",
        "claims": {
            "CLAIM-1001": {
                "status": "Denied",
                "payer_name": "Payer One",
                "billed_amount": 215.75,
                "denial_reason": "Missing supporting attachment",
                "procedures": [
                    {
                        "procedure_id": "PROC-CROWN-BUILDUP-3",
                        "description": "Crown buildup",
                        "tooth": "3",
                        "service_date": "2026-06-12",
                    }
                ],
                "clinical_note_excerpt": (
                    "Fractured cusp with recurrent decay; documented cold sensitivity."
                ),
                "attachments_available": [],
                "missing_codes": [
                    "missing_softdent_ar",
                    "missing_prior_auth",
                    "missing_radiograph",
                ],
            }
        },
    }
}

MISSING_DATA_CATALOG: dict[str, NarrativeMissingDataItem] = {
    "missing_softdent_ar": NarrativeMissingDataItem(
        code="missing_softdent_ar",
        label="SoftDent accounts receivable export",
        severity="warning",
        why_it_matters="A/R aging informs resubmission and patient-balance context; unavailable exports must not be treated as zero.",
        blocking=False,
    ),
    "missing_prior_auth": NarrativeMissingDataItem(
        code="missing_prior_auth",
        label="Prior authorization reference",
        severity="warning",
        why_it_matters="Payer may require prior-auth proof for the billed procedure.",
        blocking=False,
    ),
    "missing_radiograph": NarrativeMissingDataItem(
        code="missing_radiograph",
        label="Supporting radiograph attachment",
        severity="critical",
        why_it_matters="Denial cited missing supporting attachment; radiograph may be required for resubmission.",
        blocking=True,
    ),
    "missing_periodontal_chart": NarrativeMissingDataItem(
        code="missing_periodontal_chart",
        label="Periodontal chart",
        severity="warning",
        why_it_matters="Periodontal documentation may be required for certain procedure narratives.",
        blocking=False,
    ),
    "missing_denial_letter": NarrativeMissingDataItem(
        code="missing_denial_letter",
        label="Payer denial letter",
        severity="info",
        why_it_matters="Formal denial letter can clarify payer-specific requirements.",
        blocking=False,
    ),
    "missing_claim_status": NarrativeMissingDataItem(
        code="missing_claim_status",
        label="Claim status export",
        severity="warning",
        why_it_matters="Claim status confirms whether the case is denied, pending, or paid.",
        blocking=True,
    ),
    "missing_claim_record": NarrativeMissingDataItem(
        code="missing_claim_record",
        label="Matching claim record",
        severity="critical",
        why_it_matters="No approved claim export matched the requested patient/claim scope.",
        blocking=True,
    ),
    "missing_patient_record": NarrativeMissingDataItem(
        code="missing_patient_record",
        label="Matching patient record",
        severity="critical",
        why_it_matters="No approved patient-scoped export matched the requested patient reference.",
        blocking=True,
    ),
    "missing_softdent_claims_export": NarrativeMissingDataItem(
        code="missing_softdent_claims_export",
        label="SoftDent claims export file",
        severity="critical",
        why_it_matters="Insurance narrative scope requires softdent_claims_export.csv in the configured import directory.",
        blocking=True,
    ),
    "missing_softdent_procedures_export": NarrativeMissingDataItem(
        code="missing_softdent_procedures_export",
        label="SoftDent procedures export file",
        severity="warning",
        why_it_matters="Procedure detail requires softdent_procedures_export.csv in the configured import directory.",
        blocking=False,
    ),
    "missing_scoped_claim_row": NarrativeMissingDataItem(
        code="missing_scoped_claim_row",
        label="Scoped claim row",
        severity="critical",
        why_it_matters="No claim row in the export matched the requested patient_ref and claim_id.",
        blocking=True,
    ),
    "missing_scoped_procedure_rows": NarrativeMissingDataItem(
        code="missing_scoped_procedure_rows",
        label="Scoped procedure rows",
        severity="warning",
        why_it_matters="Expected procedure rows were not found in the procedures export for this scope.",
        blocking=False,
    ),
    "missing_softdent_patient_ledger_export": NarrativeMissingDataItem(
        code="missing_softdent_patient_ledger_export",
        label="SoftDent patient ledger export file",
        severity="warning",
        why_it_matters="Ledger supporting facts require softdent_patient_ledger_export.csv in the configured import directory.",
        blocking=False,
    ),
    "missing_scoped_ledger_rows": NarrativeMissingDataItem(
        code="missing_scoped_ledger_rows",
        label="Scoped ledger rows",
        severity="warning",
        why_it_matters="No ledger rows in the export matched the requested patient, claim, procedure, or date scope.",
        blocking=False,
    ),
    "invalid_softdent_patient_ledger_export": NarrativeMissingDataItem(
        code="invalid_softdent_patient_ledger_export",
        label="Invalid SoftDent patient ledger export",
        severity="warning",
        why_it_matters="softdent_patient_ledger_export.csv is present but malformed or missing required columns.",
        blocking=False,
    ),
}

SOFTDENT_NARRATIVE_CLAIMS_FILENAME = "softdent_claims_export.csv"
SOFTDENT_NARRATIVE_PROCEDURES_FILENAME = "softdent_procedures_export.csv"
SOFTDENT_NARRATIVE_PATIENT_LEDGER_FILENAME = "softdent_patient_ledger_export.csv"
SOFTDENT_NARRATIVE_LEDGER_REQUIRED_COLUMNS = frozenset(
    {
        "patient_ref",
        "transaction_id",
        "transaction_date",
        "transaction_type",
        "procedure_id",
        "claim_id",
        "description",
        "amount",
        "source_report_date",
    }
)
DEFAULT_SOFTDENT_NARRATIVE_EXPORT_DIR = Path("app/data/imports/insurance_narratives/softdent")


class InsuranceNarrativeScope(BaseModel):
    patient_ref: str
    claim_id: str | None = None
    procedure_ids: list[str] | None = None
    date_range: tuple[str, str] | None = None
    narrative_type: str
    actor: str


class InsuranceNarrativePacketInputs(BaseModel):
    """Bounded adapter output normalized before packet assembly. No raw database rows."""

    patient: PatientCaseSummary
    claim: ClaimCaseSummary | None = None
    procedures: list[ProcedureCaseSummary] = Field(default_factory=list)
    date_range: DateRangeSummary | None = None
    payer_name: str | None = None
    source_facts: list[NarrativeSourceFact] = Field(default_factory=list)
    attachments: list[NarrativeAttachmentSummary] = Field(default_factory=list)
    missing_data: list[NarrativeMissingDataItem] = Field(default_factory=list)


class InsuranceNarrativeDataAdapter(Protocol):
    """Protocol for scoped, read-only narrative packet input providers."""

    @property
    def adapter_name(self) -> str: ...

    @property
    def source_mode(self) -> str: ...

    def fetch_packet_inputs(self, scope: InsuranceNarrativeScope) -> InsuranceNarrativePacketInputs: ...


def missing_data_item(code: str) -> NarrativeMissingDataItem:
    if code not in MISSING_DATA_CATALOG:
        return NarrativeMissingDataItem(
            code=code,
            label=code.replace("_", " "),
            severity="warning",
            why_it_matters="Required supporting data is unavailable in approved exports.",
            blocking=False,
        )
    return MISSING_DATA_CATALOG[code].model_copy(deep=True)


def _normalize_ref(value: str) -> str:
    return value.strip().upper()


def _build_source_facts_for_claim(
    *,
    patient_ref: str,
    claim_id: str,
    claim: dict[str, Any],
    source_label_prefix: str | None = None,
) -> list[NarrativeSourceFact]:
    facts: list[NarrativeSourceFact] = []
    procedures = claim.get("procedures") or []
    primary_source_date = str((procedures or [{}])[0].get("service_date") or "") or None
    claim_status_label = f"Claim {claim_id} status"
    payer_label = "Payer"
    denial_label = "Payer denial note"
    procedure_label = "Procedure"
    billed_amount_label = "Billed amount"
    clinical_note_label = "Clinical note excerpt"
    if source_label_prefix:
        claim_status_label = f"{source_label_prefix}: {claim_status_label}"
        payer_label = f"{source_label_prefix}: {payer_label}"
        denial_label = f"{source_label_prefix}: {denial_label}"
        procedure_label = f"{source_label_prefix}: {procedure_label}"
        billed_amount_label = f"{source_label_prefix}: {billed_amount_label}"
        clinical_note_label = f"{source_label_prefix}: {clinical_note_label}"
    facts.append(
        NarrativeSourceFact(
            fact_id=f"fact-{patient_ref}-claim-status",
            source_type="claim",
            source_label=claim_status_label,
            source_date=primary_source_date,
            text=f"Claim {claim_id} status is {claim.get('status')}.",
            supports=[claim_id],
            source_strength="primary",
        )
    )
    if claim.get("payer_name"):
        facts.append(
            NarrativeSourceFact(
                fact_id=f"fact-{patient_ref}-payer",
                source_type="claim",
                source_label=payer_label,
                source_date=primary_source_date,
                text=f"Payer: {claim['payer_name']}.",
                supports=[claim_id],
                source_strength="primary",
            )
        )
    if claim.get("denial_reason"):
        facts.append(
            NarrativeSourceFact(
                fact_id=f"fact-{patient_ref}-denial-reason",
                source_type="payer_denial",
                source_label=denial_label,
                source_date=primary_source_date,
                text=str(claim["denial_reason"]),
                supports=[claim_id],
                source_strength="primary",
            )
        )
    for procedure in procedures:
        proc_id = str(procedure.get("procedure_id") or "")
        facts.append(
            NarrativeSourceFact(
                fact_id=f"fact-{proc_id}-procedure",
                source_type="softdent",
                source_label=procedure_label,
                source_date=str(procedure.get("service_date") or "") or None,
                text=(
                    f"Procedure {procedure.get('description')} "
                    f"tooth {procedure.get('tooth')} "
                    f"on {procedure.get('service_date')}."
                ).strip(),
                supports=[proc_id, claim_id],
                source_strength="primary",
            )
        )
        if procedure.get("service_date") and claim.get("billed_amount") is not None:
            facts.append(
                NarrativeSourceFact(
                    fact_id=f"fact-{proc_id}-billed-amount",
                    source_type="claim",
                    source_label=billed_amount_label,
                    source_date=str(procedure.get("service_date")),
                    text=f"Billed amount {claim['billed_amount']:.2f}.",
                    supports=[claim_id, proc_id],
                    source_strength="primary",
                )
            )
    if claim.get("clinical_note_excerpt"):
        facts.append(
            NarrativeSourceFact(
                fact_id=f"fact-{patient_ref}-clinical-note",
                source_type="clinical_note",
                source_label=clinical_note_label,
                source_date=str((claim.get("procedures") or [{}])[0].get("service_date") or "") or None,
                text=str(claim["clinical_note_excerpt"]),
                supports=[claim_id],
                source_strength="supporting",
            )
        )
    return facts


def _build_fixture_claim_inputs(
    *,
    normalized_ref: str,
    claim_key: str,
    claim_fixture: dict[str, Any],
    patient_label: str,
    procedure_ids: list[str] | None,
    date_range: tuple[str, str] | None,
) -> InsuranceNarrativePacketInputs:
    claim_summary = ClaimCaseSummary(
        claim_id=claim_key,
        status=str(claim_fixture.get("status") or "") or None,
        payer_name=str(claim_fixture.get("payer_name") or "") or None,
        billed_amount=claim_fixture.get("billed_amount"),
        denial_reason=str(claim_fixture.get("denial_reason") or "") or None,
    )
    procedures: list[ProcedureCaseSummary] = []
    for raw_procedure in claim_fixture.get("procedures") or []:
        proc = ProcedureCaseSummary(
            procedure_id=str(raw_procedure.get("procedure_id") or ""),
            description=str(raw_procedure.get("description") or ""),
            code=raw_procedure.get("code"),
            tooth=raw_procedure.get("tooth"),
            service_date=raw_procedure.get("service_date"),
        )
        if procedure_ids and proc.procedure_id not in procedure_ids:
            continue
        procedures.append(proc)
    source_facts = _build_source_facts_for_claim(
        patient_ref=normalized_ref,
        claim_id=claim_key,
        claim=claim_fixture,
    )
    missing_data = [missing_data_item(str(code)) for code in claim_fixture.get("missing_codes") or []]
    attachments = [
        NarrativeAttachmentSummary(
            attachment_id=f"att-{attachment_label.lower().replace(' ', '-')}",
            label=str(attachment_label),
            attachment_type="supporting_document",
            available=True,
        )
        for attachment_label in claim_fixture.get("attachments_available") or []
    ]
    date_range_summary: DateRangeSummary | None = None
    service_dates = [proc.service_date for proc in procedures if proc.service_date]
    if service_dates:
        date_range_summary = DateRangeSummary(start_date=min(service_dates), end_date=max(service_dates))
    if date_range:
        date_range_summary = DateRangeSummary(start_date=date_range[0], end_date=date_range[1])
    return InsuranceNarrativePacketInputs(
        patient=PatientCaseSummary(
            patient_ref=normalized_ref,
            chart_ref=normalized_ref,
            label=patient_label,
        ),
        claim=claim_summary,
        procedures=procedures,
        date_range=date_range_summary,
        payer_name=claim_summary.payer_name,
        source_facts=source_facts,
        attachments=attachments,
        missing_data=missing_data,
    )


class FixtureInsuranceNarrativeDataAdapter:
    """Deterministic de-identified fixture adapter (default for tests)."""

    @property
    def adapter_name(self) -> str:
        return "fixture"

    @property
    def source_mode(self) -> str:
        return "fixture"

    def fetch_packet_inputs(self, scope: InsuranceNarrativeScope) -> InsuranceNarrativePacketInputs:
        normalized_ref = _normalize_ref(scope.patient_ref)
        patient_fixture = FIXTURE_CATALOG.get(normalized_ref)
        if patient_fixture is None:
            return InsuranceNarrativePacketInputs(
                patient=PatientCaseSummary(
                    patient_ref=normalized_ref,
                    chart_ref=normalized_ref,
                    label=f"Patient ref {normalized_ref}",
                ),
                missing_data=[missing_data_item("missing_patient_record")],
            )

        patient_label = str(patient_fixture.get("patient_label") or f"Patient ref {normalized_ref}")
        claims: dict[str, Any] = patient_fixture.get("claims") or {}
        claim_key = (scope.claim_id or "").strip().upper()
        claim_fixture = claims.get(claim_key) if claim_key else None

        if claim_key and claim_fixture is None:
            return InsuranceNarrativePacketInputs(
                patient=PatientCaseSummary(
                    patient_ref=normalized_ref,
                    chart_ref=normalized_ref,
                    label=patient_label,
                ),
                claim=ClaimCaseSummary(claim_id=claim_key),
                missing_data=[
                    missing_data_item("missing_claim_record"),
                    missing_data_item("missing_claim_status"),
                ],
            )

        if claim_fixture:
            return _build_fixture_claim_inputs(
                normalized_ref=normalized_ref,
                claim_key=claim_key,
                claim_fixture=claim_fixture,
                patient_label=patient_label,
                procedure_ids=scope.procedure_ids,
                date_range=scope.date_range,
            )

        return InsuranceNarrativePacketInputs(
            patient=PatientCaseSummary(
                patient_ref=normalized_ref,
                chart_ref=normalized_ref,
                label=patient_label,
            ),
        )


def _normalize_scope_token(value: str) -> str:
    return "".join(character for character in value.upper() if character.isalnum())


def _row_matches_patient_ref(row: dict[str, Any], patient_ref: str) -> bool:
    normalized_ref = _normalize_scope_token(patient_ref)
    if not normalized_ref:
        return False
    for key in ("MRN", "mrn", "chart", "chartnumber", "patientid", "patient_id"):
        candidate = _normalize_scope_token(str(row.get(key) or ""))
        if candidate and candidate == normalized_ref:
            return True
    return False


def _row_matches_claim_id(row: dict[str, Any], claim_id: str) -> bool:
    normalized_claim = _normalize_scope_token(claim_id)
    if not normalized_claim:
        return False
    for key in ("ClaimId", "claimid", "claim_id", "claimnumber", "claim_number", "claim"):
        candidate = _normalize_scope_token(str(row.get(key) or ""))
        if candidate and candidate == normalized_claim:
            return True
    return False


def _procedure_id_from_row(row: dict[str, Any], *, index: int) -> str:
    for key in ("procedure_id", "ProcedureId", "procedureid"):
        value = str(row.get(key) or "").strip()
        if value:
            return value.upper()
    procedure = str(row.get("Procedure") or row.get("procedure") or "procedure").strip()
    service_date = str(row.get("ServiceDate") or row.get("servicedate") or "").strip()
    tooth = str(row.get("Tooth") or row.get("tooth") or "").strip()
    seed = "-".join(part for part in (procedure, tooth, service_date, str(index)) if part)
    return f"PROC-{_normalize_scope_token(seed) or str(index)}"


def _row_service_date(row: dict[str, Any]) -> str | None:
    value = str(row.get("ServiceDate") or row.get("servicedate") or row.get("NoteDate") or "").strip()
    return value or None


def _row_in_date_range(row: dict[str, Any], date_range: tuple[str, str] | None) -> bool:
    if not date_range:
        return True
    service_date = _row_service_date(row)
    if not service_date:
        return False
    start_date, end_date = date_range
    return start_date <= service_date <= end_date


def _source_label_prefix(source_status: dict[str, Any]) -> str:
    source_file = str(source_status.get("source_file") or "SoftDent claims export").strip()
    source_backend = str(source_status.get("source_backend") or "local").strip()
    return f"{source_file} ({source_backend})"


def _claim_amount_if_explicit(row: dict[str, Any]) -> float | None:
    for key in ("ClaimAmount", "claimamount", "amount", "balance"):
        if key in row and row.get(key) not in (None, ""):
            try:
                return float(row.get(key))
            except (TypeError, ValueError):
                return None
    return None


def _build_local_claim_facts(
    *,
    patient_ref: str,
    claim_id: str,
    claim_rows: list[dict[str, Any]],
    note_excerpt: str | None,
    source_label_prefix: str,
) -> list[NarrativeSourceFact]:
    if not claim_rows:
        return []
    primary = claim_rows[0]
    status = str(primary.get("ClaimStatus") or primary.get("status") or "").strip() or None
    payer = str(primary.get("Payer") or primary.get("payer") or "").strip() or None
    denial = str(primary.get("DenialReason") or primary.get("denialreason") or "").strip() or None
    claim_payload: dict[str, Any] = {
        "status": status,
        "payer_name": payer,
        "denial_reason": denial,
        "billed_amount": _claim_amount_if_explicit(primary),
        "procedures": [
            {
                "procedure_id": _procedure_id_from_row(row, index=index),
                "description": str(row.get("Procedure") or row.get("procedure") or ""),
                "tooth": row.get("Tooth") or row.get("tooth"),
                "service_date": _row_service_date(row),
            }
            for index, row in enumerate(claim_rows, start=1)
        ],
        "clinical_note_excerpt": note_excerpt,
    }
    return _build_source_facts_for_claim(
        patient_ref=patient_ref,
        claim_id=claim_id,
        claim=claim_payload,
        source_label_prefix=source_label_prefix,
    )


class LocalInsuranceNarrativeDataAdapter:
    """Conservative adapter over approved local SoftDent exports.

    Reads only scoped claim/clinical-note exports when available. Never returns raw rows,
    invents facts, or synthesizes A/R. Missing exports remain explicit missing-data items.
    """

    @property
    def adapter_name(self) -> str:
        return "local_softdent_export"

    @property
    def source_mode(self) -> str:
        return "local_softdent"

    def fetch_packet_inputs(self, scope: InsuranceNarrativeScope) -> InsuranceNarrativePacketInputs:
        from app.services import (
            get_softdent_claim_source_status,
            load_softdent_claim_rows,
            load_softdent_clinical_note_rows,
        )

        normalized_ref = _normalize_ref(scope.patient_ref)
        claim_key = (scope.claim_id or "").strip().upper()
        patient_label = f"Patient ref {normalized_ref}"
        missing_data: list[NarrativeMissingDataItem] = [missing_data_item("missing_softdent_ar")]

        claim_source = get_softdent_claim_source_status()
        if not bool(claim_source.get("available")):
            missing_data.append(missing_data_item("missing_claim_status"))

        try:
            claim_rows = load_softdent_claim_rows()
        except Exception:
            claim_rows = []

        patient_rows = [row for row in claim_rows if _row_matches_patient_ref(row, normalized_ref)]
        if not patient_rows:
            missing_data.append(missing_data_item("missing_patient_record"))
            return InsuranceNarrativePacketInputs(
                patient=PatientCaseSummary(
                    patient_ref=normalized_ref,
                    chart_ref=normalized_ref,
                    label=patient_label,
                ),
                missing_data=_dedupe_missing_data(missing_data),
            )

        if not claim_key:
            return InsuranceNarrativePacketInputs(
                patient=PatientCaseSummary(
                    patient_ref=normalized_ref,
                    chart_ref=normalized_ref,
                    label=patient_label,
                ),
                missing_data=_dedupe_missing_data(missing_data),
            )

        scoped_claim_rows = []
        for index, row in enumerate(patient_rows, start=1):
            if not _row_matches_claim_id(row, claim_key):
                continue
            proc_id = _procedure_id_from_row(row, index=index)
            if scope.procedure_ids and proc_id not in scope.procedure_ids:
                continue
            if not _row_in_date_range(row, scope.date_range):
                continue
            scoped_claim_rows.append(row)
        if not scoped_claim_rows:
            missing_data.extend(
                [
                    missing_data_item("missing_claim_record"),
                    missing_data_item("missing_claim_status"),
                ]
            )
            return InsuranceNarrativePacketInputs(
                patient=PatientCaseSummary(
                    patient_ref=normalized_ref,
                    chart_ref=normalized_ref,
                    label=patient_label,
                ),
                claim=ClaimCaseSummary(claim_id=claim_key),
                missing_data=_dedupe_missing_data(missing_data),
            )

        try:
            note_rows = load_softdent_clinical_note_rows()
        except Exception:
            note_rows = []
        patient_notes = [
            row
            for row in note_rows
            if _row_matches_patient_ref(row, normalized_ref)
            and _row_in_date_range(row, scope.date_range)
            and (
                not scope.procedure_ids
                or _normalize_scope_token(str(row.get("Procedure") or row.get("procedure") or ""))
                in {_normalize_scope_token(procedure_id) for procedure_id in scope.procedure_ids}
            )
        ]
        note_excerpt: str | None = None
        if patient_notes:
            excerpt = str(
                patient_notes[0].get("ClinicalNote")
                or patient_notes[0].get("clinicalnote")
                or ""
            ).strip()
            if excerpt:
                note_excerpt = excerpt[:280]

        primary = scoped_claim_rows[0]
        claim_summary = ClaimCaseSummary(
            claim_id=claim_key,
            status=str(primary.get("ClaimStatus") or primary.get("status") or "") or None,
            payer_name=str(primary.get("Payer") or primary.get("payer") or "") or None,
            billed_amount=_claim_amount_if_explicit(primary),
            denial_reason=str(primary.get("DenialReason") or primary.get("denialreason") or "") or None,
        )
        procedures: list[ProcedureCaseSummary] = []
        for index, row in enumerate(scoped_claim_rows, start=1):
            proc = ProcedureCaseSummary(
                procedure_id=_procedure_id_from_row(row, index=index),
                description=str(row.get("Procedure") or row.get("procedure") or ""),
                code=row.get("Code") or row.get("code"),
                tooth=row.get("Tooth") or row.get("tooth"),
                service_date=_row_service_date(row),
            )
            procedures.append(proc)

        source_facts = _build_local_claim_facts(
            patient_ref=normalized_ref,
            claim_id=claim_key,
            claim_rows=scoped_claim_rows,
            note_excerpt=note_excerpt,
            source_label_prefix=_source_label_prefix(claim_source),
        )
        missing_data.extend(
            [
                missing_data_item("missing_prior_auth"),
                missing_data_item("missing_radiograph"),
            ]
        )

        date_range_summary: DateRangeSummary | None = None
        service_dates = [proc.service_date for proc in procedures if proc.service_date]
        if service_dates:
            date_range_summary = DateRangeSummary(start_date=min(service_dates), end_date=max(service_dates))
        if scope.date_range:
            date_range_summary = DateRangeSummary(
                start_date=scope.date_range[0],
                end_date=scope.date_range[1],
            )

        return InsuranceNarrativePacketInputs(
            patient=PatientCaseSummary(
                patient_ref=normalized_ref,
                chart_ref=normalized_ref,
                label=patient_label,
            ),
            claim=claim_summary,
            procedures=procedures,
            date_range=date_range_summary,
            payer_name=claim_summary.payer_name,
            source_facts=source_facts,
            attachments=[],
            missing_data=_dedupe_missing_data(missing_data),
        )


def _resolve_softdent_narrative_export_dir(export_dir: str | Path | None = None) -> Path:
    if export_dir is not None:
        return Path(export_dir)
    configured = os.environ.get("INSURANCE_NARRATIVE_SOFTDENT_EXPORT_DIR", "").strip()
    if configured:
        return Path(configured)
    return DEFAULT_SOFTDENT_NARRATIVE_EXPORT_DIR


def _normalize_csv_header(value: str) -> str:
    return value.strip().lower().replace(" ", "_")


def _read_scoped_export_csv(path: Path) -> list[dict[str, str]] | None:
    """Read a narrative export CSV. Returns None when missing or malformed."""
    if not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                return None
            normalized_fieldnames = [_normalize_csv_header(name) for name in reader.fieldnames]
            if not normalized_fieldnames or any(not name for name in normalized_fieldnames):
                return None
            rows: list[dict[str, str]] = []
            for raw_row in reader:
                if raw_row is None:
                    continue
                row = {
                    _normalize_csv_header(key): str(raw_row.get(key) or "").strip()
                    for key in reader.fieldnames
                }
                if any(row.values()):
                    rows.append(row)
            return rows
    except (OSError, csv.Error, UnicodeDecodeError):
        return None


def _export_row_patient_ref(row: dict[str, str]) -> str:
    return _normalize_ref(str(row.get("patient_ref") or ""))


def _export_row_claim_id(row: dict[str, str]) -> str:
    return _normalize_ref(str(row.get("claim_id") or ""))


def _export_row_procedure_id(row: dict[str, str]) -> str:
    return _normalize_ref(str(row.get("procedure_id") or ""))


def _parse_export_procedure_ids(value: str) -> list[str]:
    return [_normalize_ref(part) for part in value.split(",") if part.strip()]


def _parse_claim_amount(value: str) -> float | None:
    cleaned = value.strip().replace("$", "").replace(",", "")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _build_export_claim_facts(
    *,
    patient_ref: str,
    claim_id: str,
    claim_row: dict[str, str],
    procedure_rows: list[dict[str, str]],
    claims_source_label: str,
    procedures_source_label: str,
) -> list[NarrativeSourceFact]:
    facts: list[NarrativeSourceFact] = []
    claim_status = str(claim_row.get("claim_status") or "").strip()
    payer_name = str(claim_row.get("payer_name") or "").strip()
    service_date = str(claim_row.get("service_date") or "").strip() or None
    source_report_date = str(claim_row.get("source_report_date") or "").strip() or None
    claim_amount = _parse_claim_amount(str(claim_row.get("claim_amount") or ""))

    if claim_status:
        facts.append(
            NarrativeSourceFact(
                fact_id=f"fact-{patient_ref}-{claim_id}-claim-status",
                source_type="softdent",
                source_label=claims_source_label,
                source_date=source_report_date or service_date,
                text=f"Claim {claim_id} status is {claim_status}.",
                supports=[claim_id],
                source_strength="primary",
            )
        )
    if payer_name:
        facts.append(
            NarrativeSourceFact(
                fact_id=f"fact-{patient_ref}-{claim_id}-payer",
                source_type="softdent",
                source_label=claims_source_label,
                source_date=source_report_date or service_date,
                text=f"Payer: {payer_name}.",
                supports=[claim_id],
                source_strength="primary",
            )
        )
    if claim_amount is not None:
        facts.append(
            NarrativeSourceFact(
                fact_id=f"fact-{patient_ref}-{claim_id}-claim-amount",
                source_type="softdent",
                source_label=claims_source_label,
                source_date=service_date or source_report_date,
                text=f"Claim amount {claim_amount:.2f}.",
                supports=[claim_id],
                source_strength="primary",
            )
        )

    for procedure_row in procedure_rows:
        proc_id = _export_row_procedure_id(procedure_row)
        if not proc_id:
            continue
        description = str(procedure_row.get("procedure_description") or "").strip()
        tooth = str(procedure_row.get("tooth") or "").strip()
        proc_service_date = str(procedure_row.get("service_date") or "").strip() or None
        proc_source_date = str(procedure_row.get("source_report_date") or "").strip() or None
        provider_label = str(procedure_row.get("provider_label") or "").strip()
        text_parts = [f"Procedure {description or proc_id}"]
        if tooth:
            text_parts.append(f"tooth {tooth}")
        if proc_service_date:
            text_parts.append(f"on {proc_service_date}")
        if provider_label:
            text_parts.append(f"provider {provider_label}")
        facts.append(
            NarrativeSourceFact(
                fact_id=f"fact-{proc_id}-procedure",
                source_type="softdent",
                source_label=procedures_source_label,
                source_date=proc_source_date or proc_service_date,
                text=" ".join(text_parts).strip() + ".",
                supports=[proc_id, claim_id],
                source_strength="primary",
            )
        )
        procedure_code = str(procedure_row.get("procedure_code") or "").strip()
        if procedure_code:
            facts.append(
                NarrativeSourceFact(
                    fact_id=f"fact-{proc_id}-procedure-code",
                    source_type="softdent",
                    source_label=procedures_source_label,
                    source_date=proc_source_date or proc_service_date,
                    text=f"Procedure code {procedure_code}.",
                    supports=[proc_id, claim_id],
                    source_strength="supporting",
                )
            )
    return facts


def _ledger_csv_has_required_columns(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                return False
            normalized = {_normalize_csv_header(name) for name in reader.fieldnames}
            return SOFTDENT_NARRATIVE_LEDGER_REQUIRED_COLUMNS.issubset(normalized)
    except (OSError, csv.Error, UnicodeDecodeError):
        return False


def _load_patient_ledger_export(path: Path) -> tuple[list[dict[str, str]], str | None]:
    """Load ledger CSV. Returns (rows, missing_code) when absent or invalid."""
    if not path.is_file():
        return [], "missing_softdent_patient_ledger_export"
    if not _ledger_csv_has_required_columns(path):
        return [], "invalid_softdent_patient_ledger_export"
    rows = _read_scoped_export_csv(path)
    if rows is None:
        return [], "invalid_softdent_patient_ledger_export"
    return rows, None


def _ledger_transaction_date(row: dict[str, str]) -> str | None:
    value = str(row.get("transaction_date") or "").strip()
    return value or None


def _ledger_row_in_date_range(row: dict[str, str], date_range: tuple[str, str] | None) -> bool:
    if not date_range:
        return True
    transaction_date = _ledger_transaction_date(row)
    if not transaction_date:
        return False
    start_date, end_date = date_range
    return start_date <= transaction_date <= end_date


def _scope_ledger_rows(
    ledger_rows: list[dict[str, str]],
    *,
    patient_ref: str,
    claim_id: str | None,
    procedure_ids: list[str] | None,
    included_procedure_ids: set[str],
    date_range: tuple[str, str] | None,
) -> list[dict[str, str]]:
    scoped: list[dict[str, str]] = []
    requested_procedure_ids = (
        {_normalize_ref(proc_id) for proc_id in procedure_ids} if procedure_ids else None
    )
    for row in ledger_rows:
        if _export_row_patient_ref(row) != patient_ref:
            continue
        if not _ledger_row_in_date_range(row, date_range):
            continue
        row_procedure_id = _export_row_procedure_id(row)
        if requested_procedure_ids is not None:
            if not row_procedure_id or row_procedure_id not in requested_procedure_ids:
                continue
        row_claim_id = _export_row_claim_id(row)
        if claim_id:
            if row_claim_id == claim_id:
                if row_procedure_id and included_procedure_ids and row_procedure_id not in included_procedure_ids:
                    continue
                scoped.append(row)
                continue
            if not row_claim_id and row_procedure_id and row_procedure_id in included_procedure_ids:
                scoped.append(row)
            continue
        if row_procedure_id and included_procedure_ids and row_procedure_id not in included_procedure_ids:
            continue
        scoped.append(row)
    return scoped


def _build_export_ledger_facts(
    *,
    patient_ref: str,
    ledger_rows: list[dict[str, str]],
    procedure_code_by_id: dict[str, str],
) -> list[NarrativeSourceFact]:
    facts: list[NarrativeSourceFact] = []
    for row in ledger_rows:
        transaction_id = str(row.get("transaction_id") or "").strip()
        if not transaction_id:
            continue
        transaction_date = _ledger_transaction_date(row) or ""
        source_report_date = str(row.get("source_report_date") or "").strip() or None
        procedure_id = _export_row_procedure_id(row)
        claim_id = _export_row_claim_id(row)
        amount = _parse_claim_amount(str(row.get("amount") or ""))

        procedure_display = ""
        if procedure_id:
            procedure_display = procedure_code_by_id.get(procedure_id) or procedure_id

        supports = ["ledger", transaction_id]
        if procedure_id:
            supports.append(procedure_id)
        if claim_id:
            supports.append(claim_id)

        text = f"Ledger transaction {transaction_id} for Patient ref {patient_ref}"
        if transaction_date:
            text += f" on {transaction_date}"
        detail_parts: list[str] = []
        if procedure_display:
            detail_parts.append(f"records procedure {procedure_display}")
        if amount is not None:
            detail_parts.append(f"with amount {amount:.2f}")
        if detail_parts:
            text = f"{text} {' '.join(detail_parts)}."
        else:
            text = f"{text}."

        facts.append(
            NarrativeSourceFact(
                fact_id=f"fact-{transaction_id}-ledger",
                source_type="softdent",
                source_label=SOFTDENT_NARRATIVE_PATIENT_LEDGER_FILENAME,
                source_date=source_report_date or transaction_date or None,
                text=text,
                supports=supports,
                source_strength="supporting",
            )
        )
    return facts


class SoftDentExportFileInsuranceNarrativeAdapter:
    """Reads scoped SoftDent narrative CSV exports from a configured import directory.

    No E-Services/Gateway API, no database scraping, and no unrestricted patient dumps.
    """

    def __init__(self, export_dir: str | Path | None = None) -> None:
        self._export_dir = _resolve_softdent_narrative_export_dir(export_dir)

    @property
    def export_dir(self) -> Path:
        return self._export_dir

    @property
    def adapter_name(self) -> str:
        return "softdent_export_file"

    @property
    def source_mode(self) -> str:
        return "export_file"

    def fetch_packet_inputs(self, scope: InsuranceNarrativeScope) -> InsuranceNarrativePacketInputs:
        normalized_ref = _normalize_ref(scope.patient_ref)
        claim_key = (scope.claim_id or "").strip().upper()
        patient_label = f"Patient ref {normalized_ref}"
        missing_data: list[NarrativeMissingDataItem] = [missing_data_item("missing_softdent_ar")]

        claims_path = self._export_dir / SOFTDENT_NARRATIVE_CLAIMS_FILENAME
        procedures_path = self._export_dir / SOFTDENT_NARRATIVE_PROCEDURES_FILENAME

        claim_rows = _read_scoped_export_csv(claims_path)
        procedure_rows = _read_scoped_export_csv(procedures_path)

        if claim_rows is None:
            missing_data.append(missing_data_item("missing_softdent_claims_export"))
            return InsuranceNarrativePacketInputs(
                patient=PatientCaseSummary(
                    patient_ref=normalized_ref,
                    chart_ref=normalized_ref,
                    label=patient_label,
                ),
                claim=ClaimCaseSummary(claim_id=claim_key) if claim_key else None,
                missing_data=_dedupe_missing_data(missing_data),
            )

        if procedure_rows is None:
            missing_data.append(missing_data_item("missing_softdent_procedures_export"))
            procedure_rows = []

        scoped_claim_rows = [
            row
            for row in claim_rows
            if _export_row_patient_ref(row) == normalized_ref
            and (not claim_key or _export_row_claim_id(row) == claim_key)
        ]

        if claim_key and not scoped_claim_rows:
            missing_data.append(missing_data_item("missing_scoped_claim_row"))
            return InsuranceNarrativePacketInputs(
                patient=PatientCaseSummary(
                    patient_ref=normalized_ref,
                    chart_ref=normalized_ref,
                    label=patient_label,
                ),
                claim=ClaimCaseSummary(claim_id=claim_key),
                missing_data=_dedupe_missing_data(missing_data),
            )

        if not claim_key:
            return InsuranceNarrativePacketInputs(
                patient=PatientCaseSummary(
                    patient_ref=normalized_ref,
                    chart_ref=normalized_ref,
                    label=patient_label,
                ),
                missing_data=_dedupe_missing_data(missing_data),
            )

        claim_row = scoped_claim_rows[0]
        claim_summary = ClaimCaseSummary(
            claim_id=claim_key,
            status=str(claim_row.get("claim_status") or "").strip() or None,
            payer_name=str(claim_row.get("payer_name") or "").strip() or None,
            billed_amount=_parse_claim_amount(str(claim_row.get("claim_amount") or "")),
            denial_reason=None,
        )

        claim_procedure_ids = _parse_export_procedure_ids(str(claim_row.get("procedure_ids") or ""))
        expected_procedure_ids = (
            {_normalize_ref(proc_id) for proc_id in (scope.procedure_ids or [])}
            if scope.procedure_ids
            else set(claim_procedure_ids)
        )

        patient_procedure_rows = [
            row for row in procedure_rows if _export_row_patient_ref(row) == normalized_ref
        ]
        matched_procedure_rows = [
            row
            for row in patient_procedure_rows
            if _export_row_procedure_id(row) in expected_procedure_ids
        ]

        if expected_procedure_ids and not matched_procedure_rows:
            missing_data.append(missing_data_item("missing_scoped_procedure_rows"))

        procedures: list[ProcedureCaseSummary] = []
        for row in matched_procedure_rows:
            proc_id = _export_row_procedure_id(row)
            proc = ProcedureCaseSummary(
                procedure_id=proc_id,
                description=str(row.get("procedure_description") or ""),
                code=str(row.get("procedure_code") or "") or None,
                tooth=str(row.get("tooth") or "") or None,
                service_date=str(row.get("service_date") or "") or None,
            )
            if scope.procedure_ids and proc.procedure_id not in scope.procedure_ids:
                continue
            procedures.append(proc)

        source_facts = _build_export_claim_facts(
            patient_ref=normalized_ref,
            claim_id=claim_key,
            claim_row=claim_row,
            procedure_rows=matched_procedure_rows,
            claims_source_label=SOFTDENT_NARRATIVE_CLAIMS_FILENAME,
            procedures_source_label=SOFTDENT_NARRATIVE_PROCEDURES_FILENAME,
        )

        ledger_path = self._export_dir / SOFTDENT_NARRATIVE_PATIENT_LEDGER_FILENAME
        ledger_rows, ledger_error = _load_patient_ledger_export(ledger_path)
        if ledger_error:
            missing_data.append(missing_data_item(ledger_error))
        else:
            scoped_ledger_rows = _scope_ledger_rows(
                ledger_rows,
                patient_ref=normalized_ref,
                claim_id=claim_key,
                procedure_ids=scope.procedure_ids,
                included_procedure_ids=expected_procedure_ids,
                date_range=scope.date_range,
            )
            if not scoped_ledger_rows:
                missing_data.append(missing_data_item("missing_scoped_ledger_rows"))
            else:
                procedure_code_by_id = {
                    _export_row_procedure_id(row): str(row.get("procedure_code") or "").strip()
                    for row in matched_procedure_rows
                    if _export_row_procedure_id(row)
                }
                source_facts.extend(
                    _build_export_ledger_facts(
                        patient_ref=normalized_ref,
                        ledger_rows=scoped_ledger_rows,
                        procedure_code_by_id=procedure_code_by_id,
                    )
                )

        date_range_summary: DateRangeSummary | None = None
        service_dates = [proc.service_date for proc in procedures if proc.service_date]
        claim_service_date = str(claim_row.get("service_date") or "").strip()
        if claim_service_date:
            service_dates.append(claim_service_date)
        if service_dates:
            date_range_summary = DateRangeSummary(start_date=min(service_dates), end_date=max(service_dates))
        if scope.date_range:
            date_range_summary = DateRangeSummary(
                start_date=scope.date_range[0],
                end_date=scope.date_range[1],
            )

        return InsuranceNarrativePacketInputs(
            patient=PatientCaseSummary(
                patient_ref=normalized_ref,
                chart_ref=normalized_ref,
                label=patient_label,
            ),
            claim=claim_summary,
            procedures=procedures,
            date_range=date_range_summary,
            payer_name=claim_summary.payer_name,
            source_facts=source_facts,
            attachments=[],
            missing_data=_dedupe_missing_data(missing_data),
        )


def softdent_export_file_adapter(export_dir: str | Path | None = None) -> SoftDentExportFileInsuranceNarrativeAdapter:
    return SoftDentExportFileInsuranceNarrativeAdapter(export_dir=export_dir)


def _dedupe_missing_data(items: list[NarrativeMissingDataItem]) -> list[NarrativeMissingDataItem]:
    seen: set[str] = set()
    deduped: list[NarrativeMissingDataItem] = []
    for item in items:
        if item.code in seen:
            continue
        seen.add(item.code)
        deduped.append(item)
    return deduped


def build_packet_inputs_from_adapter_scope(
    adapter: InsuranceNarrativeDataAdapter,
    scope: InsuranceNarrativeScope,
) -> InsuranceNarrativePacketInputs:
    """Fetch bounded packet inputs from a scoped adapter."""
    return adapter.fetch_packet_inputs(scope)


def default_fixture_adapter() -> FixtureInsuranceNarrativeDataAdapter:
    return FixtureInsuranceNarrativeDataAdapter()
