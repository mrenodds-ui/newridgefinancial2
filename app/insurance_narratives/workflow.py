"""Orchestrated local workflow facade for insurance narrative pipelines."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.insurance_narratives.case_packet import build_insurance_narrative_case_packet
from app.insurance_narratives.draft import (
    draft_insurance_narrative_from_packet,
    draft_to_fast_review_source_text,
)
from app.insurance_narratives.export import export_approved_insurance_narrative
from app.insurance_narratives.review import (
    approve_narrative_draft,
    checker_result_to_summary,
    create_narrative_review_record,
)
from app.hal.fast_review_checker import run_fast_review_check
from app.insurance_narratives.schemas import (
    InsuranceNarrativeCasePacket,
    InsuranceNarrativeDraft,
    InsuranceNarrativeWorkflowResult,
    InsuranceNarrativeWorkflowStatus,
    NarrativeCheckerSummary,
    NarrativeWorkflowAuditEvent,
    NarrativeWorkflowWarning,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _workflow_audit(
    *,
    event_type: str,
    at: str,
    actor: str,
    detail: str | None = None,
) -> NarrativeWorkflowAuditEvent:
    return NarrativeWorkflowAuditEvent(
        event_type=event_type,
        at=at,
        actor=actor,
        detail=detail,
    )


def _review_audit_to_workflow_events(
    review_events: list[Any],
) -> list[NarrativeWorkflowAuditEvent]:
    converted: list[NarrativeWorkflowAuditEvent] = []
    for event in review_events:
        converted.append(
            NarrativeWorkflowAuditEvent(
                event_type=f"review:{event.event_type}",
                at=event.at,
                actor=event.actor,
                detail=event.notes,
            )
        )
    return converted


def _resolve_draft_workflow_status(
    *,
    draft: InsuranceNarrativeDraft,
    run_checker: bool,
    checker_status: str | None,
) -> InsuranceNarrativeWorkflowStatus:
    if draft.status == "blocked_missing_data":
        return "blocked_missing_data"
    if not run_checker:
        return "draft_created"
    if checker_status == "ok":
        return "checker_completed"
    if checker_status == "lane_unavailable":
        return "checker_unavailable"
    return "checker_completed"


def create_insurance_narrative_draft_workflow(
    *,
    patient_ref: str,
    claim_id: str | None = None,
    procedure_ids: list[str] | None = None,
    date_range: tuple[str, str] | None = None,
    narrative_type: str,
    actor: str,
    created_at: str | None = None,
    run_checker: bool = False,
) -> InsuranceNarrativeWorkflowResult:
    """Build a bounded packet and template draft; optionally run the opt-in checker."""

    timestamp = created_at or _utc_now_iso()
    audit_events = [
        _workflow_audit(
            event_type="workflow_started",
            at=timestamp,
            actor=actor,
            detail="create_insurance_narrative_draft_workflow",
        )
    ]
    warnings: list[NarrativeWorkflowWarning] = []

    packet = build_insurance_narrative_case_packet(
        patient_ref=patient_ref,
        claim_id=claim_id,
        procedure_ids=procedure_ids,
        date_range=date_range,
        narrative_type=narrative_type,
        actor=actor,
        created_at=timestamp,
    )
    audit_events.append(
        _workflow_audit(
            event_type="packet_created",
            at=timestamp,
            actor=actor,
            detail=packet.packet_id,
        )
    )

    draft = draft_insurance_narrative_from_packet(packet, actor=actor, created_at=timestamp)
    audit_events.append(
        _workflow_audit(
            event_type="draft_created",
            at=timestamp,
            actor=actor,
            detail=draft.draft_id,
        )
    )

    checker_summary: NarrativeCheckerSummary | None = None
    checker_status: str | None = None
    if run_checker:
        source_text = draft_to_fast_review_source_text(packet, draft)
        check_result = run_fast_review_check(
            source_text=source_text,
            packet_id=packet.packet_id,
            actor=actor,
        )
        checker_summary = checker_result_to_summary(check_result)
        checker_status = str(check_result.get("status") or "")
        audit_events.append(
            _workflow_audit(
                event_type="checker_invoked",
                at=timestamp,
                actor=actor,
                detail=checker_status,
            )
        )
        if checker_status == "lane_unavailable":
            warnings.append(
                NarrativeWorkflowWarning(
                    code="checker_unavailable",
                    message=str(check_result.get("error") or "fast_review lane unavailable"),
                )
            )
        elif checker_status not in ("ok",):
            warnings.append(
                NarrativeWorkflowWarning(
                    code="checker_advisory",
                    message=f"fast_review returned status={checker_status!r}; advisory only",
                )
            )

    status = _resolve_draft_workflow_status(
        draft=draft,
        run_checker=run_checker,
        checker_status=checker_status,
    )

    return InsuranceNarrativeWorkflowResult(
        packet=packet,
        draft=draft,
        checker_summary=checker_summary,
        status=status,
        warnings=warnings,
        audit_events=audit_events,
    )


def approve_and_export_insurance_narrative_workflow(
    *,
    packet: InsuranceNarrativeCasePacket,
    draft: InsuranceNarrativeDraft,
    reviewer: str,
    notes: str,
    approval_attestation: bool,
    actor: str,
    export_format: str = "markdown",
    reviewed_at: str | None = None,
    created_at: str | None = None,
    checker_summary: NarrativeCheckerSummary | dict[str, Any] | None = None,
) -> InsuranceNarrativeWorkflowResult:
    """Create review, approve, and format export locally. Does not submit to payers."""

    timestamp = created_at or _utc_now_iso()
    review_timestamp = reviewed_at or timestamp
    audit_events = [
        _workflow_audit(
            event_type="workflow_started",
            at=timestamp,
            actor=actor,
            detail="approve_and_export_insurance_narrative_workflow",
        )
    ]
    warnings: list[NarrativeWorkflowWarning] = []

    review = create_narrative_review_record(
        draft,
        reviewer=reviewer,
        created_at=review_timestamp,
        checker_summary=checker_summary,
    )
    audit_events.append(
        _workflow_audit(
            event_type="pending_review",
            at=review_timestamp,
            actor=reviewer,
            detail=review.review_id,
        )
    )

    approved = approve_narrative_draft(
        review,
        reviewer=reviewer,
        notes=notes,
        reviewed_at=review_timestamp,
        approval_attestation=approval_attestation,
    )
    audit_events.append(
        _workflow_audit(
            event_type="approved",
            at=review_timestamp,
            actor=reviewer,
            detail=approved.review_id,
        )
    )
    audit_events.extend(_review_audit_to_workflow_events(approved.audit_events))

    export = export_approved_insurance_narrative(
        packet=packet,
        draft=draft,
        review=approved,
        actor=actor,
        export_format=export_format,
        created_at=timestamp,
    )
    audit_events.append(
        _workflow_audit(
            event_type="export_created",
            at=timestamp,
            actor=actor,
            detail=export.export_id,
        )
    )

    return InsuranceNarrativeWorkflowResult(
        packet=packet,
        draft=draft,
        checker_summary=approved.checker_summary,
        review=approved,
        export=export,
        status="export_created",
        warnings=warnings,
        audit_events=audit_events,
    )
