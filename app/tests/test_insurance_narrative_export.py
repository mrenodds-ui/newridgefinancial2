from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.insurance_narratives import (
    NarrativeExportWorkflowError,
    NarrativeReviewWorkflowError,
    approve_narrative_draft,
    build_insurance_narrative_case_packet,
    create_narrative_review_record,
    draft_insurance_narrative_from_packet,
    export_approved_insurance_narrative,
    reject_narrative_draft,
    request_narrative_revision,
)


@pytest.fixture
def fixed_timestamp() -> str:
    return "2026-06-25T12:00:00+00:00"


def _ready_packet_and_draft(*, created_at: str):
    packet = build_insurance_narrative_case_packet(
        patient_ref="CHART-A",
        claim_id="CLAIM-1001",
        narrative_type="denied_claim_resubmission",
        actor="operator@test",
        created_at=created_at,
    )
    packet.missing_data = [item for item in packet.missing_data if not item.blocking]
    draft = draft_insurance_narrative_from_packet(packet, actor="operator@test", created_at=created_at)
    return packet, draft


def _approved_review(*, created_at: str):
    packet, draft = _ready_packet_and_draft(created_at=created_at)
    review = create_narrative_review_record(
        draft,
        reviewer="reviewer@test",
        created_at=created_at,
    )
    approved = approve_narrative_draft(
        review,
        reviewer="reviewer@test",
        notes="Citations verified.",
        reviewed_at=created_at,
        approval_attestation=True,
    )
    return packet, draft, approved


def test_approved_review_exports_successfully(fixed_timestamp: str) -> None:
    packet, draft, review = _approved_review(created_at=fixed_timestamp)
    export = export_approved_insurance_narrative(
        packet=packet,
        draft=draft,
        review=review,
        actor="exporter@test",
        created_at=fixed_timestamp,
    )

    assert export.packet_id == packet.packet_id
    assert export.draft_id == draft.draft_id
    assert export.review_id == review.review_id
    assert export.format == "markdown"
    assert export.body
    assert export.approval_summary.attestation_confirmed is True


@pytest.mark.parametrize("status", ["pending_review", "rejected", "revision_requested"])
def test_non_approved_reviews_cannot_export(fixed_timestamp: str, status: str) -> None:
    packet, draft = _ready_packet_and_draft(created_at=fixed_timestamp)
    review = create_narrative_review_record(
        draft,
        reviewer="reviewer@test",
        created_at=fixed_timestamp,
    )

    if status == "rejected":
        review = reject_narrative_draft(
            review,
            reviewer="reviewer@test",
            notes="Reject.",
            reviewed_at=fixed_timestamp,
        )
    elif status == "revision_requested":
        review = request_narrative_revision(
            review,
            reviewer="reviewer@test",
            notes="Revise.",
            required_changes=["Add citation."],
            reviewed_at=fixed_timestamp,
        )

    with pytest.raises(NarrativeExportWorkflowError, match="only approved"):
        export_approved_insurance_narrative(
            packet=packet,
            draft=draft,
            review=review,
            actor="exporter@test",
            created_at=fixed_timestamp,
        )


def test_lineage_mismatch_fails(fixed_timestamp: str) -> None:
    packet, draft, review = _approved_review(created_at=fixed_timestamp)
    other_packet = build_insurance_narrative_case_packet(
        patient_ref="CHART-B",
        claim_id="CLAIM-2002",
        narrative_type="denied_claim_resubmission",
        actor="operator@test",
        created_at=fixed_timestamp,
    )

    with pytest.raises(NarrativeExportWorkflowError, match="packet_id"):
        export_approved_insurance_narrative(
            packet=other_packet,
            draft=draft,
            review=review,
            actor="exporter@test",
            created_at=fixed_timestamp,
        )


def test_missing_approval_attestation_fails(fixed_timestamp: str) -> None:
    packet, draft = _ready_packet_and_draft(created_at=fixed_timestamp)
    review = create_narrative_review_record(
        draft,
        reviewer="reviewer@test",
        created_at=fixed_timestamp,
    )
    review.status = "approved"
    review.reviewed_at = fixed_timestamp
    review.approval_attestation = None

    with pytest.raises(NarrativeExportWorkflowError, match="approval_attestation"):
        export_approved_insurance_narrative(
            packet=packet,
            draft=draft,
            review=review,
            actor="exporter@test",
            created_at=fixed_timestamp,
        )


def test_export_includes_citations(fixed_timestamp: str) -> None:
    packet, draft, review = _approved_review(created_at=fixed_timestamp)
    export = export_approved_insurance_narrative(
        packet=packet,
        draft=draft,
        review=review,
        actor="exporter@test",
        created_at=fixed_timestamp,
    )

    assert export.citations == draft.citations
    for citation in draft.citations:
        assert citation.fact_id in export.body


def test_export_includes_missing_data_disclosures(fixed_timestamp: str) -> None:
    packet, draft, review = _approved_review(created_at=fixed_timestamp)
    export = export_approved_insurance_narrative(
        packet=packet,
        draft=draft,
        review=review,
        actor="exporter@test",
        created_at=fixed_timestamp,
    )

    assert export.missing_data_disclosures == draft.missing_data
    for item in draft.missing_data:
        assert item.code in export.body
        assert item.label in export.body


def test_submission_status_is_always_not_submitted(fixed_timestamp: str) -> None:
    packet, draft, review = _approved_review(created_at=fixed_timestamp)
    export = export_approved_insurance_narrative(
        packet=packet,
        draft=draft,
        review=review,
        actor="exporter@test",
        created_at=fixed_timestamp,
    )

    assert export.submission_status == "not_submitted"
    assert "Not submitted" in export.body


def test_export_performs_no_filesystem_or_network_side_effects(fixed_timestamp: str) -> None:
    packet, draft, review = _approved_review(created_at=fixed_timestamp)

    with patch("builtins.open", MagicMock()) as open_mock:
        with patch("urllib.request.urlopen", MagicMock()) as urlopen_mock:
            export = export_approved_insurance_narrative(
                packet=packet,
                draft=draft,
                review=review,
                actor="exporter@test",
                created_at=fixed_timestamp,
            )

    assert export.export_id
    open_mock.assert_not_called()
    urlopen_mock.assert_not_called()


@pytest.mark.parametrize("export_format", ["markdown", "plain_text"])
def test_export_formats_work(fixed_timestamp: str, export_format: str) -> None:
    packet, draft, review = _approved_review(created_at=fixed_timestamp)
    export = export_approved_insurance_narrative(
        packet=packet,
        draft=draft,
        review=review,
        actor="exporter@test",
        export_format=export_format,
        created_at=fixed_timestamp,
    )

    assert export.format == export_format
    assert "Insurance Narrative Export" in export.body
    assert "Citations" in export.body
    assert "Missing Data" in export.body
    assert "Approval" in export.body
    assert "Not submitted" in export.body
    if export_format == "markdown":
        assert export.body.startswith("# ")
    else:
        assert not export.body.startswith("# ")


def test_export_is_deterministic_with_fixed_timestamp(fixed_timestamp: str) -> None:
    packet, draft, review = _approved_review(created_at=fixed_timestamp)
    first = export_approved_insurance_narrative(
        packet=packet,
        draft=draft,
        review=review,
        actor="exporter@test",
        created_at=fixed_timestamp,
    )
    second = export_approved_insurance_narrative(
        packet=packet,
        draft=draft,
        review=review,
        actor="exporter@test",
        created_at=fixed_timestamp,
    )
    assert first.model_dump() == second.model_dump()


def test_blocked_draft_cannot_be_exported_even_if_review_approved(fixed_timestamp: str) -> None:
    packet = build_insurance_narrative_case_packet(
        patient_ref="CHART-A",
        claim_id="CLAIM-1001",
        procedure_ids=["PROC-CROWN-BUILDUP-3"],
        narrative_type="denied_claim_resubmission",
        actor="operator@test",
        created_at=fixed_timestamp,
    )
    draft = draft_insurance_narrative_from_packet(packet, actor="operator@test", created_at=fixed_timestamp)
    assert draft.status == "blocked_missing_data"

    review = create_narrative_review_record(
        draft,
        reviewer="reviewer@test",
        created_at=fixed_timestamp,
    )
    review.status = "approved"
    review.reviewed_at = fixed_timestamp
    review.approval_attestation = True

    with pytest.raises(NarrativeExportWorkflowError, match="blocked_missing_data"):
        export_approved_insurance_narrative(
            packet=packet,
            draft=draft,
            review=review,
            actor="exporter@test",
            created_at=fixed_timestamp,
        )
