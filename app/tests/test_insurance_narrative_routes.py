from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.auth import clear_user_registry_cache
from app.insurance_narratives import (
    build_insurance_narrative_case_packet,
    draft_insurance_narrative_from_packet,
)
from app.main import app

TEST_AUTH_USERS_JSON = json.dumps(
    [
        {
            "username": "operator",
            "display_name": "Operator",
            "password": "operator-password",
            "roles": ["hal:operator"],
        },
        {
            "username": "viewer",
            "display_name": "Viewer",
            "password": "viewer-password",
            "roles": ["dashboard:read"],
        },
    ]
)

os.environ["APP_AUTH_USERS_JSON"] = TEST_AUTH_USERS_JSON

client = TestClient(app)

FIXED_TIMESTAMP = "2026-06-25T12:00:00+00:00"


def setup_function() -> None:
    os.environ["APP_AUTH_USERS_JSON"] = TEST_AUTH_USERS_JSON
    clear_user_registry_cache()


def operator_auth() -> tuple[str, str]:
    return ("operator", "operator-password")


def viewer_auth() -> tuple[str, str]:
    return ("viewer", "viewer-password")


def _draft_payload(**overrides) -> dict:
    payload = {
        "patient_ref": "CHART-A",
        "claim_id": "CLAIM-1001",
        "narrative_type": "denied_claim_resubmission",
    }
    payload.update(overrides)
    return payload


def _ready_packet_and_draft() -> tuple[dict, dict]:
    packet = build_insurance_narrative_case_packet(
        patient_ref="CHART-A",
        claim_id="CLAIM-1001",
        narrative_type="denied_claim_resubmission",
        actor="operator",
        created_at=FIXED_TIMESTAMP,
    )
    packet.missing_data = [item for item in packet.missing_data if not item.blocking]
    draft = draft_insurance_narrative_from_packet(
        packet,
        actor="operator",
        created_at=FIXED_TIMESTAMP,
    )
    return packet.model_dump(mode="json"), draft.model_dump(mode="json")


def test_draft_endpoint_requires_operator_scope() -> None:
    response = client.post(
        "/api/insurance-narratives/draft",
        auth=viewer_auth(),
        json=_draft_payload(),
    )
    assert response.status_code == 403


def test_approve_export_endpoint_requires_operator_scope() -> None:
    packet, draft = _ready_packet_and_draft()
    response = client.post(
        "/api/insurance-narratives/approve-export",
        auth=viewer_auth(),
        json={
            "packet": packet,
            "draft": draft,
            "reviewer": "reviewer@test",
            "notes": "Approve.",
            "approval_attestation": True,
        },
    )
    assert response.status_code == 403


def test_draft_endpoint_creates_packet_and_draft() -> None:
    response = client.post(
        "/api/insurance-narratives/draft",
        auth=operator_auth(),
        json=_draft_payload(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["packet"]["packet_id"]
    assert payload["draft"]["packet_id"] == payload["packet"]["packet_id"]
    assert payload["status"] in ("draft_created", "blocked_missing_data")
    assert payload["export"] is None
    assert payload["review"] is None


def test_draft_endpoint_run_checker_defaults_false() -> None:
    with patch("app.insurance_narratives.workflow.run_fast_review_check") as mock_checker:
        response = client.post(
            "/api/insurance-narratives/draft",
            auth=operator_auth(),
            json=_draft_payload(),
        )

    assert response.status_code == 200
    assert response.json().get("checker_summary") is None
    mock_checker.assert_not_called()


@patch("app.insurance_narratives.workflow.run_fast_review_check")
@patch(
    "app.insurance_narratives.workflow.draft_insurance_narrative_from_packet",
    wraps=draft_insurance_narrative_from_packet,
)
def test_draft_endpoint_run_checker_true_invokes_checker_once(
    _wrapped_draft,
    mock_checker: MagicMock,
) -> None:
    mock_checker.return_value = {
        "status": "ok",
        "review": {
            "missing_data": [],
            "citation_issues": [],
            "possible_invented_facts": [],
            "contradictions": [],
            "recommended_action": "proceed",
            "ready_for_human_review": True,
        },
    }

    response = client.post(
        "/api/insurance-narratives/draft",
        auth=operator_auth(),
        json=_draft_payload(run_checker=True),
    )

    assert response.status_code == 200
    mock_checker.assert_called_once()
    call_kwargs = mock_checker.call_args.kwargs
    assert call_kwargs["actor"] == "operator"
    assert call_kwargs["packet_id"] == response.json()["packet"]["packet_id"]
    assert response.json()["draft"]["draft_id"] in call_kwargs["source_text"]


@patch("app.insurance_narratives.workflow.run_fast_review_check")
@patch("app.insurance_narratives.workflow.draft_insurance_narrative_from_packet")
def test_draft_endpoint_checker_unavailable_returns_advisory_status(
    mock_draft_fn: MagicMock,
    mock_checker: MagicMock,
) -> None:
    packet = build_insurance_narrative_case_packet(
        patient_ref="CHART-A",
        claim_id="CLAIM-1001",
        narrative_type="denied_claim_resubmission",
        actor="operator",
        created_at=FIXED_TIMESTAMP,
    )
    real_draft = draft_insurance_narrative_from_packet(packet, actor="operator", created_at=FIXED_TIMESTAMP)
    mock_draft_fn.return_value = real_draft.model_copy(
        update={
            "missing_data": [item for item in real_draft.missing_data if not item.blocking],
            "status": "ready_for_human_review",
        }
    )
    mock_checker.return_value = {
        "status": "lane_unavailable",
        "review": None,
        "error": "fast_review lane unavailable",
    }

    response = client.post(
        "/api/insurance-narratives/draft",
        auth=operator_auth(),
        json=_draft_payload(run_checker=True),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "checker_unavailable"
    assert payload["checker_summary"]["checker_status"] == "lane_unavailable"
    assert any(warning["code"] == "checker_unavailable" for warning in payload["warnings"])


def test_approve_export_endpoint_exports_approved_flow() -> None:
    packet, draft = _ready_packet_and_draft()
    response = client.post(
        "/api/insurance-narratives/approve-export",
        auth=operator_auth(),
        json={
            "packet": packet,
            "draft": draft,
            "reviewer": "reviewer@test",
            "notes": "Citations verified.",
            "approval_attestation": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "export_created"
    assert payload["review"]["status"] == "approved"
    assert payload["export"]["submission_status"] == "not_submitted"


def test_approve_export_attestation_false_returns_workflow_error() -> None:
    packet, draft = _ready_packet_and_draft()
    response = client.post(
        "/api/insurance-narratives/approve-export",
        auth=operator_auth(),
        json={
            "packet": packet,
            "draft": draft,
            "reviewer": "reviewer@test",
            "notes": "Missing attestation.",
            "approval_attestation": False,
        },
    )

    assert response.status_code == 400
    assert "approval_attestation" in response.json()["detail"]


def test_approve_export_blocked_draft_returns_workflow_error() -> None:
    packet = build_insurance_narrative_case_packet(
        patient_ref="CHART-A",
        claim_id="CLAIM-1001",
        procedure_ids=["PROC-CROWN-BUILDUP-3"],
        narrative_type="denied_claim_resubmission",
        actor="operator",
        created_at=FIXED_TIMESTAMP,
    )
    draft = draft_insurance_narrative_from_packet(packet, actor="operator", created_at=FIXED_TIMESTAMP)
    assert draft.status == "blocked_missing_data"

    response = client.post(
        "/api/insurance-narratives/approve-export",
        auth=operator_auth(),
        json={
            "packet": packet.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "reviewer": "reviewer@test",
            "notes": "Approve blocked draft.",
            "approval_attestation": True,
        },
    )

    assert response.status_code == 400
    assert "blocked_missing_data" in response.json()["detail"]


def test_approve_export_preserves_lineage() -> None:
    packet, draft = _ready_packet_and_draft()
    response = client.post(
        "/api/insurance-narratives/approve-export",
        auth=operator_auth(),
        json={
            "packet": packet,
            "draft": draft,
            "reviewer": "reviewer@test",
            "notes": "Lineage check.",
            "approval_attestation": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    packet_id = packet["packet_id"]
    draft_id = draft["draft_id"]
    assert payload["packet"]["packet_id"] == packet_id
    assert payload["draft"]["draft_id"] == draft_id
    assert payload["review"]["packet_id"] == packet_id
    assert payload["review"]["draft_id"] == draft_id
    assert payload["export"]["packet_id"] == packet_id
    assert payload["export"]["draft_id"] == draft_id
    assert payload["export"]["review_id"] == payload["review"]["review_id"]


def test_approve_export_has_no_external_submission_side_effects() -> None:
    packet, draft = _ready_packet_and_draft()
    with patch("builtins.open", MagicMock()) as open_mock:
        with patch("urllib.request.urlopen", MagicMock()) as urlopen_mock:
            response = client.post(
                "/api/insurance-narratives/approve-export",
                auth=operator_auth(),
                json={
                    "packet": packet,
                    "draft": draft,
                    "reviewer": "reviewer@test",
                    "notes": "No side effects.",
                    "approval_attestation": True,
                },
            )

    assert response.status_code == 200
    assert response.json()["export"]["submission_status"] == "not_submitted"
    open_mock.assert_not_called()
    urlopen_mock.assert_not_called()


def test_insurance_narrative_endpoints_hidden_from_openapi() -> None:
    schema = app.openapi()
    paths = schema.get("paths", {})
    assert "/api/insurance-narratives/draft" not in paths
    assert "/api/insurance-narratives/approve-export" not in paths
