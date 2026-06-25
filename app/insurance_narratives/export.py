"""Local export formatting for approved insurance narrative drafts."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from app.insurance_narratives.schemas import (
    InsuranceNarrativeCasePacket,
    InsuranceNarrativeDraft,
    InsuranceNarrativeExport,
    InsuranceNarrativeReviewRecord,
    NarrativeDraftCitation,
    NarrativeExportApprovalSummary,
    NarrativeExportAuditMetadata,
    NarrativeExportFormat,
    NarrativeExportSection,
    NarrativeMissingDataItem,
)

_APPROVAL_ATTESTATION_TEXT = (
    "Reviewer confirms: (1) draft was reviewed by a human, "
    "(2) citations and source facts were checked, "
    "(3) missing-data limitations were considered, and "
    "(4) this export is not automatically submitted to any payer."
)


class NarrativeExportWorkflowError(ValueError):
    """Raised when export preconditions are not met."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _deterministic_export_id(review_id: str) -> str:
    digest = hashlib.sha256(review_id.encode("utf-8")).hexdigest()[:16]
    return f"narrative-export-{digest}"


def _require_actor(actor: str) -> str:
    normalized = actor.strip()
    if not normalized:
        raise NarrativeExportWorkflowError("actor is required")
    return normalized


def _assert_lineage(
    *,
    packet: InsuranceNarrativeCasePacket,
    draft: InsuranceNarrativeDraft,
    review: InsuranceNarrativeReviewRecord,
) -> None:
    if draft.packet_id != packet.packet_id:
        raise NarrativeExportWorkflowError("draft.packet_id does not match packet.packet_id")
    if review.packet_id != packet.packet_id:
        raise NarrativeExportWorkflowError("review.packet_id does not match packet.packet_id")
    if review.draft_id != draft.draft_id:
        raise NarrativeExportWorkflowError("review.draft_id does not match draft.draft_id")


def _assert_exportable(
    *,
    draft: InsuranceNarrativeDraft,
    review: InsuranceNarrativeReviewRecord,
) -> None:
    if review.status != "approved":
        raise NarrativeExportWorkflowError(
            f"only approved reviews can be exported (status={review.status!r})"
        )
    if review.approval_attestation is not True:
        raise NarrativeExportWorkflowError("approval_attestation must be true to export")
    if draft.status == "blocked_missing_data":
        raise NarrativeExportWorkflowError(
            "cannot export a draft with status 'blocked_missing_data'"
        )
    if review.draft_status == "blocked_missing_data":
        raise NarrativeExportWorkflowError(
            "cannot export a review tied to blocked_missing_data draft status"
        )


def _normalize_format(export_format: str) -> NarrativeExportFormat:
    normalized = export_format.strip().lower()
    if normalized not in ("plain_text", "markdown"):
        raise NarrativeExportWorkflowError(
            f"unsupported export_format {export_format!r}; use 'markdown' or 'plain_text'"
        )
    return normalized  # type: ignore[return-value]


def _fact_lookup(packet: InsuranceNarrativeCasePacket) -> dict[str, object]:
    return {fact.fact_id: fact for fact in packet.source_facts}


def _format_citation_line(
    citation: NarrativeDraftCitation,
    packet: InsuranceNarrativeCasePacket,
    *,
    markdown: bool,
) -> str:
    facts_by_id = _fact_lookup(packet)
    fact = facts_by_id.get(citation.fact_id)
    if fact is None:
        label = "unknown source"
        date_part = ""
        text = citation.excerpt
    else:
        label = str(getattr(fact, "source_label", "source"))
        source_date = getattr(fact, "source_date", None)
        date_part = f" ({source_date})" if source_date else ""
        text = str(getattr(fact, "text", citation.excerpt))

    prefix = "- " if markdown else "* "
    bracket_open = "[" if markdown else "["
    bracket_close = "]" if markdown else "]"
    return f"{prefix}{bracket_open}{citation.fact_id}{bracket_close} {label}{date_part}: {text}"


def _format_missing_data_line(item: NarrativeMissingDataItem, *, markdown: bool) -> str:
    prefix = "- " if markdown else "* "
    return f"{prefix}{item.code}: {item.label} — {item.why_it_matters}"


def _build_narrative_sections(draft: InsuranceNarrativeDraft) -> list[NarrativeExportSection]:
    return [
        NarrativeExportSection(key=section.key, title=section.title, body=section.body)
        for section in draft.sections
    ]


def _build_approval_summary(review: InsuranceNarrativeReviewRecord) -> NarrativeExportApprovalSummary:
    if not review.reviewed_at:
        raise NarrativeExportWorkflowError("approved review must include reviewed_at")
    return NarrativeExportApprovalSummary(
        reviewer=review.reviewer,
        reviewed_at=review.reviewed_at,
        notes=review.notes,
        attestation_confirmed=True,
        attestation_text=_APPROVAL_ATTESTATION_TEXT,
    )


def _render_body(
    *,
    draft: InsuranceNarrativeDraft,
    packet: InsuranceNarrativeCasePacket,
    review: InsuranceNarrativeReviewRecord,
    export_format: NarrativeExportFormat,
    title: str,
    approval_summary: NarrativeExportApprovalSummary,
    missing_data_disclosures: list[NarrativeMissingDataItem],
    citations: list[NarrativeDraftCitation],
) -> str:
    markdown = export_format == "markdown"
    lines: list[str] = []

    if markdown:
        lines.append(f"# {title}")
        lines.append("")
        lines.append("## Narrative")
    else:
        lines.append(title)
        lines.append("=" * len(title))
        lines.append("")
        lines.append("Narrative")
        lines.append("-" * 9)

    for section in draft.sections:
        if markdown:
            lines.append("")
            lines.append(f"### {section.title}")
        else:
            lines.append("")
            lines.append(section.title)
            lines.append("-" * len(section.title))
        lines.append(section.body)

    if markdown:
        lines.append("")
        lines.append("## Citations")
    else:
        lines.append("")
        lines.append("Citations")
        lines.append("-" * 9)

    if citations:
        for citation in citations:
            lines.append(_format_citation_line(citation, packet, markdown=markdown))
    else:
        lines.append("- None listed." if markdown else "* None listed.")

    if markdown:
        lines.append("")
        lines.append("## Missing Data / Limitations")
    else:
        lines.append("")
        lines.append("Missing Data / Limitations")
        lines.append("-" * 28)

    if missing_data_disclosures:
        for item in missing_data_disclosures:
            lines.append(_format_missing_data_line(item, markdown=markdown))
    else:
        lines.append("- None flagged." if markdown else "* None flagged.")

    if markdown:
        lines.append("")
        lines.append("## Approval")
    else:
        lines.append("")
        lines.append("Approval")
        lines.append("-" * 8)

    lines.append(f"Reviewer: {approval_summary.reviewer}")
    lines.append(f"Reviewed at: {approval_summary.reviewed_at}")
    if approval_summary.notes:
        lines.append(f"Notes: {approval_summary.notes}")
    lines.append(f"Attestation: {approval_summary.attestation_text}")
    lines.append(f"Review id: {review.review_id}")

    if markdown:
        lines.append("")
        lines.append("## Submission Status")
    else:
        lines.append("")
        lines.append("Submission Status")
        lines.append("-" * 17)

    lines.append("Not submitted")

    return "\n".join(lines).strip()


def export_approved_insurance_narrative(
    *,
    packet: InsuranceNarrativeCasePacket,
    draft: InsuranceNarrativeDraft,
    review: InsuranceNarrativeReviewRecord,
    actor: str,
    export_format: str = "markdown",
    created_at: str | None = None,
) -> InsuranceNarrativeExport:
    """Format an approved narrative draft for local human copy/review only.

    Does not submit, email, fax, upload, or write to disk.
    """

    actor_id = _require_actor(actor)
    fmt = _normalize_format(export_format)
    _assert_lineage(packet=packet, draft=draft, review=review)
    _assert_exportable(draft=draft, review=review)

    timestamp = created_at or _utc_now_iso()
    title = f"Insurance Narrative Export — {packet.narrative_type}"
    citations = [citation.model_copy(deep=True) for citation in draft.citations]
    missing_data_disclosures = [item.model_copy(deep=True) for item in draft.missing_data]
    approval_summary = _build_approval_summary(review)
    sections = _build_narrative_sections(draft)
    body = _render_body(
        draft=draft,
        packet=packet,
        review=review,
        export_format=fmt,
        title=title,
        approval_summary=approval_summary,
        missing_data_disclosures=missing_data_disclosures,
        citations=citations,
    )

    return InsuranceNarrativeExport(
        export_id=_deterministic_export_id(review.review_id),
        packet_id=packet.packet_id,
        draft_id=draft.draft_id,
        review_id=review.review_id,
        format=fmt,
        title=title,
        body=body,
        sections=sections,
        citations=citations,
        missing_data_disclosures=missing_data_disclosures,
        approval_summary=approval_summary,
        audit_metadata=NarrativeExportAuditMetadata(
            created_at=timestamp,
            created_by=actor_id,
        ),
        created_at=timestamp,
        actor=actor_id,
        submission_status="not_submitted",
    )
