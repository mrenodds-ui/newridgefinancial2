"""Insurance narrative case-packet builder and fast-review helpers."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from app.insurance_narratives.data_adapter import (
    InsuranceNarrativeDataAdapter,
    InsuranceNarrativeScope,
    build_packet_inputs_from_adapter_scope,
    default_fixture_adapter,
)
from app.insurance_narratives.schemas import (
    CASE_PACKET_BUILDER_VERSION,
    CASE_PACKET_SCHEMA_VERSION,
    InsuranceNarrativeCasePacket,
    NarrativeAuditMetadata,
)


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


def _resolve_adapter(adapter: InsuranceNarrativeDataAdapter | None) -> InsuranceNarrativeDataAdapter:
    if adapter is None:
        return default_fixture_adapter()
    return adapter


def build_insurance_narrative_case_packet(
    *,
    patient_ref: str,
    claim_id: str | None = None,
    procedure_ids: list[str] | None = None,
    date_range: tuple[str, str] | None = None,
    narrative_type: str,
    actor: str,
    created_at: str | None = None,
    adapter: InsuranceNarrativeDataAdapter | None = None,
) -> InsuranceNarrativeCasePacket:
    """Build a bounded, patient/claim-scoped case packet via a scoped data adapter.

    When ``adapter`` is ``None``, the deterministic fixture adapter is used (existing test
    behavior). Explicit adapters must return bounded ``InsuranceNarrativePacketInputs`` only —
    no raw database rows, invented clinical facts, or synthesized A/R values.
    """

    normalized_ref = patient_ref.strip().upper()
    timestamp = created_at or _utc_now_iso()
    packet_id = _deterministic_packet_id(
        patient_ref=normalized_ref,
        claim_id=claim_id,
        narrative_type=narrative_type,
        procedure_ids=procedure_ids,
    )

    resolved_adapter = _resolve_adapter(adapter)
    scope = InsuranceNarrativeScope(
        patient_ref=normalized_ref,
        claim_id=claim_id,
        procedure_ids=procedure_ids,
        date_range=date_range,
        narrative_type=narrative_type,
        actor=actor,
    )
    inputs = build_packet_inputs_from_adapter_scope(resolved_adapter, scope)

    return InsuranceNarrativeCasePacket(
        packet_id=packet_id,
        created_at=timestamp,
        actor=actor,
        narrative_type=narrative_type,
        patient=inputs.patient,
        claim=inputs.claim,
        procedures=inputs.procedures,
        date_range=inputs.date_range,
        payer_name=inputs.payer_name,
        source_facts=inputs.source_facts,
        attachments=inputs.attachments,
        missing_data=inputs.missing_data,
        audit_metadata=NarrativeAuditMetadata(
            created_at=timestamp,
            created_by=actor,
            builder_version=CASE_PACKET_BUILDER_VERSION,
            schema_version=CASE_PACKET_SCHEMA_VERSION,
            adapter_name=resolved_adapter.adapter_name,
            source_mode=resolved_adapter.source_mode,
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
    if packet.audit_metadata.adapter_name:
        lines.append(
            f"Data adapter: {packet.audit_metadata.adapter_name} "
            f"(source_mode={packet.audit_metadata.source_mode})"
        )
    lines.append(
        "Rules: use only the facts above. Do not invent clinical, financial, or identity details. "
        "Missing exports are unavailable, not $0."
    )
    return "\n".join(lines)
