from __future__ import annotations

import json
import re

import pytest

from app.insurance_narratives import (
    build_insurance_narrative_case_packet,
    draft_insurance_narrative_from_packet,
    draft_to_fast_review_source_text,
)

_PHONE_RE = re.compile(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


@pytest.fixture
def fixed_timestamp() -> str:
    return "2026-06-25T12:00:00+00:00"


def _sample_packet(*, created_at: str):
    return build_insurance_narrative_case_packet(
        patient_ref="CHART-A",
        claim_id="CLAIM-1001",
        procedure_ids=["PROC-CROWN-BUILDUP-3"],
        narrative_type="denied_claim_resubmission",
        actor="operator@test",
        created_at=created_at,
    )


def test_draft_is_deterministic_with_fixed_timestamp(fixed_timestamp: str) -> None:
    packet = _sample_packet(created_at=fixed_timestamp)
    first = draft_insurance_narrative_from_packet(packet, actor="operator@test", created_at=fixed_timestamp)
    second = draft_insurance_narrative_from_packet(packet, actor="operator@test", created_at=fixed_timestamp)
    assert first.model_dump() == second.model_dump()


def test_draft_uses_only_packet_facts(fixed_timestamp: str) -> None:
    packet = _sample_packet(created_at=fixed_timestamp)
    draft = draft_insurance_narrative_from_packet(packet, actor="operator@test", created_at=fixed_timestamp)
    fact_ids = {fact.fact_id for fact in packet.source_facts}

    assert draft.citations
    assert {citation.fact_id for citation in draft.citations}.issubset(fact_ids)
    supporting = next(section for section in draft.sections if section.key == "supporting_facts")
    for fact_id in fact_ids:
        assert fact_id in supporting.body


def test_all_citations_reference_valid_fact_ids(fixed_timestamp: str) -> None:
    packet = _sample_packet(created_at=fixed_timestamp)
    draft = draft_insurance_narrative_from_packet(packet, actor="operator@test", created_at=fixed_timestamp)
    valid_ids = {fact.fact_id for fact in packet.source_facts}

    for citation in draft.citations:
        assert citation.fact_id in valid_ids


def test_blocking_missing_data_produces_blocked_status(fixed_timestamp: str) -> None:
    packet = _sample_packet(created_at=fixed_timestamp)
    draft = draft_insurance_narrative_from_packet(packet, actor="operator@test", created_at=fixed_timestamp)

    assert draft.status == "blocked_missing_data"
    assert any(item.blocking for item in draft.missing_data)
    next_step = next(section for section in draft.sections if section.key == "recommended_next_step")
    assert "blocking" in next_step.body.lower()


def test_non_blocking_missing_data_appears_in_warnings(fixed_timestamp: str) -> None:
    packet = _sample_packet(created_at=fixed_timestamp)
    draft = draft_insurance_narrative_from_packet(packet, actor="operator@test", created_at=fixed_timestamp)

    warning_codes = {warning.code for warning in draft.warnings}
    assert "missing_softdent_ar" in warning_codes
    assert "missing_prior_auth" in warning_codes
    limitations = next(section for section in draft.sections if section.key == "missing_limitations")
    assert "missing_softdent_ar" in limitations.body


def test_ready_for_human_review_when_no_blocking_missing_data(fixed_timestamp: str) -> None:
    packet = build_insurance_narrative_case_packet(
        patient_ref="CHART-A",
        claim_id="CLAIM-1001",
        narrative_type="denied_claim_resubmission",
        actor="operator@test",
        created_at=fixed_timestamp,
    )
    packet.missing_data = [item for item in packet.missing_data if not item.blocking]
    draft = draft_insurance_narrative_from_packet(packet, actor="operator@test", created_at=fixed_timestamp)

    assert draft.status == "ready_for_human_review"
    assert draft.approval_required is True


def test_approval_required_is_always_true(fixed_timestamp: str) -> None:
    packet = _sample_packet(created_at=fixed_timestamp)
    draft = draft_insurance_narrative_from_packet(packet, actor="operator@test", created_at=fixed_timestamp)
    assert draft.approval_required is True


def test_ar_unavailable_stays_missing_not_zero(fixed_timestamp: str) -> None:
    packet = _sample_packet(created_at=fixed_timestamp)
    draft = draft_insurance_narrative_from_packet(packet, actor="operator@test", created_at=fixed_timestamp)
    blob = json.dumps(draft.model_dump(mode="json"))

    assert "missing_softdent_ar" in blob
    assert '"accounts_receivable": 0' not in blob
    assert '"ar_total": 0' not in blob
    limitations = next(section for section in draft.sections if section.key == "missing_limitations")
    assert "not $0" in limitations.body or "unavailable" in limitations.body.lower()


def test_draft_does_not_include_raw_patient_dump(fixed_timestamp: str) -> None:
    packet = _sample_packet(created_at=fixed_timestamp)
    draft = draft_insurance_narrative_from_packet(packet, actor="operator@test", created_at=fixed_timestamp)
    blob = json.dumps(draft.model_dump(mode="json"))

    assert "raw_rows" not in blob
    assert "database_dump" not in blob
    assert "patient_name" not in blob
    assert not _PHONE_RE.search(blob)
    assert not _SSN_RE.search(blob)
    assert not _EMAIL_RE.search(blob)


def test_draft_to_fast_review_source_text_includes_required_parts(fixed_timestamp: str) -> None:
    packet = _sample_packet(created_at=fixed_timestamp)
    draft = draft_insurance_narrative_from_packet(packet, actor="operator@test", created_at=fixed_timestamp)
    source_text = draft_to_fast_review_source_text(packet, draft)

    assert packet.packet_id in source_text
    assert draft.draft_id in source_text
    for fact in packet.source_facts:
        assert fact.fact_id in source_text
    for section in draft.sections:
        assert section.title in source_text
    for citation in draft.citations:
        assert citation.fact_id in source_text
    for item in draft.missing_data:
        assert item.code in source_text
    for warning in draft.warnings:
        assert warning.code in source_text
