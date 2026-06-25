"""Insurance narrative case-packet builder and fast-review helpers."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from app.insurance_narratives.schemas import (
    CASE_PACKET_BUILDER_VERSION,
    CASE_PACKET_SCHEMA_VERSION,
    ClaimCaseSummary,
    DateRangeSummary,
    InsuranceNarrativeCasePacket,
    NarrativeAttachmentSummary,
    NarrativeAuditMetadata,
    NarrativeMissingDataItem,
    NarrativeSourceFact,
    PatientCaseSummary,
    ProcedureCaseSummary,
)

# Deterministic de-identified fixture catalog for tests and local development.
# Keys are patient_ref values. No real PHI — synthetic refs only.
_FIXTURE_CATALOG: dict[str, dict[str, Any]] = {
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

_MISSING_DATA_CATALOG: dict[str, NarrativeMissingDataItem] = {
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


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _deterministic_packet_id(
    *,
    patient_ref: str,
    claim_id: str | None,
    narrative_type: str,
    procedure_ids: list[str] | None,
) -> str:
    seed = "|".join(
        [
            patient_ref.strip().upper(),
            (claim_id or "").strip().upper(),
            narrative_type.strip().lower(),
            ",".join(sorted(procedure_ids or [])),
        ]
    )
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
    return f"narrative-packet-{digest}"


def _missing_item(code: str) -> NarrativeMissingDataItem:
    if code not in _MISSING_DATA_CATALOG:
        return NarrativeMissingDataItem(
            code=code,
            label=code.replace("_", " "),
            severity="warning",
            why_it_matters="Required supporting data is unavailable in approved exports.",
            blocking=False,
        )
    return _MISSING_DATA_CATALOG[code].model_copy(deep=True)


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


def build_insurance_narrative_case_packet(
    *,
    patient_ref: str,
    claim_id: str | None = None,
    procedure_ids: list[str] | None = None,
    date_range: tuple[str, str] | None = None,
    narrative_type: str,
    actor: str,
    created_at: str | None = None,
) -> InsuranceNarrativeCasePacket:
    """Build a bounded, patient/claim-scoped case packet from approved fixture exports.

    This foundation builder uses deterministic de-identified fixtures only. It does not
    dump unrestricted database rows, invent clinical facts, or synthesize A/R values.
    """

    normalized_ref = patient_ref.strip().upper()
    timestamp = created_at or _utc_now_iso()
    packet_id = _deterministic_packet_id(
        patient_ref=normalized_ref,
        claim_id=claim_id,
        narrative_type=narrative_type,
        procedure_ids=procedure_ids,
    )

    patient_fixture = _FIXTURE_CATALOG.get(normalized_ref)
    if patient_fixture is None:
        return InsuranceNarrativeCasePacket(
            packet_id=packet_id,
            created_at=timestamp,
            actor=actor,
            narrative_type=narrative_type,
            patient=PatientCaseSummary(
                patient_ref=normalized_ref,
                chart_ref=normalized_ref,
                label=f"Patient ref {normalized_ref}",
            ),
            claim=None,
            procedures=[],
            date_range=None,
            payer_name=None,
            source_facts=[],
            attachments=[],
            missing_data=[_missing_item("missing_patient_record")],
            audit_metadata=NarrativeAuditMetadata(
                created_at=timestamp,
                created_by=actor,
                builder_version=CASE_PACKET_BUILDER_VERSION,
                schema_version=CASE_PACKET_SCHEMA_VERSION,
            ),
        )

    claims: dict[str, Any] = patient_fixture.get("claims") or {}
    claim_key = (claim_id or "").strip().upper()
    claim_fixture = claims.get(claim_key) if claim_key else None

    if claim_key and claim_fixture is None:
        return InsuranceNarrativeCasePacket(
            packet_id=packet_id,
            created_at=timestamp,
            actor=actor,
            narrative_type=narrative_type,
            patient=PatientCaseSummary(
                patient_ref=normalized_ref,
                chart_ref=normalized_ref,
                label=str(patient_fixture.get("patient_label") or f"Patient ref {normalized_ref}"),
            ),
            claim=ClaimCaseSummary(claim_id=claim_key),
            procedures=[],
            date_range=None,
            payer_name=None,
            source_facts=[],
            attachments=[],
            missing_data=[_missing_item("missing_claim_record"), _missing_item("missing_claim_status")],
            audit_metadata=NarrativeAuditMetadata(
                created_at=timestamp,
                created_by=actor,
                builder_version=CASE_PACKET_BUILDER_VERSION,
                schema_version=CASE_PACKET_SCHEMA_VERSION,
            ),
        )

    procedures: list[ProcedureCaseSummary] = []
    source_facts: list[NarrativeSourceFact] = []
    attachments: list[NarrativeAttachmentSummary] = []
    missing_data: list[NarrativeMissingDataItem] = []
    claim_summary: ClaimCaseSummary | None = None
    payer_name: str | None = None
    date_range_summary: DateRangeSummary | None = None

    if claim_fixture:
        claim_summary = ClaimCaseSummary(
            claim_id=claim_key,
            status=str(claim_fixture.get("status") or "") or None,
            payer_name=str(claim_fixture.get("payer_name") or "") or None,
            billed_amount=claim_fixture.get("billed_amount"),
            denial_reason=str(claim_fixture.get("denial_reason") or "") or None,
        )
        payer_name = claim_summary.payer_name
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
        for code in claim_fixture.get("missing_codes") or []:
            missing_data.append(_missing_item(str(code)))
        for attachment_label in claim_fixture.get("attachments_available") or []:
            attachments.append(
                NarrativeAttachmentSummary(
                    attachment_id=f"att-{attachment_label.lower().replace(' ', '-')}",
                    label=str(attachment_label),
                    attachment_type="supporting_document",
                    available=True,
                )
            )
        service_dates = [proc.service_date for proc in procedures if proc.service_date]
        if service_dates:
            start = min(service_dates)
            end = max(service_dates)
            date_range_summary = DateRangeSummary(start_date=start, end_date=end)

    if date_range:
        date_range_summary = DateRangeSummary(start_date=date_range[0], end_date=date_range[1])

    return InsuranceNarrativeCasePacket(
        packet_id=packet_id,
        created_at=timestamp,
        actor=actor,
        narrative_type=narrative_type,
        patient=PatientCaseSummary(
            patient_ref=normalized_ref,
            chart_ref=normalized_ref,
            label=str(patient_fixture.get("patient_label") or f"Patient ref {normalized_ref}"),
        ),
        claim=claim_summary,
        procedures=procedures,
        date_range=date_range_summary,
        payer_name=payer_name,
        source_facts=source_facts,
        attachments=attachments,
        missing_data=missing_data,
        audit_metadata=NarrativeAuditMetadata(
            created_at=timestamp,
            created_by=actor,
            builder_version=CASE_PACKET_BUILDER_VERSION,
            schema_version=CASE_PACKET_SCHEMA_VERSION,
        ),
    )


def case_packet_to_fast_review_source_text(packet: InsuranceNarrativeCasePacket) -> str:
    """Convert a bounded case packet into deterministic source text for the opt-in fast_review checker."""

    lines = [
        f"Insurance narrative case packet: {packet.packet_id}",
        f"Narrative type: {packet.narrative_type}",
        f"Patient ref: {packet.patient.patient_ref} ({packet.patient.label})",
    ]
    if packet.claim:
        lines.append(f"Claim: {packet.claim.claim_id} status {packet.claim.status or 'unknown'}")
        if packet.claim.payer_name:
            lines.append(f"Payer: {packet.claim.payer_name}")
        if packet.claim.billed_amount is not None:
            lines.append(f"Billed amount: {packet.claim.billed_amount:.2f}")
        if packet.claim.denial_reason:
            lines.append(f"Denial note: {packet.claim.denial_reason}")
    if packet.date_range:
        lines.append(
            f"Date range: {packet.date_range.start_date} to {packet.date_range.end_date}"
        )
    if packet.procedures:
        lines.append("Procedures:")
        for procedure in packet.procedures:
            lines.append(
                f"- {procedure.procedure_id}: {procedure.description} "
                f"tooth {procedure.tooth or 'n/a'} on {procedure.service_date or 'n/a'}"
            )
    if packet.attachments:
        lines.append("Attachments:")
        for attachment in packet.attachments:
            lines.append(
                f"- {attachment.attachment_id}: {attachment.label} "
                f"({'available' if attachment.available else 'unavailable'})"
            )
    if packet.source_facts:
        lines.append("Source facts:")
        for fact in packet.source_facts:
            date_suffix = f" date {fact.source_date}" if fact.source_date else ""
            lines.append(
                f"- [{fact.fact_id}] ({fact.source_type}/{fact.source_label}){date_suffix}: {fact.text}"
            )
    if packet.missing_data:
        lines.append("Missing data (unavailable — not zero):")
        for item in packet.missing_data:
            lines.append(
                f"- {item.code}: {item.label} "
                f"(severity={item.severity}, blocking={item.blocking}) — {item.why_it_matters}"
            )
    else:
        lines.append("Missing data: none flagged in this packet.")
    lines.append(
        "Rules: use only the facts above. Do not invent clinical, financial, or identity details. "
        "Missing exports are unavailable, not $0."
    )
    return "\n".join(lines)
