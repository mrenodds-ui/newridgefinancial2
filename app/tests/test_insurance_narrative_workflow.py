from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.insurance_narratives import (
    NarrativeReviewWorkflowError,
    approve_and_export_insurance_narrative_workflow,
    create_insurance_narrative_draft_workflow,
)


@pytest.fixture
def fixed_timestamp() -> str:
    return "2026-06-25T12:00:00+00:00"


def _checker_ok_result() -> dict:
    return {
        "status": "ok",
        "review": {
            "missing_data": [],
            "citation_issues": [],
            "possible_invented_facts": [],
            "contradictions": [],
            "recommended_action": "proceed to human review",
            "ready_for_human_review": True,
        },
    }


def _checker_unavailable_result() -> dict:
    return {
        "status": "lane_unavailable",
        "review": None,
        "error": "fast_review lane unavailable",
    }


def test_draft_workflow_creates_packet_and_draft_without_checker(fixed_timestamp: str) -> None:
    result = create_insurance_narrative_draft_workflow(
        patient_ref="CHART-A",
        claim_id="CLAIM-1001",
        narrative_type="denied_claim_resubmission",
        actor="operator@test",
        created_at=fixed_timestamp,
        run_checker=False,
    )

    assert result.packet.packet_id
    assert result.draft.packet_id == result.packet.packet_id
    assert result.status in ("draft_created", "blocked_missing_data")
    assert result.checker_summary is None
    assert result.review is None
    assert result.export is None
    assert any(event.event_type == "packet_created" for event in result.audit_events)
    assert any(event.event_type == "draft_created" for event in result.audit_events)


def _ready_draft_side_effect(packet, *, actor, created_at=None):
    from app.insurance_narratives import draft_insurance_narrative_from_packet

    draft = draft_insurance_narrative_from_packet(packet, actor=actor, created_at=created_at)
    non_blocking = [item for item in draft.missing_data if not item.blocking]
    return draft.model_copy(
        update={
            "missing_data": non_blocking,
            "status": "ready_for_human_review",
        }
    )


@patch("app.insurance_narratives.workflow.run_fast_review_check")
def test_run_checker_false_does_not_call_fast_review(
    mock_checker: MagicMock,
    fixed_timestamp: str,
) -> None:
    create_insurance_narrative_draft_workflow(
        patient_ref="CHART-A",
        claim_id="CLAIM-1001",
        narrative_type="denied_claim_resubmission",
        actor="operator@test",
        created_at=fixed_timestamp,
        run_checker=False,
    )
    mock_checker.assert_not_called()


@patch("app.insurance_narratives.workflow.run_fast_review_check")
@patch(
    "app.insurance_narratives.workflow.draft_insurance_narrative_from_packet",
    side_effect=_ready_draft_side_effect,
)
def test_run_checker_true_calls_fast_review_once_with_source_text(
    _mock_draft: MagicMock,
    mock_checker: MagicMock,
    fixed_timestamp: str,
) -> None:
    mock_checker.return_value = _checker_ok_result()
    result = create_insurance_narrative_draft_workflow(
        patient_ref="CHART-A",
        claim_id="CLAIM-1001",
        procedure_ids=["PROC-CROWN-BUILDUP-3"],
        narrative_type="denied_claim_resubmission",
        actor="operator@test",
        created_at=fixed_timestamp,
        run_checker=True,
    )

    mock_checker.assert_called_once()
    call_kwargs = mock_checker.call_args.kwargs
    assert call_kwargs["packet_id"] == result.packet.packet_id
    assert result.draft.draft_id in call_kwargs["source_text"]
    for fact in result.packet.source_facts:
        assert fact.fact_id in call_kwargs["source_text"]
    assert result.status == "checker_completed"
    assert result.checker_summary is not None
    assert result.checker_summary.checker_status == "ok"


@patch("app.insurance_narratives.workflow.run_fast_review_check")
@patch(
    "app.insurance_narratives.workflow.draft_insurance_narrative_from_packet",
    side_effect=_ready_draft_side_effect,
)
def test_checker_unavailable_captured_as_advisory_status(
    _mock_draft: MagicMock,
    mock_checker: MagicMock,
    fixed_timestamp: str,
) -> None:
    mock_checker.return_value = _checker_unavailable_result()
    result = create_insurance_narrative_draft_workflow(
        patient_ref="CHART-A",
        claim_id="CLAIM-1001",
        narrative_type="denied_claim_resubmission",
        actor="operator@test",
        created_at=fixed_timestamp,
        run_checker=True,
    )

    assert result.packet.packet_id
    assert result.draft.draft_id
    assert result.status == "checker_unavailable"
    assert result.checker_summary is not None
    assert result.checker_summary.checker_status == "lane_unavailable"
    assert any(warning.code == "checker_unavailable" for warning in result.warnings)


def test_blocked_missing_data_status_preserved_not_auto_approved(fixed_timestamp: str) -> None:
    result = create_insurance_narrative_draft_workflow(
        patient_ref="CHART-A",
        claim_id="CLAIM-1001",
        procedure_ids=["PROC-CROWN-BUILDUP-3"],
        narrative_type="denied_claim_resubmission",
        actor="operator@test",
        created_at=fixed_timestamp,
        run_checker=False,
    )

    assert result.draft.status == "blocked_missing_data"
    assert result.status == "blocked_missing_data"
    assert result.review is None
    assert result.export is None


def _ready_workflow_result(*, created_at: str):
    draft_result = create_insurance_narrative_draft_workflow(
        patient_ref="CHART-A",
        claim_id="CLAIM-1001",
        narrative_type="denied_claim_resubmission",
        actor="operator@test",
        created_at=created_at,
        run_checker=False,
    )
    from app.insurance_narratives import draft_insurance_narrative_from_packet

    draft_result.packet.missing_data = [
        item for item in draft_result.packet.missing_data if not item.blocking
    ]
    ready_draft = draft_insurance_narrative_from_packet(
        draft_result.packet,
        actor="operator@test",
        created_at=created_at,
    )
    return draft_result.packet, ready_draft


def test_approval_export_workflow_requires_attestation(fixed_timestamp: str) -> None:
    packet, ready_draft = _ready_workflow_result(created_at=fixed_timestamp)

    with pytest.raises(NarrativeReviewWorkflowError, match="approval_attestation"):
        approve_and_export_insurance_narrative_workflow(
            packet=packet,
            draft=ready_draft,
            reviewer="reviewer@test",
            notes="Approve.",
            approval_attestation=False,
            actor="exporter@test",
            reviewed_at=fixed_timestamp,
            created_at=fixed_timestamp,
        )


def test_approval_export_workflow_rejects_blocked_drafts(fixed_timestamp: str) -> None:
    blocked = create_insurance_narrative_draft_workflow(
        patient_ref="CHART-A",
        claim_id="CLAIM-1001",
        procedure_ids=["PROC-CROWN-BUILDUP-3"],
        narrative_type="denied_claim_resubmission",
        actor="operator@test",
        created_at=fixed_timestamp,
        run_checker=False,
    )

    with pytest.raises(NarrativeReviewWorkflowError, match="blocked_missing_data"):
        approve_and_export_insurance_narrative_workflow(
            packet=blocked.packet,
            draft=blocked.draft,
            reviewer="reviewer@test",
            notes="Approve blocked draft.",
            approval_attestation=True,
            actor="exporter@test",
            reviewed_at=fixed_timestamp,
            created_at=fixed_timestamp,
        )


def test_approval_export_result_includes_not_submitted_export(fixed_timestamp: str) -> None:
    packet, ready_draft = _ready_workflow_result(created_at=fixed_timestamp)

    result = approve_and_export_insurance_narrative_workflow(
        packet=packet,
        draft=ready_draft,
        reviewer="reviewer@test",
        notes="Approved for local copy.",
        approval_attestation=True,
        actor="exporter@test",
        reviewed_at=fixed_timestamp,
        created_at=fixed_timestamp,
    )

    assert result.status == "export_created"
    assert result.review is not None
    assert result.review.status == "approved"
    assert result.export is not None
    assert result.export.submission_status == "not_submitted"
    assert "Not submitted" in result.export.body


def test_lineage_preserved_packet_draft_review_export(fixed_timestamp: str) -> None:
    packet, ready_draft = _ready_workflow_result(created_at=fixed_timestamp)

    result = approve_and_export_insurance_narrative_workflow(
        packet=packet,
        draft=ready_draft,
        reviewer="reviewer@test",
        notes="Lineage check.",
        approval_attestation=True,
        actor="exporter@test",
        reviewed_at=fixed_timestamp,
        created_at=fixed_timestamp,
    )

    packet_id = packet.packet_id
    draft_id = ready_draft.draft_id
    assert result.packet.packet_id == packet_id
    assert result.draft.draft_id == draft_id
    assert result.review is not None
    assert result.export is not None
    assert result.review.packet_id == packet_id
    assert result.review.draft_id == draft_id
    assert result.export.packet_id == packet_id
    assert result.export.draft_id == draft_id
    assert result.export.review_id == result.review.review_id


@patch("app.insurance_narratives.workflow.run_fast_review_check")
@patch(
    "app.insurance_narratives.workflow.draft_insurance_narrative_from_packet",
    side_effect=_ready_draft_side_effect,
)
def test_no_filesystem_network_or_payer_side_effects(
    _mock_draft: MagicMock,
    mock_checker: MagicMock,
    fixed_timestamp: str,
) -> None:
    mock_checker.return_value = _checker_ok_result()
    with patch("builtins.open", MagicMock()) as open_mock:
        with patch("urllib.request.urlopen", MagicMock()) as urlopen_mock:
            draft_result = create_insurance_narrative_draft_workflow(
                patient_ref="CHART-A",
                claim_id="CLAIM-1001",
                narrative_type="denied_claim_resubmission",
                actor="operator@test",
                created_at=fixed_timestamp,
                run_checker=True,
            )
            packet, ready_draft = _ready_workflow_result(created_at=fixed_timestamp)
            export_result = approve_and_export_insurance_narrative_workflow(
                packet=packet,
                draft=ready_draft,
                reviewer="reviewer@test",
                notes="No side effects.",
                approval_attestation=True,
                actor="exporter@test",
                reviewed_at=fixed_timestamp,
                created_at=fixed_timestamp,
            )

    assert export_result.export is not None
    open_mock.assert_not_called()
    urlopen_mock.assert_not_called()
    mock_checker.assert_called_once()
