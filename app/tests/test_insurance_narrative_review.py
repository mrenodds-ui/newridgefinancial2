from __future__ import annotations

from unittest.mock import patch

import pytest

from app.insurance_narratives import (
    NarrativeReviewWorkflowError,
    approve_narrative_draft,
    build_insurance_narrative_case_packet,
    checker_result_to_summary,
    create_narrative_review_record,
    draft_insurance_narrative_from_packet,
    reject_narrative_draft,
    request_narrative_revision,
)


@pytest.fixture
def fixed_timestamp() -> str:
    return "2026-06-25T12:00:00+00:00"


def _ready_draft(*, created_at: str):
    packet = build_insurance_narrative_case_packet(
        patient_ref="CHART-A",
        claim_id="CLAIM-1001",
        narrative_type="denied_claim_resubmission",
        actor="operator@test",
        created_at=created_at,
    )
    packet.missing_data = [item for item in packet.missing_data if not item.blocking]
    return draft_insurance_narrative_from_packet(packet, actor="operator@test", created_at=created_at)


def _blocked_draft(*, created_at: str):
    packet = build_insurance_narrative_case_packet(
        patient_ref="CHART-A",
        claim_id="CLAIM-1001",
        procedure_ids=["PROC-CROWN-BUILDUP-3"],
        narrative_type="denied_claim_resubmission",
        actor="operator@test",
        created_at=created_at,
    )
    return draft_insurance_narrative_from_packet(packet, actor="operator@test", created_at=created_at)


def _pending_review(*, created_at: str, draft=None):
    draft = draft or _ready_draft(created_at=created_at)
    return create_narrative_review_record(
        draft,
        reviewer="reviewer@test",
        created_at=created_at,
    )


def test_pending_review_preserves_packet_and_draft_lineage(fixed_timestamp: str) -> None:
    draft = _ready_draft(created_at=fixed_timestamp)
    review = _pending_review(created_at=fixed_timestamp, draft=draft)

    assert review.status == "pending_review"
    assert review.packet_id == draft.packet_id
    assert review.draft_id == draft.draft_id
    assert review.draft_status == draft.status
    assert review.audit_events[0].event_type == "review_created"


def test_approval_requires_attestation_true(fixed_timestamp: str) -> None:
    review = _pending_review(created_at=fixed_timestamp)

    with pytest.raises(NarrativeReviewWorkflowError, match="approval_attestation"):
        approve_narrative_draft(
            review,
            reviewer="reviewer@test",
            notes="Looks good.",
            reviewed_at=fixed_timestamp,
            approval_attestation=False,
        )


def test_blocked_draft_cannot_be_approved(fixed_timestamp: str) -> None:
    draft = _blocked_draft(created_at=fixed_timestamp)
    assert draft.status == "blocked_missing_data"
    review = create_narrative_review_record(
        draft,
        reviewer="reviewer@test",
        created_at=fixed_timestamp,
    )

    with pytest.raises(NarrativeReviewWorkflowError, match="blocked_missing_data"):
        approve_narrative_draft(
            review,
            reviewer="reviewer@test",
            notes="Approve anyway.",
            reviewed_at=fixed_timestamp,
            approval_attestation=True,
        )


def test_approved_review_cannot_be_approved_or_rejected_again(fixed_timestamp: str) -> None:
    review = _pending_review(created_at=fixed_timestamp)
    approved = approve_narrative_draft(
        review,
        reviewer="reviewer@test",
        notes="Approved after citation check.",
        reviewed_at=fixed_timestamp,
        approval_attestation=True,
    )

    with pytest.raises(NarrativeReviewWorkflowError, match="cannot approve"):
        approve_narrative_draft(
            approved,
            reviewer="reviewer@test",
            notes="Second approval.",
            reviewed_at=fixed_timestamp,
            approval_attestation=True,
        )

    with pytest.raises(NarrativeReviewWorkflowError, match="cannot reject"):
        reject_narrative_draft(
            approved,
            reviewer="reviewer@test",
            notes="Reject after approval.",
            reviewed_at=fixed_timestamp,
        )


def test_revision_request_requires_required_changes(fixed_timestamp: str) -> None:
    review = _pending_review(created_at=fixed_timestamp)

    with pytest.raises(NarrativeReviewWorkflowError, match="required_changes"):
        request_narrative_revision(
            review,
            reviewer="reviewer@test",
            notes="Needs edits.",
            required_changes=[],
            reviewed_at=fixed_timestamp,
        )


def test_rejection_records_reviewer_timestamp_and_notes(fixed_timestamp: str) -> None:
    review = _pending_review(created_at=fixed_timestamp)
    rejected = reject_narrative_draft(
        review,
        reviewer="reviewer@test",
        notes="Citations do not match packet facts.",
        reviewed_at=fixed_timestamp,
    )

    assert rejected.status == "rejected"
    assert rejected.reviewer == "reviewer@test"
    assert rejected.reviewed_at == fixed_timestamp
    assert rejected.notes == "Citations do not match packet facts."
    assert rejected.audit_events[-1].event_type == "draft_rejected"
    assert rejected.audit_events[-1].new_status == "rejected"


def test_checker_summary_stored_but_does_not_drive_approval(fixed_timestamp: str) -> None:
    check_result = {
        "status": "ok",
        "review": {
            "missing_data": ["missing_softdent_ar"],
            "citation_issues": ["unsupported fact"],
            "possible_invented_facts": ["invented amount"],
            "contradictions": ["date mismatch"],
            "recommended_action": "revise",
            "ready_for_human_review": False,
        },
    }
    draft = _ready_draft(created_at=fixed_timestamp)
    review = create_narrative_review_record(
        draft,
        reviewer="reviewer@test",
        created_at=fixed_timestamp,
        checker_summary=check_result,
    )

    assert review.checker_summary is not None
    assert review.checker_summary.checker_status == "ok"
    assert review.checker_summary.missing_data_count == 1
    assert review.checker_summary.citation_issue_count == 1
    assert review.checker_summary.possible_invented_fact_count == 1
    assert review.checker_summary.contradiction_count == 1
    assert review.checker_summary.ready_for_human_review is False

    approved = approve_narrative_draft(
        review,
        reviewer="reviewer@test",
        notes="Human override after checker flags.",
        reviewed_at=fixed_timestamp,
        approval_attestation=True,
    )
    assert approved.status == "approved"
    assert approved.checker_summary == review.checker_summary


def test_approval_does_not_call_export_or_submission_code(fixed_timestamp: str) -> None:
    review = _pending_review(created_at=fixed_timestamp)

    with patch("app.routes.submit_insurance_narrative", create=True) as submit_mock:
        approved = approve_narrative_draft(
            review,
            reviewer="reviewer@test",
            notes="Staff approved for internal record only.",
            reviewed_at=fixed_timestamp,
            approval_attestation=True,
        )

    assert approved.status == "approved"
    submit_mock.assert_not_called()


def test_audit_events_append_on_decision_changes(fixed_timestamp: str) -> None:
    review = _pending_review(created_at=fixed_timestamp)
    assert len(review.audit_events) == 1

    revised = request_narrative_revision(
        review,
        reviewer="reviewer@test",
        notes="Add payer reference.",
        required_changes=["Cite payer denial letter fact_id."],
        reviewed_at=fixed_timestamp,
    )
    assert len(revised.audit_events) == 2
    assert revised.audit_events[-1].previous_status == "pending_review"
    assert revised.audit_events[-1].new_status == "revision_requested"

    approved = approve_narrative_draft(
        revised,
        reviewer="reviewer@test",
        notes="Revision complete.",
        reviewed_at=fixed_timestamp,
        approval_attestation=True,
    )
    assert len(approved.audit_events) == 3
    assert approved.audit_events[-1].event_type == "draft_approved"
    assert approved.approval_attestation is True


def test_checker_result_to_summary_normalizes_counts() -> None:
    summary = checker_result_to_summary(
        {
            "status": "parse_error",
            "review": None,
        }
    )
    assert summary.checker_status == "parse_error"
    assert summary.missing_data_count == 0
    assert summary.ready_for_human_review is None
