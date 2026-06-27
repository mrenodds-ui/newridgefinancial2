from __future__ import annotations

import json
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.hal.financial_tools as financial_tools
from app.auth import clear_user_registry_cache
from app.hal import orchestrator as hal_orchestrator
from app.hal.claim_packet_readiness import (
    assess_claim_packet_readiness,
    build_claim_packet_readiness_response,
    readiness_label,
)
from app.insurance_narratives.data_adapter import FixtureInsuranceNarrativeDataAdapter
from app.main import app

TEST_AUTH_USERS_JSON = json.dumps(
    [
        {
            "username": "office_manager",
            "display_name": "Office Manager",
            "password": "office-password",
            "roles": ["dashboard:read", "hal:operator"],
        },
        {
            "username": "viewer_only",
            "display_name": "Viewer Only",
            "password": "viewer-password",
            "roles": ["dashboard:read"],
        },
    ]
)

os.environ["APP_AUTH_USERS_JSON"] = TEST_AUTH_USERS_JSON
client = TestClient(app)


@pytest.fixture(autouse=True)
def _runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime_dir = os.path.join(os.path.dirname(__file__), ".claim_packet_runtime", uuid4().hex)
    os.environ["APP_AUTH_USERS_JSON"] = TEST_AUTH_USERS_JSON
    os.environ["HAL_ALLOWED_BASE_PATH"] = runtime_dir
    os.environ["HAL_SQLITE_PATH"] = os.path.join(runtime_dir, "hal_test.sqlite3")
    clear_user_registry_cache()
    monkeypatch.setattr(
        financial_tools,
        "get_financial_source_status",
        lambda: {
            "softdent": {"status": "available", "summary": "SoftDent exports available."},
            "quickbooks": {"status": "available", "summary": "QuickBooks summary available."},
        },
    )


def office_manager_auth() -> tuple[str, str]:
    return ("office_manager", "office-password")


def test_claim_packet_readiness_endpoint_requires_hal_operator() -> None:
    response = client.get("/api/hal9000/claim-packet-readiness", auth=("viewer_only", "viewer-password"))
    assert response.status_code == 403


def test_claim_packet_readiness_endpoint_returns_safe_payload() -> None:
    response = client.get("/api/hal9000/claim-packet-readiness", auth=office_manager_auth())
    assert response.status_code == 200
    payload = response.json()
    assert payload["submission_status"] == "not_submitted"
    assert payload["local_only"] is True
    assert payload["safety"]["local_only"] is True
    assert payload["safety"]["not_submitted"] is True
    assert payload["safety"]["human_review_required"] is True
    assert payload["safety"]["external_delivery_allowed"] is False
    assert payload["safety"]["softdent_writeback_allowed"] is False
    assert payload["safety"]["payer_contact_allowed"] is False
    assert payload["summary"]["total_count"] >= 1
    assert payload["items"]


def test_fixture_denied_claim_is_blocked_for_missing_radiograph() -> None:
    item = assess_claim_packet_readiness(
        patient_ref="CHART-A",
        claim_id="CLAIM-1001",
        procedure_ids=["PROC-CROWN-BUILDUP-3"],
        actor="operator@test",
        adapter=FixtureInsuranceNarrativeDataAdapter(),
    )
    assert item.status == "blocked"
    assert readiness_label("missing_radiograph_or_photo") in item.missing_items
    assert item.safety.human_review_required is True
    assert item.can_prepare_local_draft is True
    assert "Radiograph/photo missing" in " ".join(item.missing_items)


def test_ready_packet_still_requires_human_review(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.insurance_narratives.data_adapter import InsuranceNarrativePacketInputs, missing_data_item
    from app.insurance_narratives.schemas import ClaimCaseSummary, NarrativeSourceFact, PatientCaseSummary, ProcedureCaseSummary

    class CompleteClaimAdapter(FixtureInsuranceNarrativeDataAdapter):
        def fetch_packet_inputs(self, scope):  # type: ignore[override]
            return InsuranceNarrativePacketInputs(
                patient=PatientCaseSummary(patient_ref="CHART-Z", chart_ref="CHART-Z", label="Patient ref CHART-Z"),
                claim=ClaimCaseSummary(
                    claim_id="CLAIM-READY",
                    status="Denied",
                    payer_name="Payer One",
                    billed_amount=100.0,
                    denial_reason="Missing documentation",
                ),
                procedures=[
                    ProcedureCaseSummary(
                        procedure_id="PROC-1",
                        description="Crown",
                        tooth="3",
                        service_date="2026-06-12",
                    )
                ],
                source_facts=[
                    NarrativeSourceFact(
                        fact_id="fact-clinical",
                        source_type="clinical_note",
                        source_label="Clinical note excerpt",
                        text="Fractured cusp documented.",
                        supports=["CLAIM-READY"],
                    )
                ],
                missing_data=[missing_data_item("missing_softdent_ar")],
            )

    item = assess_claim_packet_readiness(
        patient_ref="CHART-Z",
        claim_id="CLAIM-READY",
        actor="operator@test",
        adapter=CompleteClaimAdapter(),
    )
    assert item.status == "ready"
    assert readiness_label("missing_human_review") in item.missing_items
    assert item.safety.human_review_required is True
    assert "Packet appears ready for human review" in item.staff_summary
    assert item.safety.not_submitted is True


def test_missing_claim_export_never_becomes_ready(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INSURANCE_NARRATIVE_SOFTDENT_EXPORT_DIR", str(tmp_path))
    payload = build_claim_packet_readiness_response(actor="operator@test")
    assert payload.summary.blocked_count >= 1
    assert payload.summary.ready_count == 0
    assert payload.items[0].status == "blocked"
    assert readiness_label("missing_claim_export") in payload.items[0].missing_items


def test_readiness_does_not_invent_radiograph_or_perio_data() -> None:
    item = assess_claim_packet_readiness(
        patient_ref="CHART-A",
        claim_id="CLAIM-1001",
        procedure_ids=["PROC-CROWN-BUILDUP-3"],
        actor="operator@test",
        adapter=FixtureInsuranceNarrativeDataAdapter(),
    )
    available_text = " ".join(item.available_items).lower()
    assert "radiograph available" not in available_text
    assert "perio chart available" not in available_text
    assert readiness_label("missing_radiograph_or_photo") in item.missing_items


def test_ask_hal_claim_packet_readiness_is_deterministic(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_generate(**kwargs):
        del kwargs
        raise AssertionError("Claim packet readiness should not call a model")

    monkeypatch.setattr(hal_orchestrator, "_generate_profile_answer", fail_generate)

    payload = hal_orchestrator.answer_hal_question(
        question="claim packet readiness",
        actor="hal_operator",
    )

    answer = payload["answer"]
    assert payload["answer_lane"] == "deterministic"
    assert "Claim packet readiness" in answer
    assert "Ready:" in answer
    assert "Needs review:" in answer
    assert "Blocked:" in answer
    assert "Nothing has been submitted or sent." in answer
    assert "QuickBooks" not in answer
    assert "QBXML" not in answer
