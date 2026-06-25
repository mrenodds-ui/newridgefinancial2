"""Human review and approval workflow for insurance narrative drafts."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from app.insurance_narratives.schemas import (
    InsuranceNarrativeDraft,
    InsuranceNarrativeReviewRecord,
    NarrativeCheckerSummary,
    NarrativeReviewAuditEvent,
    NarrativeReviewStatus,
)

_TERMINAL_REVIEW_STATUSES: frozenset[NarrativeReviewStatus] = frozenset(
    {"approved", "rejected"}
)
_ACTIONABLE_REVIEW_STATUSES: frozenset[NarrativeReviewStatus] = frozenset(
    {"pending_review", "revision_requested"}
)


class NarrativeReviewWorkflowError(ValueError):
    """Raised when a review transition violates workflow safety rules."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _deterministic_review_id(draft_id: str) -> str:
    digest = hashlib.sha256(draft_id.encode("utf-8")).hexdigest()[:16]
    return f"narrative-review-{digest}"


def _require_reviewer(reviewer: str) -> str:
    normalized = reviewer.strip()
    if not normalized:
        raise NarrativeReviewWorkflowError("reviewer is required")
    return normalized


def _append_audit_event(
    review: InsuranceNarrativeReviewRecord,
    *,
    event_type: str,
    at: str,
    actor: str,
    previous_status: NarrativeReviewStatus | None,
    new_status: NarrativeReviewStatus,
    notes: str | None = None,
) -> list[NarrativeReviewAuditEvent]:
    events = [event.model_copy(deep=True) for event in review.audit_events]
    events.append(
        NarrativeReviewAuditEvent(
            event_type=event_type,
            at=at,
            actor=actor,
            previous_status=previous_status,
            new_status=new_status,
            notes=notes,
        )
    )
    return events


def _assert_actionable(review: InsuranceNarrativeReviewRecord, action: str) -> None:
    if review.status in _TERMINAL_REVIEW_STATUSES:
        raise NarrativeReviewWorkflowError(
            f"cannot {action} a review already in status '{review.status}'"
        )
    if review.status not in _ACTIONABLE_REVIEW_STATUSES:
        raise NarrativeReviewWorkflowError(
            f"cannot {action} a review in status '{review.status}'"
        )


def _assert_lineage_unchanged(
    review: InsuranceNarrativeReviewRecord,
    *,
    packet_id: str,
    draft_id: str,
) -> None:
    if review.packet_id != packet_id or review.draft_id != draft_id:
        raise NarrativeReviewWorkflowError("packet_id and draft_id lineage must not change")


def checker_result_to_summary(check_result: dict[str, Any]) -> NarrativeCheckerSummary:
    """Normalize an opt-in ``run_fast_review_check`` result into advisory summary counts."""

    review_payload = check_result.get("review") or {}
    return NarrativeCheckerSummary(
        checker_status=str(check_result.get("status") or ""),
        missing_data_count=len(review_payload.get("missing_data") or []),
        citation_issue_count=len(review_payload.get("citation_issues") or []),
        possible_invented_fact_count=len(review_payload.get("possible_invented_facts") or []),
        contradiction_count=len(review_payload.get("contradictions") or []),
        ready_for_human_review=review_payload.get("ready_for_human_review"),
    )


def create_narrative_review_record(
    draft: InsuranceNarrativeDraft,
    *,
    reviewer: str,
    created_at: str | None = None,
    checker_summary: NarrativeCheckerSummary | dict[str, Any] | None = None,
) -> InsuranceNarrativeReviewRecord:
    """Open a pending human-review record for a bounded narrative draft."""

    reviewer_id = _require_reviewer(reviewer)
    timestamp = created_at or _utc_now_iso()
    summary: NarrativeCheckerSummary | None
    if checker_summary is None:
        summary = None
    elif isinstance(checker_summary, NarrativeCheckerSummary):
        summary = checker_summary.model_copy(deep=True)
    else:
        summary = checker_result_to_summary(checker_summary)

    review_id = _deterministic_review_id(draft.draft_id)
    audit_events = [
        NarrativeReviewAuditEvent(
            event_type="review_created",
            at=timestamp,
            actor=reviewer_id,
            previous_status=None,
            new_status="pending_review",
            notes="Review record created for human approval workflow.",
        )
    ]

    return InsuranceNarrativeReviewRecord(
        review_id=review_id,
        packet_id=draft.packet_id,
        draft_id=draft.draft_id,
        draft_status=draft.status,
        status="pending_review",
        reviewer=reviewer_id,
        checker_summary=summary,
        created_at=timestamp,
        audit_events=audit_events,
    )


def approve_narrative_draft(
    review: InsuranceNarrativeReviewRecord,
    *,
    reviewer: str,
    notes: str,
    reviewed_at: str | None = None,
    approval_attestation: bool,
) -> InsuranceNarrativeReviewRecord:
    """Approve a draft after explicit human attestation. Does not export or submit."""

    reviewer_id = _require_reviewer(reviewer)
    _assert_actionable(review, "approve")
    _assert_lineage_unchanged(review, packet_id=review.packet_id, draft_id=review.draft_id)

    if review.draft_status == "blocked_missing_data":
        raise NarrativeReviewWorkflowError(
            "cannot approve a draft with status 'blocked_missing_data'"
        )
    if not approval_attestation:
        raise NarrativeReviewWorkflowError("approval_attestation must be true to approve")

    timestamp = reviewed_at or _utc_now_iso()
    updated = review.model_copy(deep=True)
    updated.status = "approved"
    updated.reviewer = reviewer_id
    updated.reviewed_at = timestamp
    updated.notes = notes.strip() or None
    updated.approval_attestation = True
    updated.audit_events = _append_audit_event(
        review,
        event_type="draft_approved",
        at=timestamp,
        actor=reviewer_id,
        previous_status=review.status,
        new_status="approved",
        notes=notes,
    )
    return updated


def reject_narrative_draft(
    review: InsuranceNarrativeReviewRecord,
    *,
    reviewer: str,
    notes: str,
    reviewed_at: str | None = None,
) -> InsuranceNarrativeReviewRecord:
    """Reject a draft with reviewer notes. Does not export or submit."""

    reviewer_id = _require_reviewer(reviewer)
    _assert_actionable(review, "reject")
    _assert_lineage_unchanged(review, packet_id=review.packet_id, draft_id=review.draft_id)

    timestamp = reviewed_at or _utc_now_iso()
    updated = review.model_copy(deep=True)
    updated.status = "rejected"
    updated.reviewer = reviewer_id
    updated.reviewed_at = timestamp
    updated.notes = notes.strip() or None
    updated.approval_attestation = None
    updated.audit_events = _append_audit_event(
        review,
        event_type="draft_rejected",
        at=timestamp,
        actor=reviewer_id,
        previous_status=review.status,
        new_status="rejected",
        notes=notes,
    )
    return updated


def request_narrative_revision(
    review: InsuranceNarrativeReviewRecord,
    *,
    reviewer: str,
    notes: str,
    required_changes: list[str],
    reviewed_at: str | None = None,
) -> InsuranceNarrativeReviewRecord:
    """Request narrative revision with explicit required changes."""

    reviewer_id = _require_reviewer(reviewer)
    _assert_actionable(review, "request revision for")
    _assert_lineage_unchanged(review, packet_id=review.packet_id, draft_id=review.draft_id)

    normalized_changes = [change.strip() for change in required_changes if change.strip()]
    if not normalized_changes:
        raise NarrativeReviewWorkflowError(
            "required_changes must include at least one non-empty item"
        )

    timestamp = reviewed_at or _utc_now_iso()
    updated = review.model_copy(deep=True)
    updated.status = "revision_requested"
    updated.reviewer = reviewer_id
    updated.reviewed_at = timestamp
    updated.notes = notes.strip() or None
    updated.required_changes = normalized_changes
    updated.approval_attestation = None
    updated.audit_events = _append_audit_event(
        review,
        event_type="revision_requested",
        at=timestamp,
        actor=reviewer_id,
        previous_status=review.status,
        new_status="revision_requested",
        notes=notes,
    )
    return updated
