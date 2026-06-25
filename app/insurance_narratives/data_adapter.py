"""Scoped data adapters for insurance narrative case packets."""

from __future__ import annotations

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
}


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
) -> list[NarrativeSourceFact]:
    facts: list[NarrativeSourceFact] = []
    facts.append(
        NarrativeSourceFact(
            fact_id=f"fact-{patient_ref}-claim-status",
            source_type="claim",
            source_label=f"Claim {claim_id} status",
            source_date=None,
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
                source_label="Payer",
                source_date=None,
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
                source_label="Payer denial note",
                source_date=None,
                text=str(claim["denial_reason"]),
                supports=[claim_id],
                source_strength="primary",
            )
        )
    for procedure in claim.get("procedures") or []:
        proc_id = str(procedure.get("procedure_id") or "")
        facts.append(
            NarrativeSourceFact(
                fact_id=f"fact-{proc_id}-procedure",
                source_type="softdent",
                source_label="Procedure",
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
                    source_label="Billed amount",
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
                source_label="Clinical note excerpt",
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


def _build_local_claim_facts(
    *,
    patient_ref: str,
    claim_id: str,
    claim_rows: list[dict[str, Any]],
    note_excerpt: str | None,
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
        "billed_amount": primary.get("ClaimAmount"),
        "procedures": [
            {
                "procedure_id": _procedure_id_from_row(row, index=index),
                "description": str(row.get("Procedure") or row.get("procedure") or ""),
                "tooth": row.get("Tooth") or row.get("tooth"),
                "service_date": str(row.get("ServiceDate") or row.get("servicedate") or "") or None,
            }
            for index, row in enumerate(claim_rows, start=1)
        ],
        "clinical_note_excerpt": note_excerpt,
    }
    return _build_source_facts_for_claim(
        patient_ref=patient_ref,
        claim_id=claim_id,
        claim=claim_payload,
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
        return "local_export"

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

        scoped_claim_rows = [
            row for row in patient_rows if _row_matches_claim_id(row, claim_key)
        ]
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
        patient_notes = [row for row in note_rows if _row_matches_patient_ref(row, normalized_ref)]
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
            billed_amount=primary.get("ClaimAmount"),
            denial_reason=str(primary.get("DenialReason") or primary.get("denialreason") or "") or None,
        )
        procedures: list[ProcedureCaseSummary] = []
        for index, row in enumerate(scoped_claim_rows, start=1):
            proc = ProcedureCaseSummary(
                procedure_id=_procedure_id_from_row(row, index=index),
                description=str(row.get("Procedure") or row.get("procedure") or ""),
                code=row.get("Code") or row.get("code"),
                tooth=row.get("Tooth") or row.get("tooth"),
                service_date=str(row.get("ServiceDate") or row.get("servicedate") or "") or None,
            )
            if scope.procedure_ids and proc.procedure_id not in scope.procedure_ids:
                continue
            procedures.append(proc)

        source_facts = _build_local_claim_facts(
            patient_ref=normalized_ref,
            claim_id=claim_key,
            claim_rows=scoped_claim_rows,
            note_excerpt=note_excerpt,
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
