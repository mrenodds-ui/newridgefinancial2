from __future__ import annotations

import json
import re

import pytest

from app.insurance_narratives import (
    build_insurance_narrative_case_packet,
    case_packet_to_fast_review_source_text,
)

_PHONE_RE = re.compile(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


@pytest.fixture
def fixed_timestamp() -> str:
    return "2026-06-25T12:00:00+00:00"


def _build_sample_packet(*, created_at: str) -> object:
    return build_insurance_narrative_case_packet(
        patient_ref="CHART-A",
        claim_id="CLAIM-1001",
        procedure_ids=["PROC-CROWN-BUILDUP-3"],
        date_range=None,
        narrative_type="denied_claim_resubmission",
        actor="operator@test",
        created_at=created_at,
    )


def test_packet_schema_serializes_cleanly(fixed_timestamp: str) -> None:
    packet = _build_sample_packet(created_at=fixed_timestamp)
    payload = packet.model_dump(mode="json")

    assert payload["packet_id"].startswith("narrative-packet-")
    assert payload["narrative_type"] == "denied_claim_resubmission"
    assert payload["patient"]["patient_ref"] == "CHART-A"
    assert payload["claim"]["claim_id"] == "CLAIM-1001"
    assert payload["audit_metadata"]["created_by"] == "operator@test"
    assert payload["audit_metadata"]["schema_version"] == "1.0.0"

    round_trip = json.dumps(payload)
    assert "CHART-A" in round_trip
    assert '"billed_amount": 215.75' in round_trip or '"billed_amount":215.75' in round_trip.replace(" ", "")


def test_builder_is_deterministic(fixed_timestamp: str) -> None:
    first = _build_sample_packet(created_at=fixed_timestamp)
    second = _build_sample_packet(created_at=fixed_timestamp)

    assert first.packet_id == second.packet_id
    assert first.model_dump() == second.model_dump()


def test_builder_includes_source_facts_and_missing_data(fixed_timestamp: str) -> None:
    packet = _build_sample_packet(created_at=fixed_timestamp)

    assert packet.source_facts
    assert all(fact.fact_id for fact in packet.source_facts)
    assert {fact.source_type for fact in packet.source_facts} >= {"claim", "clinical_note", "payer_denial"}

    missing_codes = {item.code for item in packet.missing_data}
    assert "missing_softdent_ar" in missing_codes
    assert "missing_prior_auth" in missing_codes
    assert "missing_radiograph" in missing_codes


def test_missing_ar_is_unavailable_not_zero(fixed_timestamp: str) -> None:
    packet = _build_sample_packet(created_at=fixed_timestamp)
    ar_item = next(item for item in packet.missing_data if item.code == "missing_softdent_ar")

    assert ar_item.blocking is False
    assert "not" in ar_item.why_it_matters.lower() or "unavailable" in ar_item.why_it_matters.lower()
    payload = packet.model_dump(mode="json")
    assert "accounts_receivable" not in payload or payload.get("claim", {}).get("ar_total") is None
    dumped = json.dumps(payload)
    assert '"ar_total": 0' not in dumped
    assert '"accounts_receivable": 0' not in dumped


def test_packet_does_not_include_raw_unrestricted_dump(fixed_timestamp: str) -> None:
    packet = _build_sample_packet(created_at=fixed_timestamp)
    dumped = packet.model_dump(mode="json")

    assert "raw_rows" not in dumped
    assert "database_dump" not in dumped
    assert "unrestricted" not in dumped
    assert packet.patient.label.startswith("Patient ref")
    assert "patient_name" not in dumped["patient"]


def test_unknown_patient_returns_missing_patient_record(fixed_timestamp: str) -> None:
    packet = build_insurance_narrative_case_packet(
        patient_ref="CHART-UNKNOWN",
        claim_id="CLAIM-9999",
        narrative_type="denied_claim_resubmission",
        actor="operator@test",
        created_at=fixed_timestamp,
    )

    assert packet.source_facts == []
    assert {item.code for item in packet.missing_data} == {"missing_patient_record"}


def test_fast_review_source_text_includes_fact_ids_and_missing_codes(fixed_timestamp: str) -> None:
    packet = _build_sample_packet(created_at=fixed_timestamp)
    source_text = case_packet_to_fast_review_source_text(packet)

    assert packet.packet_id in source_text
    assert packet.narrative_type in source_text
    for fact in packet.source_facts:
        assert fact.fact_id in source_text
    for item in packet.missing_data:
        assert item.code in source_text
    assert "unavailable" in source_text.lower() or "not $0" in source_text.lower()


def test_fixture_data_contains_no_obvious_phi() -> None:
    packet = _build_sample_packet(created_at="2026-06-25T12:00:00+00:00")
    blob = json.dumps(packet.model_dump(mode="json"))

    assert not _PHONE_RE.search(blob)
    assert not _SSN_RE.search(blob)
    assert not _EMAIL_RE.search(blob)
    assert "John Doe" not in blob
    assert "Jane" not in blob
