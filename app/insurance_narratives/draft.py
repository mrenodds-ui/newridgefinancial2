"""Template-based insurance narrative drafting from bounded case packets."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from app.insurance_narratives.case_packet import case_packet_to_fast_review_source_text
from app.insurance_narratives.schemas import (
    InsuranceNarrativeCasePacket,
    InsuranceNarrativeDraft,
    NarrativeDraftAuditMetadata,
    NarrativeDraftCitation,
    NarrativeDraftSection,
    NarrativeDraftWarning,
    NarrativeMissingDataItem,
    NARRATIVE_DRAFT_VERSION,
)

_SECTION_PURPOSE = "purpose"
_SECTION_CASE_SUMMARY = "case_summary"
_SECTION_SUPPORTING_FACTS = "supporting_facts"
_SECTION_MISSING_LIMITATIONS = "missing_limitations"
_SECTION_RECOMMENDED_NEXT_STEP = "recommended_next_step"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _deterministic_draft_id(packet_id: str) -> str:
    digest = hashlib.sha256(packet_id.encode("utf-8")).hexdigest()[:16]
    return f"narrative-draft-{digest}"


def _fact_lookup(packet: InsuranceNarrativeCasePacket) -> dict[str, object]:
    return {fact.fact_id: fact for fact in packet.source_facts}


def _cite(fact_id: str, section_key: str, excerpt: str) -> NarrativeDraftCitation:
    return NarrativeDraftCitation(fact_id=fact_id, section_key=section_key, excerpt=excerpt)


def _build_purpose_section(packet: InsuranceNarrativeCasePacket) -> NarrativeDraftSection:
    body = (
        f"Prepare a human-reviewed insurance narrative for narrative type "
        f"'{packet.narrative_type}' using only the bounded case packet "
        f"{packet.packet_id}. This draft does not auto-submit to any payer."
    )
    return NarrativeDraftSection(key=_SECTION_PURPOSE, title="Purpose", body=body)


def _build_case_summary_section(
    packet: InsuranceNarrativeCasePacket,
    citations: list[NarrativeDraftCitation],
) -> NarrativeDraftSection:
    lines: list[str] = [f"Patient scope: {packet.patient.label} (ref {packet.patient.patient_ref})."]
    facts_by_id = _fact_lookup(packet)

    if packet.claim:
        lines.append(f"Claim scope: {packet.claim.claim_id}.")
        status_fact_id = f"fact-{packet.patient.patient_ref}-claim-status"
        if status_fact_id in facts_by_id:
            fact = facts_by_id[status_fact_id]
            sentence = str(fact.text)
            lines.append(f"{sentence} [{status_fact_id}]")
            citations.append(_cite(status_fact_id, _SECTION_CASE_SUMMARY, sentence))
        payer_fact_id = f"fact-{packet.patient.patient_ref}-payer"
        if payer_fact_id in facts_by_id:
            fact = facts_by_id[payer_fact_id]
            sentence = str(fact.text)
            lines.append(f"{sentence} [{payer_fact_id}]")
            citations.append(_cite(payer_fact_id, _SECTION_CASE_SUMMARY, sentence))

    if packet.date_range:
        lines.append(
            f"Service window in packet: {packet.date_range.start_date} to {packet.date_range.end_date}."
        )

    return NarrativeDraftSection(
        key=_SECTION_CASE_SUMMARY,
        title="Case Summary",
        body="\n".join(lines),
    )


def _build_supporting_facts_section(
    packet: InsuranceNarrativeCasePacket,
    citations: list[NarrativeDraftCitation],
) -> NarrativeDraftSection:
    if not packet.source_facts:
        body = "No supporting source facts are present in this packet."
        return NarrativeDraftSection(
            key=_SECTION_SUPPORTING_FACTS,
            title="Supporting Facts",
            body=body,
        )

    lines: list[str] = []
    for fact in packet.source_facts:
        sentence = f"{fact.text} [{fact.fact_id}]"
        lines.append(sentence)
        citations.append(_cite(fact.fact_id, _SECTION_SUPPORTING_FACTS, fact.text))
    return NarrativeDraftSection(
        key=_SECTION_SUPPORTING_FACTS,
        title="Supporting Facts",
        body="\n".join(lines),
    )


def _build_missing_limitations_section(packet: InsuranceNarrativeCasePacket) -> NarrativeDraftSection:
    if not packet.missing_data:
        body = "No missing-data limitations were flagged in this packet."
        return NarrativeDraftSection(
            key=_SECTION_MISSING_LIMITATIONS,
            title="Missing Information / Limitations",
            body=body,
        )

    lines = [
        "The following exports or references are unavailable in the approved packet scope "
        "(unavailable means not provided — not $0):"
    ]
    for item in packet.missing_data:
        blocking_label = "blocking" if item.blocking else "non-blocking"
        lines.append(
            f"- {item.code}: {item.label} ({blocking_label}, severity={item.severity}). "
            f"{item.why_it_matters}"
        )
    return NarrativeDraftSection(
        key=_SECTION_MISSING_LIMITATIONS,
        title="Missing Information / Limitations",
        body="\n".join(lines),
    )


def _build_recommended_next_step_section(
    packet: InsuranceNarrativeCasePacket,
    *,
    blocked: bool,
) -> NarrativeDraftSection:
    if blocked:
        blocking_codes = ", ".join(item.code for item in packet.missing_data if item.blocking)
        body = (
            "Resolve blocking missing-data items before payer submission: "
            f"{blocking_codes or 'see missing limitations'}. "
            "Staff must verify supporting documentation and approve any narrative text."
        )
    elif packet.missing_data:
        body = (
            "Review non-blocking missing-data limitations with staff. "
            "Complete human approval before any payer submission."
        )
    else:
        body = (
            "Complete human review and approval before any payer submission. "
            "Verify cited facts against approved exports."
        )
    return NarrativeDraftSection(
        key=_SECTION_RECOMMENDED_NEXT_STEP,
        title="Recommended Next Step",
        body=body,
    )


def _build_warnings(packet: InsuranceNarrativeCasePacket) -> list[NarrativeDraftWarning]:
    warnings: list[NarrativeDraftWarning] = []
    for item in packet.missing_data:
        if item.blocking:
            continue
        warnings.append(
            NarrativeDraftWarning(
                code=item.code,
                message=f"{item.label} is unavailable in the packet. {item.why_it_matters}",
                severity=item.severity,
            )
        )
    return warnings


def draft_insurance_narrative_from_packet(
    packet: InsuranceNarrativeCasePacket,
    *,
    actor: str,
    created_at: str | None = None,
) -> InsuranceNarrativeDraft:
    """Create a conservative template draft from a bounded case packet only."""

    timestamp = created_at or _utc_now_iso()
    citations: list[NarrativeDraftCitation] = []
    missing_data = [item.model_copy(deep=True) for item in packet.missing_data]
    blocked = any(item.blocking for item in missing_data)
    status = "blocked_missing_data" if blocked else "ready_for_human_review"

    sections = [
        _build_purpose_section(packet),
        _build_case_summary_section(packet, citations),
        _build_supporting_facts_section(packet, citations),
        _build_missing_limitations_section(packet),
        _build_recommended_next_step_section(packet, blocked=blocked),
    ]

    return InsuranceNarrativeDraft(
        draft_id=_deterministic_draft_id(packet.packet_id),
        packet_id=packet.packet_id,
        narrative_type=packet.narrative_type,
        status=status,
        sections=sections,
        citations=citations,
        warnings=_build_warnings(packet),
        missing_data=missing_data,
        created_at=timestamp,
        actor=actor,
        approval_required=True,
        audit_metadata=NarrativeDraftAuditMetadata(
            created_at=timestamp,
            created_by=actor,
            drafter_version=NARRATIVE_DRAFT_VERSION,
        ),
    )


def draft_to_fast_review_source_text(
    packet: InsuranceNarrativeCasePacket,
    draft: InsuranceNarrativeDraft,
) -> str:
    """Prepare deterministic checker input from a packet and its template draft."""

    lines = [
        case_packet_to_fast_review_source_text(packet),
        "",
        f"Insurance narrative draft: {draft.draft_id}",
        f"Draft status: {draft.status}",
        f"Approval required: {draft.approval_required}",
        "",
        "Draft sections:",
    ]
    for section in draft.sections:
        lines.append(f"## {section.title}")
        lines.append(section.body)
        lines.append("")

    if draft.citations:
        lines.append("Draft citations:")
        for citation in draft.citations:
            lines.append(
                f"- {citation.fact_id} ({citation.section_key}): {citation.excerpt}"
            )
        lines.append("")

    if draft.warnings:
        lines.append("Draft warnings:")
        for warning in draft.warnings:
            lines.append(f"- {warning.code} ({warning.severity}): {warning.message}")
        lines.append("")

    if draft.missing_data:
        lines.append("Draft missing-data codes:")
        for item in draft.missing_data:
            lines.append(
                f"- {item.code} blocking={item.blocking} severity={item.severity}: {item.label}"
            )
        lines.append("")

    lines.append(
        "Checker rules: verify draft sentences against packet fact_ids only. "
        "Flag invented facts, citation gaps, and any treatment of missing A/R as zero."
    )
    return "\n".join(lines).strip()
