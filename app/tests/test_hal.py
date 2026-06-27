import json
import os
from datetime import datetime, timezone
from pathlib import Path
import pytest
from unittest.mock import patch
from uuid import uuid4

import app.hal.financial_tools as financial_tools
import app.hal.index_builder as index_builder_module
import app.hal.orchestrator as hal_orchestrator
from fastapi.testclient import TestClient

from app.auth import clear_user_registry_cache
from app.hal.audit import get_recent_hal_audits
from app.hal.charting import approve_hal_chart_plan, create_hal_chart_plan, list_hal_chart_plans
from app.hal.safety import create_ai_workspace_handle, get_ai_workspace_path
from app.hal.storage import get_hal_storage_path, hal_connection
from app.hal.vector_store import clear_hal_vector_store, count_hal_collection_documents, get_hal_chroma_path
from app.main import app


client = TestClient(app)


@pytest.fixture(autouse=True)
def disable_hal_ask_model_routing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HAL_ASK_MODEL_ROUTING", "0")
    # The financial source status payload is cached for 60s by default. Across
    # the full suite that cache leaks between tests and ignores per-test
    # monkeypatches, so disable it and clear any prior payload for isolation.
    monkeypatch.setenv("FINANCIAL_SOURCE_STATUS_CACHE_SECONDS", "0")
    financial_tools._financial_source_status_cache["payload"] = None
    financial_tools._financial_source_status_cache["expires_at"] = 0.0

TEST_RUNTIME_ROOT = Path(__file__).resolve().parent / ".hal_test_runtime"
TEST_AUTH_USERS_JSON = json.dumps(
    [
        {
            "username": "admin",
            "display_name": "Administrator",
            "password": "password",
            "roles": [
                "dashboard:read",
                "hal:operator",
                "hal:index:refresh",
                "admin",
                "softdent:read",
                "softdent:patient:read",
                "softdent:clinical:read",
                "softdent:ledger:read",
                "softdent:narrative:draft",
                "softdent:export:refresh",
            ],
        },
        {
            "username": "hal_operator",
            "display_name": "HAL Operator",
            "password": "hal-password",
            "roles": [
                "dashboard:read",
                "hal:operator",
                "softdent:read",
                "softdent:patient:read",
                "softdent:clinical:read",
                "softdent:ledger:read",
                "softdent:narrative:draft",
            ],
        },
        {
            "username": "operator_no_softdent",
            "display_name": "Operator Without SoftDent",
            "password": "no-softdent-password",
            "roles": ["dashboard:read", "hal:operator"],
        },
        {
            "username": "viewer",
            "display_name": "Dashboard Viewer",
            "password": "viewer-password",
            "roles": ["dashboard:read"],
        },
    ]
)

os.environ["APP_AUTH_USERS_JSON"] = TEST_AUTH_USERS_JSON


def basic_auth():
    return ("admin", "password")


def operator_auth():
    return ("hal_operator", "hal-password")


def operator_no_softdent_auth():
    return ("operator_no_softdent", "no-softdent-password")


def viewer_auth():
    return ("viewer", "viewer-password")


def setup_function():
    runtime_dir = TEST_RUNTIME_ROOT / uuid4().hex
    os.environ["APP_AUTH_USERS_JSON"] = TEST_AUTH_USERS_JSON
    os.environ["HAL_ALLOWED_BASE_PATH"] = str(runtime_dir)
    os.environ["HAL_SQLITE_PATH"] = str(runtime_dir / "hal_test.sqlite3")
    os.environ["HAL_CHROMA_PATH"] = str(runtime_dir / "hal_chroma")
    os.environ.pop("HAL_QB_REVENUE_SQL", None)
    os.environ.pop("HAL_QB_EXPENSES_SQL", None)
    os.environ.pop("HAL_QB_AR_SQL", None)
    clear_user_registry_cache()


def test_hal_page_exposes_local_policy():
    response = client.get("/hal9000", auth=operator_auth())

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "local-rag-phase-1"
    assert payload["access_policy"]["audited"] is True
    assert "browser-to-model" in payload["access_policy"]["network_boundary"]
    assert "deployment configuration" in payload["access_policy"]["auth_requirement"]
    assert payload["access_policy"]["workspace_root"] == ""
    assert payload["access_policy"]["activity_log_path"] == ""
    assert payload["access_policy"]["review_plan_directory"] == ""
    assert [item["tier"] for item in payload["access_policy"]["capability_hierarchy"]] == ["tier_1", "tier_2", "tier_3"]
    assert payload["access_policy"]["capability_hierarchy"][0]["priority"] == "high"


def test_hal_exported_paths_are_redacted(monkeypatch, tmp_path):
    workspace_root = tmp_path / "AI_Workspace"
    activity_log_path = workspace_root / "ai_activity.log"
    review_plan_directory = workspace_root / "review_plans"
    storage_path = tmp_path / "hal_local.sqlite3"
    vector_path = tmp_path / "hal_chroma"

    monkeypatch.setattr(hal_orchestrator, "get_ai_workspace_path", lambda: workspace_root)
    monkeypatch.setattr(hal_orchestrator, "get_ai_activity_log_path", lambda: activity_log_path)
    monkeypatch.setattr(hal_orchestrator, "get_ai_review_plan_directory", lambda: review_plan_directory)
    monkeypatch.setattr(hal_orchestrator, "get_hal_storage_path", lambda: storage_path)
    monkeypatch.setattr(hal_orchestrator, "get_hal_chroma_path", lambda: vector_path)
    monkeypatch.setattr(hal_orchestrator, "get_financial_source_status", lambda: {})
    monkeypatch.setattr(hal_orchestrator, "count_hal_collection_documents", lambda: 3)
    monkeypatch.setattr(
        hal_orchestrator,
        "refresh_hal_index",
        lambda: {
            "document_count": 3,
            "source_count": 2,
            "refreshed_at_utc": "2026-06-22T21:00:00+00:00",
            "storage_path": str(storage_path),
            "vector_path": str(vector_path),
            "backend": "chroma",
            "embedding_provider": "onnx-minilm",
        },
    )

    access_policy = hal_orchestrator.get_hal_access_policy()
    index_status = hal_orchestrator.get_hal_index_status()
    refresh_payload = hal_orchestrator.refresh_local_hal_index(actor="admin")
    autonomy_profile = hal_orchestrator.get_hal_autonomy_profile()

    assert access_policy["workspace_root"] == "AI_Workspace"
    assert access_policy["activity_log_path"] == "AI_Workspace/ai_activity.log"
    assert access_policy["review_plan_directory"] == "AI_Workspace/review_plans"
    assert index_status["storage_path"] == "hal_local.sqlite3"
    assert index_status["vector_path"] == "hal_chroma"
    assert refresh_payload["storage_path"] == "hal_local.sqlite3"
    assert refresh_payload["vector_path"] == "hal_chroma"
    assert autonomy_profile["state_management"]["storage_path"] == "hal_local.sqlite3"


def test_viewer_cannot_access_hal_routes():
    response = client.get("/hal9000", auth=viewer_auth())

    assert response.status_code == 403


def test_hal_question_sanitizes_and_audits():
    refresh_response = client.post("/api/hal9000/refresh-index", auth=basic_auth())

    assert refresh_response.status_code == 200
    refresh_payload = refresh_response.json()
    assert refresh_payload["document_count"] > 0
    assert refresh_payload["source_count"] >= 2
    assert count_hal_collection_documents() == refresh_payload["document_count"]
    assert get_hal_chroma_path().exists()
    assert refresh_payload["backend"] == "chroma"
    assert refresh_payload["embedding_provider"] == "onnx-minilm"

    response = client.post(
        "/hal9000",
        auth=operator_auth(),
        json={
            "question": "Patient John Doe called about claims on 01/02/2025. Phone 555-222-1212, MRN 778899.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "local-rag-phase-1"
    assert payload["audit_id"].startswith("hal-")
    assert "PATIENT_REDACTED" in payload["sanitized_question"]
    assert "DATE_REDACTED" in payload["sanitized_question"]
    assert "PHONE_REDACTED" in payload["sanitized_question"]
    assert "MRN_REDACTED" in payload["sanitized_question"]
    assert payload["retrieved_context"]
    assert "sanitized retrieval only" in payload["guardrails"]
    assert "tier-1 critical actions require explicit confirmation" in payload["guardrails"]
    assert "tier-2 mismatches raise [ALERT]" in payload["guardrails"]
    assert any(item["source_id"].startswith("hal_phi_rag_architecture") or item["source_id"].startswith("README") or item["source_id"].startswith("kpi") or item["source_id"].startswith("softdent") for item in payload["retrieved_context"])

    audits = get_recent_hal_audits(limit=1)
    assert audits
    assert audits[0]["audit_id"] == payload["audit_id"]
    assert audits[0]["actor"] == "hal_operator"
    assert get_hal_storage_path().exists()


def test_hal_operating_picture_handles_empty_completion_ledger(monkeypatch):
    monkeypatch.setattr(
        hal_orchestrator,
        "get_ollama_runtime_status",
        lambda *args, **kwargs: {
            "base_url": "http://127.0.0.1:11434",
            "installed": True,
            "running": True,
            "api_reachable": True,
            "installed_models": ["mistral-small3.1:24b"],
            "model_count": 1,
            "error": None,
        },
    )
    monkeypatch.setattr(hal_orchestrator, "_get_hal_model_routing", lambda: {"profiles": []})
    monkeypatch.setattr(hal_orchestrator, "_build_page_field_timeframe_registry", lambda financial_sources: {})
    monkeypatch.setattr(hal_orchestrator, "HAL_COMPLETION_LEDGER", [])

    payload = hal_orchestrator._build_hal_operating_picture({})

    assert "Latest completed work: none recorded yet." in payload["summary"]


def test_hal_question_handles_context_without_title(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(hal_orchestrator, "_get_conversation_state", lambda actor, session_id=None: {})
    monkeypatch.setattr(hal_orchestrator, "get_controlled_patient_context", lambda question, **_kwargs: {"matched": False, "snippets": [], "narrative": ""})
    monkeypatch.setattr(hal_orchestrator, "sanitize_hal_text", lambda question, **_kwargs: {"sanitized_text": question, "findings": []})
    monkeypatch.setattr(
        hal_orchestrator,
        "retrieve_relevant_context",
        lambda question, limit=3: [{"source_id": "retrieval-1", "excerpt": "Approved context without a title.", "category": "documentation"}],
    )
    monkeypatch.setattr(hal_orchestrator, "get_live_financial_context", lambda question, **_kwargs: [])
    monkeypatch.setattr(hal_orchestrator, "compile_hardware_snippets", lambda question, **_kwargs: [])
    monkeypatch.setattr(hal_orchestrator, "_build_hardware_review_actions", lambda question, **_kwargs: [])
    monkeypatch.setattr(hal_orchestrator, "compile_softdent_aggregate_snippets", lambda question, **_kwargs: [])
    monkeypatch.setattr(hal_orchestrator, "compile_live_report_snippets", lambda question, **_kwargs: [])
    monkeypatch.setattr(hal_orchestrator, "_build_hal_operating_picture", lambda financial_sources: {"summary": "backend-verified operating picture."})
    monkeypatch.setattr(hal_orchestrator, "get_financial_source_status", lambda: {})
    monkeypatch.setattr(hal_orchestrator, "_update_conversation_state", lambda **kwargs: None)
    monkeypatch.setattr(hal_orchestrator, "append_ai_activity_log", lambda **kwargs: None)

    def fake_record_hal_audit(**kwargs):
        captured.update(kwargs)
        return {"audit_id": "hal-test-context-title"}

    monkeypatch.setattr(hal_orchestrator, "record_hal_audit", fake_record_hal_audit)

    payload = hal_orchestrator.answer_hal_question(
        question="What do the approved docs say?",
        actor="hal_operator",
    )

    assert "Approved context without a title." in payload["answer"]
    assert "retrieval-1" not in payload["answer"]
    assert captured["retrieval_ids"] == ["retrieval-1"]


def test_accounting_policy_answer_handles_context_without_title(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(hal_orchestrator, "sanitize_hal_text", lambda question, **_kwargs: {"sanitized_text": question, "findings": []})
    monkeypatch.setattr(
        hal_orchestrator,
        "retrieve_relevant_context",
        lambda question, limit=4: [{"source_id": "policy-1", "excerpt": "Approved local accounting guidance."}],
    )
    monkeypatch.setattr(hal_orchestrator, "append_ai_activity_log", lambda **kwargs: None)
    monkeypatch.setattr(hal_orchestrator, "get_hal_access_policy", lambda: {"mode": "local-rag-phase-1"})

    def fake_record_hal_audit(**kwargs):
        captured.update(kwargs)
        return {"audit_id": "hal-test-accounting-policy"}

    monkeypatch.setattr(hal_orchestrator, "record_hal_audit", fake_record_hal_audit)

    payload = hal_orchestrator.answer_accounting_policy_question(
        question="How should I treat a supplies accrual?",
        topic="expense recognition",
        accounting_standard="GAAP",
        actor="hal_operator",
    )

    assert payload["citations"][0]["title"] == "policy-1"
    assert "policy-1" in payload["answer"]
    assert captured["retrieval_ids"] == ["policy-1"]


def test_compile_softdent_aggregate_snippets_tolerates_missing_status_excerpt(monkeypatch):
    monkeypatch.setattr(
        hal_orchestrator,
        "fetch_softdent_dashboard_aggregate",
        lambda: {
            "totals": {"production": 1000.0, "collections": 900.0, "insurance": 550.0, "patient": 350.0},
            "provider_rows": [
                {"provider_name": "Dr. Adams", "production_amount": 700.0, "collection_amount": 650.0},
                {"provider_name": "Dr. Baker", "production_amount": 300.0, "collection_amount": 250.0},
            ],
        },
    )
    monkeypatch.setattr(hal_orchestrator, "get_softdent_provider_ranking_status", lambda: {})

    snippets = hal_orchestrator.compile_softdent_aggregate_snippets("Show SoftDent provider ranking for production performance.")

    ranking_item = next(item for item in snippets if item["source_id"] == "softdent-live-provider-ranking")
    assert ranking_item["excerpt"] == "The current provider ranking context is not available."


def test_get_quickbooks_live_status_tolerates_missing_snippet_fields(monkeypatch):
    monkeypatch.setattr(financial_tools, "run_quickbooks_summary_tool", lambda topic: {})
    monkeypatch.setattr(financial_tools, "get_quickbooks_source_status", lambda topic: {})

    payload = financial_tools.get_quickbooks_live_status("revenue")

    assert payload["available"] is False
    assert payload["source_id"] == "quickbooks-revenue-unavailable"
    assert payload["excerpt"] == "QuickBooks revenue summary is unavailable from the approved local sources."
    assert "live quickbooks summary missing" in payload["review_flags"]


def test_insurance_narrative_request_handles_supporting_context_without_source_id(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        hal_orchestrator,
        "get_controlled_patient_context",
        lambda question, **_kwargs: {
            "matched": True,
            "narrative": "Approved patient narrative.",
            "summary_fields": {"patient_name": "Pat Doe", "claim_count": 1, "note_count": 1},
            "snippets": [{"title": "patient-claims", "excerpt": "Approved claim context."}],
        },
    )
    monkeypatch.setattr(hal_orchestrator, "sanitize_hal_text", lambda question, **_kwargs: {"sanitized_text": question, "findings": []})
    monkeypatch.setattr(hal_orchestrator, "get_hal_access_policy", lambda: {"mode": "local-rag-phase-1"})

    def fake_record_hal_audit(**kwargs):
        captured.update(kwargs)
        return {"audit_id": "hal-test-insurance-narrative"}

    monkeypatch.setattr(hal_orchestrator, "record_hal_audit", fake_record_hal_audit)

    payload = hal_orchestrator.answer_insurance_narrative_request(
        question="Draft a narrative for this patient claim.",
        actor="hal_operator",
    )

    assert payload["matched"] is True
    assert captured["retrieval_ids"] == ["patient-claims"]


def test_draft_accounting_journal_entry_handles_supporting_context_without_source_id(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(hal_orchestrator, "sanitize_hal_text", lambda text: {"sanitized_text": text, "findings": []})
    monkeypatch.setattr(
        hal_orchestrator,
        "retrieve_relevant_context",
        lambda question, limit=3: [{"title": "journal-context", "excerpt": "Approved accounting background."}],
    )
    monkeypatch.setattr(hal_orchestrator, "_try_local_ai_journal_draft", lambda **kwargs: None)
    monkeypatch.setattr(
        hal_orchestrator,
        "draft_journal_entry_for_common_case",
        lambda **kwargs: [
            {"account_code": "1310", "account_name": "Prepaid Insurance", "debit": 100.0, "credit": 0.0, "memo": "Draft"},
            {"account_code": "1010", "account_name": "Cash", "debit": 0.0, "credit": 100.0, "memo": "Draft"},
        ],
    )
    monkeypatch.setattr(
        hal_orchestrator,
        "build_journal_validation",
        lambda **kwargs: {
            "balanced": True,
            "debit_total": 100.0,
            "credit_total": 100.0,
            "open_period": True,
            "account_validation_passed": True,
            "amount_validation_passed": True,
            "issues": [],
        },
    )
    monkeypatch.setattr(hal_orchestrator, "get_chart_of_accounts", lambda: {"1310": "Prepaid Insurance", "1010": "Cash"})
    monkeypatch.setattr(hal_orchestrator, "is_period_open", lambda period: True)
    monkeypatch.setattr(hal_orchestrator, "write_review_step_file", lambda **kwargs: "AI_Workspace/review_plans/test-review.json")
    monkeypatch.setattr(hal_orchestrator, "append_ai_activity_log", lambda **kwargs: None)
    monkeypatch.setattr(hal_orchestrator, "get_hal_access_policy", lambda: {"mode": "local-rag-phase-1"})

    def fake_record_hal_audit(**kwargs):
        captured.update(kwargs)
        return {"audit_id": "hal-test-journal-draft"}

    monkeypatch.setattr(hal_orchestrator, "record_hal_audit", fake_record_hal_audit)

    payload = hal_orchestrator.draft_accounting_journal_entry(
        description="Record prepaid insurance for June coverage.",
        transaction_date="2026-06-15",
        accounting_period="2026-06",
        amount=100.0,
        context={},
        actor="hal_operator",
    )

    assert payload["audit_id"] == "hal-test-journal-draft"
    assert captured["retrieval_ids"] == ["journal-context"]


def test_hal_phases_are_reported():
    response = client.get("/api/hal9000/phases", auth=operator_auth())

    assert response.status_code == 200
    assert "Sanitize question" in response.json()["phases"]


def test_hal_chart_plan_returns_pending_review_artifacts():
    workspace_root = get_ai_workspace_path()
    mocked_payload = {
        "mode": "local-rag-phase-1",
        "status": "pending_human_review",
        "question": "Create a bar chart for June overhead.",
        "request_json": {
            "chart_config": {
                "chart_type": "bar",
                "title": "June Overhead",
                "x_axis_label": "Category",
                "y_axis_label": "Amount",
            },
            "chart_data": [
                {"label": "Software", "value": 540.0},
                {"label": "Rent", "value": 1200.0},
            ],
        },
        "request_file_path": str(workspace_root / "request.json"),
        "planned_output_path": str(workspace_root / "output.png"),
        "review_plan_path": str(workspace_root / "review.json"),
        "preview_summary": "Chart preview: June Overhead",
        "flag_for_review": False,
        "review_reason": None,
        "alert_reason": None,
        "guardrails": ["structured chart JSON only"],
        "audit_id": "hal-chart-123",
        "access_policy": {
            "mode": "local-rag-phase-1",
            "auth_requirement": "auth",
            "network_boundary": "local-only backend mediation",
            "audited": True,
            "allowed_sources": ["approved_local_read_only_scope"],
            "disallowed_actions": ["direct_hardware_writes"],
            "capability_hierarchy": [],
        },
    }

    with patch("app.routes.create_hal_chart_plan", return_value=mocked_payload):
        response = client.post(
            "/api/hal9000/chart-plan",
            auth=operator_auth(),
            json={"question": "Create a bar chart for June overhead."},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "pending_human_review"
    assert payload["request_json"]["chart_config"]["chart_type"] == "bar"
    assert payload["review_plan_path"] == create_ai_workspace_handle(workspace_root / "review.json")
    assert payload["planned_output_path"] == create_ai_workspace_handle(workspace_root / "output.png")


def test_hal_chart_plan_approve_returns_rendered_artifact():
    workspace_root = get_ai_workspace_path()
    mocked_payload = {
        "mode": "local-rag-phase-1",
        "status": "approved_and_rendered",
        "review_plan_path": str(workspace_root / "review.json"),
        "request_json": {
            "chart_config": {
                "chart_type": "bar",
                "title": "June Overhead",
                "x_axis_label": "Category",
                "y_axis_label": "Amount",
            },
            "chart_data": [
                {"label": "Software", "value": 540.0},
                {"label": "Rent", "value": 1200.0},
            ],
        },
        "rendered_output_path": str(workspace_root / "output.png"),
        "flag_for_review": False,
        "review_reason": None,
        "alert_reason": None,
        "guardrails": ["human approval recorded before PNG render"],
        "audit_id": "hal-chart-123",
        "access_policy": {
            "mode": "local-rag-phase-1",
            "auth_requirement": "auth",
            "network_boundary": "local-only backend mediation",
            "audited": True,
            "allowed_sources": ["approved_local_read_only_scope"],
            "disallowed_actions": ["direct_hardware_writes"],
            "capability_hierarchy": [],
        },
    }

    encoded_review_plan = create_ai_workspace_handle(workspace_root / "review.json")

    with patch("app.routes.approve_hal_chart_plan", return_value=mocked_payload) as approve_mock:
        response = client.post(
            "/api/hal9000/chart-plan/approve",
            auth=operator_auth(),
            json={"review_plan_path": encoded_review_plan},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "approved_and_rendered"
    assert payload["rendered_output_path"] == create_ai_workspace_handle(workspace_root / "output.png")
    approve_mock.assert_called_once_with(review_plan_path=str(workspace_root / "review.json"), actor="hal_operator")


def test_hal_chart_plan_integration_writes_png_and_updates_review_file(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HAL_ALLOWED_BASE_PATH", str(tmp_path))
    workspace_root = tmp_path / "AI_Workspace"
    monkeypatch.setenv("HAL_AI_WORKSPACE_PATH", str(workspace_root))

    generated_payload = {
        "chart_config": {
            "chart_type": "bar",
            "title": "June Overhead Variance",
            "x_axis_label": "Category",
            "y_axis_label": "Amount",
            "value_format": "currency",
        },
        "chart_data": [
            {"label": "Software", "value": 540.0},
            {"label": "Rent", "value": 1200.0},
        ],
        "flag_for_review": True,
        "review_reason": "Generated from narrative prompt; confirm values before rendering.",
        "alert_reason": "Potential discrepancy: narrative prompt did not cite a source file.",
    }

    monkeypatch.setattr("app.hal.charting.local_ai_finance.generate_chart_request", lambda **kwargs: generated_payload.copy())

    plan = create_hal_chart_plan(question="Create a bar chart showing June overhead variance by category.", actor="hal_operator")

    review_plan_path = Path(str(plan["review_plan_path"]))
    assert review_plan_path.exists()
    assert Path(str(plan["request_file_path"])).exists()

    result = approve_hal_chart_plan(review_plan_path=str(review_plan_path), actor="hal_operator")

    rendered_output_path = Path(str(result["rendered_output_path"]))
    assert rendered_output_path.exists()
    assert rendered_output_path.suffix.lower() == ".png"

    review_document = json.loads(review_plan_path.read_text(encoding="utf-8"))
    assert review_document["status"] == "approved_and_rendered"
    assert review_document["reviewer_actor"] == "hal_operator"
    assert review_document["rendered_output_path"] == str(rendered_output_path)

    listing = list_hal_chart_plans(limit=10)
    assert listing["count"] >= 1
    assert listing["items"][0]["review_plan_path"] == str(review_plan_path)
    assert listing["items"][0]["rendered_output_path"] == str(rendered_output_path)
    approved_listing = list_hal_chart_plans(limit=10, status="approved_and_rendered")
    assert approved_listing["count"] >= 1
    pending_listing = list_hal_chart_plans(limit=10, status="pending_human_approval")
    assert pending_listing["count"] == 0


def test_hal_chart_plan_list_route_and_chart_file_route(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HAL_ALLOWED_BASE_PATH", str(tmp_path))
    workspace_root = tmp_path / "AI_Workspace"
    monkeypatch.setenv("HAL_AI_WORKSPACE_PATH", str(workspace_root))

    review_dir = workspace_root / "review_plans"
    review_dir.mkdir(parents=True, exist_ok=True)
    chart_path = workspace_root / "2026-06-16-june-overhead-variance.png"
    chart_path.write_bytes(b"mock-png")
    review_path = review_dir / "20260616T120000Z-hal-chart-render.json"
    review_path.write_text(
        json.dumps(
            {
                "created_at_utc": "2026-06-16T12:00:00+00:00",
                "tier": "tier_1",
                "actor": "hal_operator",
                "action": "hal_chart_render",
                "summary": "Chart preview: June Overhead Variance",
                "approval_required": True,
                "status": "approved_and_rendered",
                "rendered_output_path": str(chart_path),
                "payload": {
                    "audit_id": "hal-chart-123",
                    "question": "Create a bar chart showing June overhead variance by category.",
                    "planned_output_path": str(chart_path),
                    "chart_request": {
                        "chart_config": {
                            "chart_type": "bar",
                            "title": "June Overhead Variance",
                        }
                    },
                },
            },
            indent=2,
        ),
        encoding="utf-8",
        newline="\n",
    )

    list_response = client.get("/api/hal9000/chart-plans?limit=5&status=approved_and_rendered", auth=operator_auth())
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert list_payload["count"] == 1
    assert list_payload["status"] == "approved_and_rendered"
    assert list_payload["items"][0]["title"] == "June Overhead Variance"

    chart_handle = create_ai_workspace_handle(chart_path)
    file_response = client.get(f"/api/hal9000/chart-files?path={chart_handle}", auth=operator_auth())
    assert file_response.status_code == 200
    assert file_response.content == b"mock-png"


def test_hal_status_reports_vector_backend():
    client.post("/api/hal9000/refresh-index", auth=basic_auth())

    def fake_live_status(topic: str):
        return {
            "topic": topic,
            "available": topic == "revenue",
            "health": "ok" if topic == "revenue" else "warning",
            "source_backend": "sdk" if topic == "revenue" else "unavailable",
            "source_id": f"quickbooks-{topic}-summary" if topic == "revenue" else f"quickbooks-{topic}-unavailable",
            "excerpt": f"Mocked {topic} live status",
            "checked_at_utc": "2026-06-15T12:00:00+00:00",
        }

    from unittest.mock import patch

    with patch.object(financial_tools, "get_quickbooks_live_status", fake_live_status):
        response = client.get("/api/hal9000/status", auth=operator_auth())

    assert response.status_code == 200
    payload = response.json()
    assert payload["backend"] == "chroma"
    assert payload["embedding_provider"] == "onnx-minilm"
    assert payload["document_count"] > 0
    assert payload["financial_sources"]["softdent"]["available"] is True
    assert payload["financial_sources"]["softdent"]["provider_count"] >= 1


def test_hal_path_overrides_reject_out_of_bounds_paths(tmp_path: Path, monkeypatch):
    outside_root = tmp_path.parent / f"{tmp_path.name}-outside"
    monkeypatch.setenv("HAL_ALLOWED_BASE_PATH", str(tmp_path))

    monkeypatch.setenv("HAL_AI_WORKSPACE_PATH", str(outside_root / "AI_Workspace"))
    with pytest.raises(ValueError, match="HAL AI workspace path is outside HAL allowed base path"):
        get_ai_workspace_path()

    monkeypatch.setenv("HAL_CHROMA_PATH", str(outside_root / "hal_chroma"))
    with pytest.raises(ValueError, match="HAL vector store path is outside HAL allowed base path"):
        get_hal_chroma_path()

    monkeypatch.setenv("HAL_SQLITE_PATH", str(outside_root / "hal_local.sqlite3"))
    with pytest.raises(ValueError, match="HAL SQLite storage path is outside HAL allowed base path"):
        get_hal_storage_path()


def test_hal_path_overrides_reject_unsafe_in_bounds_paths(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HAL_ALLOWED_BASE_PATH", str(tmp_path))

    monkeypatch.setenv("HAL_AI_WORKSPACE_PATH", str(tmp_path))
    with pytest.raises(ValueError, match="dedicated 'AI_Workspace' directory directly under HAL allowed base path"):
        get_ai_workspace_path()

    monkeypatch.setenv("HAL_AI_WORKSPACE_PATH", str(tmp_path / "review_plans"))
    with pytest.raises(ValueError, match="dedicated 'AI_Workspace' directory directly under HAL allowed base path"):
        get_ai_workspace_path()

    monkeypatch.setenv("HAL_CHROMA_PATH", str(tmp_path))
    with pytest.raises(ValueError, match="dedicated 'hal_chroma' directory directly under HAL allowed base path"):
        get_hal_chroma_path()

    monkeypatch.setenv("HAL_CHROMA_PATH", str(tmp_path / "frontend"))
    with pytest.raises(ValueError, match="dedicated 'hal_chroma' directory directly under HAL allowed base path"):
        get_hal_chroma_path()


def test_clear_hal_vector_store_rejects_allowed_base_deletion(tmp_path: Path, monkeypatch):
    protected_file = tmp_path / "keep.txt"
    protected_file.write_text("keep", encoding="utf-8")
    monkeypatch.setenv("HAL_ALLOWED_BASE_PATH", str(tmp_path))
    monkeypatch.setenv("HAL_CHROMA_PATH", str(tmp_path))

    with pytest.raises(ValueError, match="dedicated 'hal_chroma' directory directly under HAL allowed base path"):
        clear_hal_vector_store()

    assert protected_file.exists()


def test_hal_connection_discards_uncommitted_changes_on_exception():
    audit_id = f"hal-{uuid4().hex[:12]}"

    with pytest.raises(RuntimeError, match="boom"):
        with hal_connection() as connection:
            connection.execute(
                """
                INSERT INTO hal_audits (
                    audit_id,
                    created_at_utc,
                    actor,
                    mode,
                    sanitized_question,
                    retrieval_ids_json,
                    response_summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    audit_id,
                    datetime.now(timezone.utc).isoformat(),
                    "tester",
                    "local-rag-phase-1",
                    "sanitized",
                    "[]",
                    "summary",
                ),
            )
            raise RuntimeError("boom")

    with hal_connection() as connection:
        row = connection.execute("SELECT audit_id FROM hal_audits WHERE audit_id = ?", (audit_id,)).fetchone()

    assert row is None


def test_refresh_hal_index_reports_dynamic_source_count(monkeypatch, tmp_path: Path):
    source_files = [tmp_path / "a.md", tmp_path / "b.md"]

    monkeypatch.setattr(index_builder_module, "_get_document_source_files", lambda: source_files)
    monkeypatch.setattr(
        index_builder_module,
        "_chunk_markdown",
        lambda path: [
            {
                "source_id": f"{path.stem}-1",
                "title": f"{path.stem} chunk 1",
                "category": "documentation",
                "sanitized_content": f"chunk from {path.name}",
            },
            {
                "source_id": f"{path.stem}-2",
                "title": f"{path.stem} chunk 2",
                "category": "documentation",
                "sanitized_content": f"chunk two from {path.name}",
            },
        ] if path.name == "a.md" else [
            {
                "source_id": f"{path.stem}-1",
                "title": f"{path.stem} chunk 1",
                "category": "documentation",
                "sanitized_content": f"chunk from {path.name}",
            }
        ],
    )
    monkeypatch.setattr(
        index_builder_module,
        "_build_kpi_documents",
        lambda: [
            {
                "source_id": "kpi-current-summary",
                "title": "Current KPI summary",
                "category": "kpi",
                "sanitized_content": "kpi",
            }
        ],
    )
    monkeypatch.setattr(
        index_builder_module,
        "build_financial_snapshot_documents",
        lambda: [
            {
                "source_id": "softdent-financial-snapshot",
                "title": "SoftDent financial snapshot",
                "category": "softdent",
                "sanitized_content": "snapshot",
            },
            {
                "source_id": "softdent-provider-ranking",
                "title": "SoftDent provider ranking",
                "category": "softdent",
                "sanitized_content": "ranking",
            },
            {
                "source_id": "softdent-payer-mix",
                "title": "SoftDent payer mix summary",
                "category": "softdent",
                "sanitized_content": "mix",
            },
            {
                "source_id": "quickbooks-tool-policy",
                "title": "QuickBooks controlled summary policy",
                "category": "quickbooks",
                "sanitized_content": "policy",
            },
        ],
    )
    monkeypatch.setattr(
        index_builder_module,
        "build_knowledge_memory_documents",
        lambda: [
            {
                "source_id": "memory-test-fixture",
                "title": "HAL memory: test-fixture",
                "category": "knowledge_memory",
                "sanitized_content": "guidance only fixture",
            }
        ],
    )
    monkeypatch.setattr(
        index_builder_module,
        "rebuild_hal_collection",
        lambda documents: {
            "backend": "chroma",
            "embedding_provider": "onnx-minilm",
            "vector_path": str(tmp_path / "hal_chroma"),
            "document_count": len(documents),
        },
    )
    monkeypatch.setattr(index_builder_module, "get_hal_storage_path", lambda: tmp_path / "hal_local.sqlite3")

    payload = index_builder_module.refresh_hal_index()

    assert payload["document_count"] == 9
    assert payload["source_count"] == 8
    assert payload["storage_path"] == str(tmp_path / "hal_local.sqlite3")


def test_hal_status_includes_operating_picture(monkeypatch):
    monkeypatch.setattr(
        "app.hal.orchestrator.get_ollama_runtime_status",
        lambda base_url, timeout_seconds=5: {
            "base_url": base_url,
            "installed": True,
            "running": True,
            "api_reachable": True,
            "installed_models": ["mistral-small3.1:24b", "qwen2.5-coder:14b", "qwen3:30b"],
            "model_count": 3,
            "error": None,
        },
    )

    response = client.get("/api/hal9000/status", auth=operator_auth())

    assert response.status_code == 200
    payload = response.json()
    operating_picture = payload["operating_picture"]
    assert operating_picture["operator_mode"] == "deterministic_server_facts_first"
    assert operating_picture["local_runtime"]["api_reachable"] is True
    assert len(operating_picture["capability_matrix"]) == 12
    assert len(operating_picture["file_ownership_areas"]) == 10
    assert len(operating_picture["completion_ledger"]) == 2
    assert operating_picture["completion_ledger"][-1]["entry_id"] == "unit-test-completion-ledger"
    assert operating_picture["model_routing"]["primary"]["model"] == "mistral-small3.1:24b"
    assert operating_picture["model_routing"]["second_opinion"]["model"] == "qwen3:30b"
    assert operating_picture["model_routing"]["code_help"]["model"] == "qwen3:30b"
    assert any(item["path"] == "/api/hal/shell/commands" for item in operating_picture["developer_operator_endpoints"])


def test_hal_question_uses_operating_picture_voice(monkeypatch):
    monkeypatch.setattr(
        "app.hal.orchestrator.get_ollama_runtime_status",
        lambda base_url, timeout_seconds=5: {
            "base_url": base_url,
            "installed": True,
            "running": True,
            "api_reachable": True,
            "installed_models": ["mistral-small3.1:24b"],
            "model_count": 1,
            "error": None,
        },
    )

    response = client.post(
        "/hal9000",
        auth=operator_auth(),
        json={"question": "Give me the current HAL operating picture for financial review."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "backend-verified operating picture" in payload["answer"]
    assert "deterministic server facts first" in payload["guardrails"]
    assert "approved QuickBooks read-only summaries" in payload["answer"]


def test_hal_status_includes_live_softdent_snapshot(monkeypatch):
    def fake_snapshot():
        return {
            "available": True,
            "period": "2026-06",
            "provider_count": 2,
            "providers": [
                {"provider": "Dr. Adams", "period": "2026-06", "production": 55000.0, "collections": 50000.0, "insurance": 30000.0, "patient": 20000.0},
                {"provider": "Dr. Lee", "period": "2026-06", "production": 40000.0, "collections": 37000.0, "insurance": 22000.0, "patient": 15000.0},
            ],
            "totals": {
                "production": 95000.0,
                "collections": 87000.0,
                "insurance": 52000.0,
                "patient": 35000.0,
            },
        }

    def fake_aggregate_snapshot():
        return {
            "source_file": "softdent_dashboard_data.json",
            "period_start": "2026-06-01",
            "period_end": "2026-06-30",
            "provider_count": 2,
            "provider_rows": [
                {
                    "provider_id": "dradams",
                    "provider_name": "Dr. Adams",
                    "production_amount": 55000.0,
                    "collection_amount": 50000.0,
                },
                {
                    "provider_id": "drlee",
                    "provider_name": "Dr. Lee",
                    "production_amount": 40000.0,
                    "collection_amount": 37000.0,
                },
            ],
            "totals": {
                "production": 95000.0,
                "collections": 87000.0,
                "insurance": 52000.0,
                "patient": 35000.0,
            },
            "data_complete": True,
        }

    def fake_source_status():
        return {
            "available": True,
            "source_backend": "json",
            "source_file": "softdent_dashboard_data.json",
            "modified_at_utc": "2026-06-15T12:00:00+00:00",
        }

    def fake_claim_source_status():
        return {
            "available": True,
            "source_backend": "csv",
            "source_file": "softdent_claims_export.csv",
            "modified_at_utc": "2026-06-15T12:05:00+00:00",
        }

    def fake_note_source_status():
        return {
            "available": True,
            "source_backend": "json",
            "source_file": "softdent_clinical_notes_data.json",
            "modified_at_utc": "2026-06-15T12:06:00+00:00",
        }

    def fake_claim_rows():
        return [{"ClaimId": "1001", "ClaimStatus": "Denied", "Payer": "Delta Dental", "ClaimAmount": 215.75}]

    def fake_note_rows():
        return [{"NoteDate": "2026-06-15", "Provider": "Dr. Adams", "ClinicalNote": "Patient reports sensitivity."}]

    monkeypatch.setattr(financial_tools, "build_softdent_snapshot", fake_snapshot)
    monkeypatch.setattr(financial_tools, "fetch_softdent_dashboard_aggregate", fake_aggregate_snapshot)
    monkeypatch.setattr(financial_tools, "get_softdent_source_status", fake_source_status)
    monkeypatch.setattr(financial_tools, "get_softdent_claim_source_status", fake_claim_source_status)
    monkeypatch.setattr(financial_tools, "get_softdent_clinical_note_source_status", fake_note_source_status)
    monkeypatch.setattr(financial_tools, "load_softdent_claim_rows", fake_claim_rows)
    monkeypatch.setattr(financial_tools, "load_softdent_clinical_note_rows", fake_note_rows)

    response = client.get("/api/hal9000/status", auth=operator_auth())

    assert response.status_code == 200
    softdent_payload = response.json()["financial_sources"]["softdent"]
    live_snapshot = softdent_payload["live_snapshot"]
    assert live_snapshot["available"] is True
    assert live_snapshot["health"] == "ok"
    assert live_snapshot["source_backend"] == "json"
    assert live_snapshot["source_file"] == "softdent_dashboard_data.json"
    assert live_snapshot["modified_at_utc"] == "2026-06-15T12:00:00+00:00"
    assert "production 95000.0" in live_snapshot["excerpt"]
    assert "Rank 1:" in softdent_payload["live_provider_ranking"]["excerpt"]
    assert "insurance collections share" in softdent_payload["live_payer_mix"]["excerpt"]
    assert "delta 8000.0" in softdent_payload["live_collection_delta"]["excerpt"]
    assert softdent_payload["live_claims"]["source_file"] == "softdent_claims_export.csv"
    assert "1 row(s)" in softdent_payload["live_claims"]["excerpt"]
    assert softdent_payload["live_clinical_notes"]["source_file"] == "softdent_clinical_notes_data.json"
    assert "ClinicalNote=" in softdent_payload["live_clinical_notes"]["excerpt"]
    assert "Patient reports sensitivity." in softdent_payload["live_clinical_notes"]["excerpt"]


def test_hal_question_includes_softdent_live_summary(canonical_softdent_dashboard):
    client.post("/api/hal9000/refresh-index", auth=basic_auth())

    response = client.post(
        "/hal9000",
        auth=operator_auth(),
        json={"question": "Show SoftDent production and collections summary."},
    )

    assert response.status_code == 200
    payload = response.json()
    summary_item = next(item for item in payload["retrieved_context"] if item["source_id"] == "softdent-live-summary")

    assert summary_item["category"] == "softdent_aggregate"
    assert summary_item["title"] == "Verified SoftDent practice performance snapshot (2026-06-01 to 2026-06-30)"
    assert "$116,780.00" in summary_item["excerpt"]
    assert "$107,015.00" in summary_item["excerpt"]
    assert "Verified SoftDent metrics:" in payload["answer"]
    assert "Production=$116,780.00 | Collections=$107,015.00 (91.64% Collection Ratio)" in payload["answer"]
    assert "Providers tracking 3." not in payload["answer"]


def test_hal_question_surfaces_retrieved_guidance(monkeypatch):
    import app.hal.orchestrator as orchestrator

    monkeypatch.setattr(orchestrator, "get_controlled_patient_context", lambda question, **_kwargs: {"matched": False, "snippets": [], "narrative": ""})
    monkeypatch.setattr(orchestrator, "get_live_financial_context", lambda question, **_kwargs: [])

    monkeypatch.setattr(
        orchestrator,
        "retrieve_relevant_context",
        lambda question, **_kwargs: [
            {
                "source_id": "softdent_bridge_automation-25",
                "title": "softdent_bridge_automation chunk 25",
                "category": "documentation",
                "excerpt": "Run `softdent: activate bridge exports` to stage the current bridge export drop into the repo root.",
            },
            {
                "source_id": "softdent_bridge_automation-29",
                "title": "softdent_bridge_automation chunk 29",
                "category": "documentation",
                "excerpt": "Run `softdent: activate demo mode` to clear staged files and rebuild the canonical demo exports.",
            },
        ],
    )

    payload = orchestrator.answer_hal_question(
        question="How do I switch HAL between the current SoftDent bridge exports and demo mode?",
        actor="admin",
    )

    assert "activate bridge exports" in payload["answer"]
    assert "activate demo mode" in payload["answer"]
    assert any(item["source_id"] == "softdent_bridge_automation-25" for item in payload["retrieved_context"])
    assert any(item["source_id"] == "softdent_bridge_automation-29" for item in payload["retrieved_context"])
    assert "backend-verified operating picture" not in payload["answer"]
    assert "Priority routing applies:" not in payload["answer"]


def test_hal_question_appends_profit_loss_report_snippet(monkeypatch):
    import app.hal.orchestrator as orchestrator

    monkeypatch.setattr(orchestrator, "get_controlled_patient_context", lambda question, **_kwargs: {"matched": False, "snippets": [], "narrative": ""})
    monkeypatch.setattr(orchestrator, "get_live_financial_context", lambda question, **_kwargs: [])
    monkeypatch.setattr(orchestrator, "retrieve_relevant_context", lambda question, **_kwargs: [])
    monkeypatch.setattr(orchestrator, "get_financial_source_status", lambda: {})
    monkeypatch.setattr(orchestrator, "_build_hal_operating_picture", lambda financial_sources: {"summary": "backend-verified operating picture."})
    monkeypatch.setattr(
        orchestrator,
        "get_profit_loss_report",
        lambda period: {
            "source_backend": "env",
            "period": {"start_date": period.start_date, "end_date": period.end_date},
            "rows": [],
            "summary_fields": {
                "total_revenue": 18250.25,
                "total_expense": 7450.10,
                "net_income": 10800.15,
            },
            "health": {"data_complete": True, "period_bound": False, "warning": "Approved summary rows only.", "error": None},
        },
    )

    payload = orchestrator.answer_hal_question(
        question="Show QuickBooks P&L for 2026-06-01 to 2026-06-30.",
        actor="admin",
    )

    report_item = next(item for item in payload["retrieved_context"] if item["source_id"] == "qb-pl-2026-06-01-2026-06-30")
    assert report_item["title"] == "QuickBooks verified profit and loss 2026-06-01 to 2026-06-30"
    assert "source backend env" in report_item["excerpt"]
    assert "$18,250.25" in report_item["excerpt"]
    assert "$10,800.15" in report_item["excerpt"]
    assert "period bound False" in report_item["excerpt"]
    assert "Verified report metrics:" in payload["answer"]
    assert "$18,250.25" in payload["answer"]
    assert "$7,450.10" in payload["answer"]
    assert "$10,800.15" in payload["answer"]
    assert "QuickBooks verified profit and loss 2026-06-01 to 2026-06-30" in payload["answer"]


def test_hal_question_appends_unconfigured_balance_sheet_snippet(monkeypatch):
    import app.hal.orchestrator as orchestrator

    monkeypatch.setattr(orchestrator, "get_controlled_patient_context", lambda question, **_kwargs: {"matched": False, "snippets": [], "narrative": ""})
    monkeypatch.setattr(orchestrator, "get_live_financial_context", lambda question, **_kwargs: [])
    monkeypatch.setattr(orchestrator, "retrieve_relevant_context", lambda question, **_kwargs: [])
    monkeypatch.setattr(orchestrator, "get_financial_source_status", lambda: {})
    monkeypatch.setattr(orchestrator, "_build_hal_operating_picture", lambda financial_sources: {"summary": "backend-verified operating picture."})
    monkeypatch.setattr(
        orchestrator,
        "get_balance_sheet_report",
        lambda period: {
            "source_backend": "empty",
            "period": {"start_date": period.start_date, "end_date": period.end_date},
            "rows": [],
            "summary_fields": {},
            "health": {
                "data_complete": False,
                "period_bound": False,
                "warning": "No verified balance-sheet fallback surface exists in this repo yet.",
                "error": "No approved balance sheet query is configured.",
            },
        },
    )

    payload = orchestrator.answer_hal_question(
        question="Show QuickBooks balance sheet for 2026-06-30.",
        actor="admin",
    )

    report_item = next(item for item in payload["retrieved_context"] if item["source_id"] == "qb-balance-sheet-2026-06-30")
    assert report_item["title"] == "QuickBooks verified balance sheet as of 2026-06-30"
    assert "source backend empty" in report_item["excerpt"]
    assert "data complete False" in report_item["excerpt"]
    assert "No approved balance sheet query is configured." in report_item["excerpt"]
    assert "QuickBooks verified balance sheet as of 2026-06-30" in payload["answer"]


def test_extract_report_period_resolves_relative_phrases(monkeypatch):
    import app.hal.orchestrator as orchestrator

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 6, 16, 12, 0, 0, tzinfo=tz or timezone.utc)

    monkeypatch.setattr(orchestrator, "datetime", FixedDateTime)

    last_month = orchestrator._extract_report_period("What is our QuickBooks P&L for last month?")
    this_month = orchestrator._extract_report_period("Show QuickBooks revenue for this month.")
    this_quarter = orchestrator._extract_report_period("Show QuickBooks balance sheet for this quarter.")

    assert last_month.start_date == "2026-05-01"
    assert last_month.end_date == "2026-05-31"
    assert this_month.start_date == "2026-06-01"
    assert this_month.end_date == "2026-06-16"
    assert this_quarter.start_date == "2026-04-01"
    assert this_quarter.end_date == "2026-06-16"


def test_extract_report_period_defaults_safely(monkeypatch):
    import app.hal.orchestrator as orchestrator

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 6, 16, 12, 0, 0, tzinfo=tz or timezone.utc)

    monkeypatch.setattr(orchestrator, "datetime", FixedDateTime)

    period = orchestrator._extract_report_period("Show QuickBooks profit and loss.")

    assert period.start_date == "2026-06-01"
    assert period.end_date == "2026-06-16"


def test_hal_question_appends_last_month_profit_loss_snippet(monkeypatch):
    import app.hal.orchestrator as orchestrator

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 6, 16, 12, 0, 0, tzinfo=tz or timezone.utc)

    monkeypatch.setattr(orchestrator, "datetime", FixedDateTime)
    monkeypatch.setattr(orchestrator, "get_controlled_patient_context", lambda question, **_kwargs: {"matched": False, "snippets": [], "narrative": ""})
    monkeypatch.setattr(orchestrator, "get_live_financial_context", lambda question, **_kwargs: [])
    monkeypatch.setattr(orchestrator, "retrieve_relevant_context", lambda question, **_kwargs: [])
    monkeypatch.setattr(orchestrator, "get_financial_source_status", lambda: {})
    monkeypatch.setattr(orchestrator, "_build_hal_operating_picture", lambda financial_sources: {"summary": "backend-verified operating picture."})
    monkeypatch.setattr(
        orchestrator,
        "get_profit_loss_report",
        lambda period: {
            "source_backend": "env",
            "period": {"start_date": period.start_date, "end_date": period.end_date},
            "rows": [],
            "summary_fields": {
                "total_revenue": 22500.0,
                "total_expense": 9100.0,
                "net_income": 13400.0,
            },
            "health": {"data_complete": True, "period_bound": False, "warning": "Approved summary rows only.", "error": None},
        },
    )

    payload = orchestrator.answer_hal_question(
        question="Show QuickBooks P&L for last month.",
        actor="admin",
    )

    report_item = next(item for item in payload["retrieved_context"] if item["source_id"] == "qb-pl-2026-05-01-2026-05-31")
    assert report_item["title"] == "QuickBooks verified profit and loss 2026-05-01 to 2026-05-31"
    assert "$22,500.00" in report_item["excerpt"]
    assert "$13,400.00" in report_item["excerpt"]
    assert "QuickBooks verified profit and loss 2026-05-01 to 2026-05-31" in payload["answer"]


def test_hal_question_includes_softdent_provider_ranking_context(canonical_softdent_dashboard):
    client.post("/api/hal9000/refresh-index", auth=basic_auth())

    response = client.post(
        "/hal9000",
        auth=operator_auth(),
        json={"question": "Show SoftDent provider ranking for production performance."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert any(item["source_id"] == "softdent-live-provider-ranking" for item in payload["retrieved_context"])
    assert any(item["title"] == "SoftDent live provider ranking" for item in payload["retrieved_context"])
    assert "Verified SoftDent metrics: Top Provider=Dr. Adams ($55,250.00 Production)" in payload["answer"]
    assert not any(item["source_id"] == "softdent-live-summary" for item in payload["retrieved_context"])


def test_hal_question_includes_softdent_payer_mix_context(canonical_softdent_dashboard):
    client.post("/api/hal9000/refresh-index", auth=basic_auth())

    response = client.post(
        "/hal9000",
        auth=operator_auth(),
        json={"question": "Show SoftDent payer mix and insurance share."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert any(item["source_id"] == "softdent-live-payer-mix" for item in payload["retrieved_context"])
    assert any(item["title"] == "SoftDent live payer mix" for item in payload["retrieved_context"])
    assert "Verified SoftDent metrics: Insurance=$65,435.00 (61.15%) | Patient=$41,580.00 (38.85%)" in payload["answer"]
    assert not any(item["source_id"] == "softdent-live-summary" for item in payload["retrieved_context"])


def test_hal_question_includes_softdent_collection_delta_context(canonical_softdent_dashboard):
    client.post("/api/hal9000/refresh-index", auth=basic_auth())

    response = client.post(
        "/hal9000",
        auth=operator_auth(),
        json={"question": "Show SoftDent collections gap and production delta."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert any(item["source_id"] == "softdent-live-collection-delta" for item in payload["retrieved_context"])
    assert any(item["title"] == "SoftDent live collections delta" for item in payload["retrieved_context"])
    assert "Verified SoftDent metrics: Collection Delta=$9,765.00 (91.64% Collection Ratio)" in payload["answer"]
    assert not any(item["source_id"] == "softdent-live-summary" for item in payload["retrieved_context"])


def test_hal_question_includes_hardware_monitor_context(monkeypatch):
    import app.hal.orchestrator as orchestrator

    monkeypatch.setattr(orchestrator, "get_controlled_patient_context", lambda question, **_kwargs: {"matched": False, "snippets": [], "narrative": "", "summary_fields": {}})
    monkeypatch.setattr(orchestrator, "get_live_financial_context", lambda question, **_kwargs: [])
    monkeypatch.setattr(orchestrator, "retrieve_relevant_context", lambda question, **_kwargs: [])
    monkeypatch.setattr(orchestrator, "get_financial_source_status", lambda: {})
    monkeypatch.setattr(orchestrator, "_build_hal_operating_picture", lambda financial_sources: {"summary": "backend-verified operating picture."})
    monkeypatch.setattr(
        orchestrator,
        "get_monitor_status",
        lambda: {
            "source_backend": "ddc_ci",
            "brightness": 42,
            "contrast": 68,
            "input_source": "HDMI-1",
            "raw_vcp_codes": {"input_source_raw": 17, "input_source_raw_type": "int"},
            "health": {"connected": True, "error": None},
        },
    )

    payload = orchestrator.answer_hal_question(
        question="Show the current monitor brightness and display input.",
        actor="admin",
    )

    monitor_item = next(item for item in payload["retrieved_context"] if item["source_id"] == "physical_monitor_primary")
    assert monitor_item["title"] == "Verified Physical Monitor Parameters (DDC/CI)"
    assert monitor_item["category"] == "hardware_status"
    assert "Brightness=42%" in monitor_item["excerpt"]
    assert "Contrast=68%" in monitor_item["excerpt"]
    assert "Raw Code=17" in monitor_item["excerpt"]
    assert "Verified hardware metrics: Brightness=42% | Contrast=68% | Input=HDMI-1" in payload["answer"]


def test_hal_question_returns_reviewed_hardware_action_for_brightness_change(monkeypatch):
    import app.hal.orchestrator as orchestrator

    monkeypatch.setattr(orchestrator, "get_controlled_patient_context", lambda question, **_kwargs: {"matched": False, "snippets": [], "narrative": "", "summary_fields": {}})
    monkeypatch.setattr(orchestrator, "get_live_financial_context", lambda question, **_kwargs: [])
    monkeypatch.setattr(orchestrator, "retrieve_relevant_context", lambda question, **_kwargs: [])
    monkeypatch.setattr(orchestrator, "get_financial_source_status", lambda: {})
    monkeypatch.setattr(orchestrator, "_build_hal_operating_picture", lambda financial_sources: {"summary": "backend-verified operating picture."})
    monkeypatch.setattr(
        orchestrator,
        "get_monitor_status",
        lambda: {
            "source_backend": "ddc_ci",
            "brightness": 42,
            "contrast": 68,
            "input_source": "HDMI-1",
            "health": {"connected": True, "error": None},
        },
    )

    payload = orchestrator.answer_hal_question(
        question="Set the monitor brightness to 30%.",
        actor="admin",
    )

    assert "Requested hardware changes require human confirmation" in payload["answer"]
    assert "hardware mutations require human confirmation" in payload["guardrails"]
    assert payload["review_actions"] == [
        {
            "action_id": "monitor-set-luminance-30",
            "action_type": "SET_LUMINANCE",
            "target_device": "primary_monitor",
            "target_value": 30,
            "human_review_required": True,
            "status": "pending_confirmation",
            "title": "Set monitor brightness to 30%",
            "confirmation_message": "Review before sending a DDC/CI brightness change to 30%.",
        }
    ]


def test_hal_follow_up_uses_last_patient_context(monkeypatch):
    def fake_claim_rows():
        return [
            {
                "PatientName": "John Doe",
                "MRN": "778899",
                "ClaimId": "CLM-1001",
                "ClaimStatus": "Denied",
                "Payer": "Delta Dental",
                "Procedure": "Crown buildup",
                "ServiceDate": "2026-06-01",
                "DenialReason": "Additional narrative requested by payer",
                "ClaimAmount": 915.4,
            }
        ]

    def fake_note_rows():
        return [
            {
                "PatientName": "John Doe",
                "MRN": "778899",
                "NoteDate": "2026-06-01",
                "Procedure": "Crown buildup",
                "ClinicalNote": "Patient has fractured cusp with recurrent decay and documented cold sensitivity.",
            }
        ]

    monkeypatch.setattr(financial_tools, "load_softdent_claim_rows", fake_claim_rows)
    monkeypatch.setattr(financial_tools, "load_softdent_clinical_note_rows", fake_note_rows)

    first_payload = client.post(
        "/hal9000",
        auth=operator_auth(),
        json={"question": "Patient John Doe MRN 778899 needs an insurance narrative for the denied crown buildup claim."},
    ).json()

    second_response = client.post(
        "/hal9000",
        auth=operator_auth(),
        json={"question": "Based on the patient details I just gave you, draft the follow-up plan."},
    )

    assert first_payload["audit_id"].startswith("hal-")
    assert second_response.status_code == 200
    second_payload = second_response.json()
    assert "Verified patient context: Patient=John Doe" in second_payload["answer"]
    assert "resubmission or appeal" in second_payload["answer"]


def test_hal_follow_up_suppresses_operating_picture_and_summarizes_collection_action(monkeypatch, canonical_softdent_dashboard):
    import app.hal.orchestrator as orchestrator

    monkeypatch.setattr(orchestrator, "get_controlled_patient_context", lambda question, **_kwargs: {"matched": False, "snippets": [], "narrative": "", "summary_fields": {}})
    monkeypatch.setattr(orchestrator, "get_live_financial_context", lambda question, **_kwargs: [])
    monkeypatch.setattr(orchestrator, "retrieve_relevant_context", lambda question, **_kwargs: [])

    payload = orchestrator.answer_hal_question(
        question="Do not repeat the operating picture. Based on that collections gap, what should I do first before lunch?",
        actor="admin",
    )

    assert "I am local, steady, and working from the backend-verified operating picture." not in payload["answer"]
    assert "A/R aging" in payload["answer"]
    assert "$9,765.00 collections gap" in payload["answer"]


def test_hal_provider_question_can_identify_weakest_provider(monkeypatch, canonical_softdent_dashboard):
    import app.hal.orchestrator as orchestrator

    monkeypatch.setattr(orchestrator, "get_controlled_patient_context", lambda question, **_kwargs: {"matched": False, "snippets": [], "narrative": "", "summary_fields": {}})
    monkeypatch.setattr(orchestrator, "get_live_financial_context", lambda question, **_kwargs: [])
    monkeypatch.setattr(orchestrator, "retrieve_relevant_context", lambda question, **_kwargs: [])

    payload = orchestrator.answer_hal_question(
        question="Which provider looks weakest from the current SoftDent snapshot, and why?",
        actor="admin",
    )

    assert "Hygiene Team" in payload["answer"]
    assert "weakest provider" in payload["answer"]
    assert "$17,480.00 in collections" in payload["answer"]
    assert "I am local, steady, and working from the backend-verified operating picture." not in payload["answer"]


def test_hal_action_summary_uses_recent_conversation_state(monkeypatch):
    import app.hal.orchestrator as orchestrator

    monkeypatch.setattr(orchestrator, "get_controlled_patient_context", lambda question, **_kwargs: {"matched": False, "snippets": [], "narrative": "", "summary_fields": {}})
    monkeypatch.setattr(orchestrator, "get_live_financial_context", lambda question, **_kwargs: [])
    monkeypatch.setattr(orchestrator, "retrieve_relevant_context", lambda question, **_kwargs: [])

    orchestrator.answer_hal_question(
        question="SoftDent collections are trailing production. What should I look at first?",
        actor="admin",
    )
    orchestrator.answer_hal_question(
        question="Set the monitor brightness to 30%.",
        actor="admin",
    )

    payload = orchestrator.answer_hal_question(
        question="Now summarize the top two action items from everything we just covered without inventing anything new.",
        actor="admin",
    )

    assert "Top two action items:" in payload["answer"]
    assert "collections gap" in payload["answer"]
    assert "Set monitor brightness to 30%" in payload["answer"]


def test_hal_question_includes_softdent_claims_context(monkeypatch):
    def fake_claim_rows():
        return [
            {"ClaimId": "1001", "ClaimStatus": "Denied", "Payer": "Delta Dental", "AgingDays": 42, "ClaimAmount": 215.75, "Note": "Missing attachment"},
            {"ClaimId": "1002", "ClaimStatus": "Open", "Payer": "MetLife", "AgingDays": 18, "ClaimAmount": 180.0, "Note": "Waiting on payer response"},
        ]

    monkeypatch.setattr(financial_tools, "load_softdent_claim_rows", fake_claim_rows)

    response = client.post(
        "/hal9000",
        auth=operator_auth(),
        json={"question": "Show SoftDent claims denied by Delta Dental."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert any(item["source_id"] == "softdent-claims-summary" for item in payload["retrieved_context"])
    claims_item = next(item for item in payload["retrieved_context"] if item["source_id"] == "softdent-claims-summary")
    assert "ClaimStatus=Denied" in claims_item["excerpt"]
    assert "Delta Dental" in claims_item["excerpt"]


def test_hal_question_includes_softdent_clinical_notes_context(monkeypatch):
    def fake_note_rows():
        return [
            {"NoteDate": "2026-06-15", "Provider": "Dr. Adams", "Procedure": "Crown prep", "ClinicalNote": "Patient reports sensitivity on upper right molar."},
            {"NoteDate": "2026-06-14", "Provider": "Dr. Lee", "Procedure": "Recall", "ClinicalNote": "Periodic exam completed with hygiene review."},
        ]

    monkeypatch.setattr(financial_tools, "load_softdent_clinical_note_rows", fake_note_rows)

    response = client.post(
        "/hal9000",
        auth=operator_auth(),
        json={"question": "Show SoftDent clinical notes about crown prep sensitivity."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert any(item["source_id"] == "softdent-clinical-notes-summary" for item in payload["retrieved_context"])
    notes_item = next(item for item in payload["retrieved_context"] if item["source_id"] == "softdent-clinical-notes-summary")
    assert "Procedure=Crown prep" in notes_item["excerpt"]
    assert "ClinicalNote=" in notes_item["excerpt"]
    assert "Patient reports sensitivity on upper right molar." in notes_item["excerpt"]


def test_hal_question_builds_patient_insurance_narrative_from_raw_identifiers(monkeypatch):
    def fake_claim_rows():
        return [
            {
                "PatientName": "John Doe",
                "MRN": "778899",
                "ClaimId": "CLM-1001",
                "ClaimStatus": "Denied",
                "Payer": "Delta Dental",
                "Procedure": "Crown buildup",
                "ServiceDate": "2026-06-01",
                "DenialReason": "Additional narrative requested by payer",
                "ClaimAmount": 915.4,
            }
        ]

    def fake_note_rows():
        return [
            {
                "PatientName": "John Doe",
                "MRN": "778899",
                "NoteDate": "2026-06-01",
                "Procedure": "Crown buildup",
                "ClinicalNote": "Patient has fractured cusp with recurrent decay and documented cold sensitivity.",
            }
        ]

    monkeypatch.setattr(financial_tools, "load_softdent_claim_rows", fake_claim_rows)
    monkeypatch.setattr(financial_tools, "load_softdent_clinical_note_rows", fake_note_rows)

    response = client.post(
        "/hal9000",
        auth=operator_auth(),
        json={"question": "Patient John Doe MRN 778899 needs an insurance narrative for the denied crown buildup claim."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "PATIENT_REDACTED" in payload["sanitized_question"]
    assert "MRN_REDACTED" in payload["sanitized_question"]
    assert "Verified patient context: Patient=John Doe | Claims=1 ($915.40 total) | Primary Status=Denied | Clinical Notes=1." in payload["answer"]
    assert "Insurance narrative for John Doe." in payload["answer"]
    assert "Delta Dental" in payload["answer"]
    assert "Additional narrative requested by payer" in payload["answer"]
    assert "fractured cusp" in payload["answer"]
    assert any(item["source_id"] == "softdent-patient-claims-dossier" for item in payload["retrieved_context"])
    assert any(item["source_id"] == "softdent-patient-clinical-dossier" for item in payload["retrieved_context"])
    assert any(item["source_id"] == "softdent-insurance-narrative-support" for item in payload["retrieved_context"])
    assert "authorized internal office context" in payload["guardrails"]
    assert payload["voice_profile"]["lane"] == "patient_workflow"
    assert any(note["label"] == "Patient context" for note in payload["governance_notes"])


def test_hal_insurance_narrative_endpoint_returns_structured_response(monkeypatch):
    def fake_claim_rows():
        return [
            {
                "PatientName": "John Doe",
                "MRN": "778899",
                "ClaimId": "CLM-1001",
                "ClaimStatus": "Denied",
                "Payer": "Delta Dental",
                "Procedure": "Crown buildup",
                "ServiceDate": "2026-06-01",
                "DenialReason": "Additional narrative requested by payer",
            }
        ]

    def fake_note_rows():
        return [
            {
                "PatientName": "John Doe",
                "MRN": "778899",
                "NoteDate": "2026-06-01",
                "Procedure": "Crown buildup",
                "ClinicalNote": "Patient has fractured cusp with recurrent decay and documented cold sensitivity.",
            }
        ]

    monkeypatch.setattr(financial_tools, "load_softdent_claim_rows", fake_claim_rows)
    monkeypatch.setattr(financial_tools, "load_softdent_clinical_note_rows", fake_note_rows)

    response = client.post(
        "/api/hal9000/insurance-narrative",
        auth=operator_auth(),
        json={"question": "Patient John Doe MRN 778899 needs an insurance narrative for the denied crown buildup claim."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["matched"] is True
    assert payload["mode"] == "local-rag-phase-1"
    assert "Verified patient context: Patient=John Doe | Claims=1 ($0.00 total) | Primary Status=Denied | Clinical Notes=1." in payload["narrative"]
    assert "Insurance narrative for John Doe." in payload["narrative"]
    assert "PATIENT_REDACTED" in payload["sanitized_question"]
    assert "MRN_REDACTED" in payload["sanitized_question"]
    assert any(item["source_id"] == "softdent-patient-claims-dossier" for item in payload["supporting_context"])
    assert any(item["source_id"] == "softdent-patient-clinical-dossier" for item in payload["supporting_context"])
    assert "patient-specific local tool only" in payload["guardrails"]
    assert payload["voice_profile"]["lane"] == "patient_workflow"


def test_hal_insurance_narrative_endpoint_reports_no_match(monkeypatch):
    monkeypatch.setattr(financial_tools, "load_softdent_claim_rows", lambda: [])
    monkeypatch.setattr(financial_tools, "load_softdent_clinical_note_rows", lambda: [])

    response = client.post(
        "/api/hal9000/insurance-narrative",
        auth=operator_auth(),
        json={"question": "Patient Jane Smith needs an insurance narrative for claim 12345."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["matched"] is False
    assert payload["supporting_context"] == []
    assert "No patient-specific SoftDent claims or clinical-note rows matched" in payload["narrative"]


def test_hal_patient_dossier_endpoint_returns_structured_lookup(monkeypatch):
    def fake_claim_rows():
        return [{"PatientName": "John Doe", "MRN": "778899", "ClaimId": "CLM-1001", "ClaimStatus": "Denied", "Payer": "Delta Dental"}]

    def fake_note_rows():
        return [{"PatientName": "John Doe", "MRN": "778899", "Procedure": "Crown buildup", "ClinicalNote": "Patient has fractured cusp."}]

    monkeypatch.setattr(financial_tools, "load_softdent_claim_rows", fake_claim_rows)
    monkeypatch.setattr(financial_tools, "load_softdent_clinical_note_rows", fake_note_rows)

    response = client.post(
        "/api/hal9000/patient-dossier",
        auth=operator_auth(),
        json={"question": "Patient John Doe MRN 778899 claim lookup."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["matched"] is True
    assert "Patient-specific SoftDent claim and/or clinical-note context matched" in payload["summary"]
    assert "Verified patient context: Patient=John Doe | Claims=1 ($0.00 total) | Primary Status=Denied | Clinical Notes=1." in payload["summary"]
    assert any(item["source_id"] == "softdent-patient-claims-dossier" for item in payload["supporting_context"])
    assert any(item["source_id"] == "softdent-patient-clinical-dossier" for item in payload["supporting_context"])
    assert payload["voice_profile"]["lane"] == "patient_workflow"


def test_hal_patient_dossier_endpoint_reports_no_match(monkeypatch):
    monkeypatch.setattr(financial_tools, "load_softdent_claim_rows", lambda: [])
    monkeypatch.setattr(financial_tools, "load_softdent_clinical_note_rows", lambda: [])

    response = client.post(
        "/api/hal9000/patient-dossier",
        auth=operator_auth(),
        json={"question": "Patient Jane Smith claim lookup."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["matched"] is False
    assert payload["supporting_context"] == []


def test_hal_question_reports_sdk_unavailable_without_odbc_fallback(monkeypatch):
    clear_user_registry_cache()

    def fake_fetch_quickbooks_sdk_summary(topic: str):
        raise RuntimeError("sdk not approved in test")

    def fake_fetch_quickbooks_data(sql_query: str, dsn: str | None = None):
        raise AssertionError("should not reach ODBC fallback when SDK is unavailable")

    monkeypatch.setattr(financial_tools, "fetch_quickbooks_sdk_summary", fake_fetch_quickbooks_sdk_summary)
    monkeypatch.setattr(financial_tools, "fetch_quickbooks_data", fake_fetch_quickbooks_data, raising=False)

    response = client.post(
        "/hal9000",
        auth=operator_auth(),
        json={"question": "Show QuickBooks revenue summary for the current period."},
    )

    assert response.status_code == 200
    payload = response.json()
    quickbooks_items = [item for item in payload["retrieved_context"] if item["source_id"] == "quickbooks-revenue-sdk-blocked"]
    assert quickbooks_items
    assert "sdk not approved in test" in quickbooks_items[0]["excerpt"]


def test_hal_question_reports_sdk_blocked_before_odbc(monkeypatch):
    def fake_fetch_quickbooks_sdk_summary(topic: str):
        raise RuntimeError("QuickBooks SDK request timed out or is blocked by the QuickBooks UI")

    def fake_fetch_quickbooks_data(sql_query: str, dsn: str | None = None):
        raise RuntimeError("should not reach ODBC when sdk is blocked")

    monkeypatch.setattr(financial_tools, "fetch_quickbooks_sdk_summary", fake_fetch_quickbooks_sdk_summary)
    monkeypatch.setattr(financial_tools, "fetch_quickbooks_data", fake_fetch_quickbooks_data, raising=False)

    response = client.post(
        "/hal9000",
        auth=operator_auth(),
        json={"question": "Show QuickBooks revenue summary for the current period."},
    )

    assert response.status_code == 200
    payload = response.json()
    quickbooks_items = [item for item in payload["retrieved_context"] if item["source_id"] == "quickbooks-revenue-sdk-blocked"]
    assert quickbooks_items
    assert "blocked by the QuickBooks UI" in quickbooks_items[0]["excerpt"]


def test_hal_question_prefers_quickbooks_sdk_summary(monkeypatch):
    def fake_fetch_quickbooks_sdk_summary(topic: str):
        assert topic == "revenue"
        return [{"ReportTitle": "Profit & Loss", "ReportPeriod": "June 1 - 15, 2026", "TotalIncome": "2500.00"}]

    monkeypatch.setattr(financial_tools, "fetch_quickbooks_sdk_summary", fake_fetch_quickbooks_sdk_summary)

    response = client.post(
        "/hal9000",
        auth=operator_auth(),
        json={"question": "Show QuickBooks revenue summary for the current period."},
    )

    assert response.status_code == 200
    payload = response.json()
    quickbooks_items = [item for item in payload["retrieved_context"] if item["source_id"].startswith("quickbooks-revenue")]
    assert quickbooks_items
    assert "sdk read-only query" in quickbooks_items[0]["excerpt"]
    assert "TotalIncome=2500.00" in quickbooks_items[0]["excerpt"]


def test_run_quickbooks_summary_tool_does_not_fall_back_to_odbc_when_sdk_is_unavailable(monkeypatch):
    monkeypatch.setattr(
        financial_tools,
        "fetch_quickbooks_sdk_summary",
        lambda topic: (_ for _ in ()).throw(RuntimeError("sdk not approved in test")),
    )
    monkeypatch.setattr(
        financial_tools,
        "fetch_quickbooks_data",
        lambda query: (_ for _ in ()).throw(AssertionError("should not reach ODBC fallback when SDK is unavailable")),
        raising=False,
    )

    payload = financial_tools.run_quickbooks_summary_tool("revenue")

    assert payload["source_id"] == "quickbooks-revenue-sdk-blocked"
    assert "sdk not approved in test" in payload["excerpt"]


def test_run_quickbooks_summary_tool_reports_sdk_blocked_before_odbc(monkeypatch):
    monkeypatch.setattr(
        financial_tools,
        "fetch_quickbooks_sdk_summary",
        lambda topic: (_ for _ in ()).throw(RuntimeError("QuickBooks SDK request timed out or is blocked by the QuickBooks UI")),
    )
    monkeypatch.setattr(
        financial_tools,
        "fetch_quickbooks_data",
        lambda query: (_ for _ in ()).throw(AssertionError("should not reach ODBC when sdk is blocked")),
        raising=False,
    )

    payload = financial_tools.run_quickbooks_summary_tool("revenue")

    assert payload["source_id"] == "quickbooks-revenue-sdk-blocked"
    assert "blocked by the QuickBooks UI" in payload["excerpt"]


def test_hal_status_includes_live_quickbooks_revenue(monkeypatch):
    def fake_live_status(topic: str):
        return {
            "topic": topic,
            "available": True,
            "health": "ok",
            "source_backend": "sdk",
            "source_id": f"quickbooks-{topic}-summary",
            "excerpt": f"QuickBooks approved {topic} summary from sdk read-only query: TotalIncome=60040.78" if topic == "revenue" else f"QuickBooks {topic} unavailable",
            "checked_at_utc": "2026-06-15T12:00:00+00:00",
            "confidence_label": "high confidence",
            "review_required": False,
            "review_flags": [],
        }

    # The /status endpoint builds live_* topics from the lightweight,
    # export-metadata variant (get_quickbooks_live_status_light), not the SDK
    # probe. Patch the function the endpoint actually consumes.
    monkeypatch.setattr(financial_tools, "get_quickbooks_live_status_light", fake_live_status)

    response = client.get("/api/hal9000/status", auth=operator_auth())

    assert response.status_code == 200
    live_revenue = response.json()["financial_sources"]["quickbooks"]["live_revenue"]
    assert live_revenue["available"] is True
    assert live_revenue["source_id"] == "quickbooks-revenue-summary"
    assert "TotalIncome=60040.78" in live_revenue["excerpt"]
    assert live_revenue["health"] == "ok"
    assert live_revenue["source_backend"] == "sdk"
    assert live_revenue["checked_at_utc"] == "2026-06-15T12:00:00+00:00"
    assert live_revenue["confidence_label"] == "high confidence"
    assert live_revenue["review_required"] is False
    assert live_revenue["review_flags"] == []


def test_get_quickbooks_live_status_marks_env_source_for_review(monkeypatch):
    def fake_run_quickbooks_summary_tool(topic: str):
        assert topic == "revenue"
        return {
            "source_id": "quickbooks-revenue-summary",
            "excerpt": "QuickBooks approved revenue summary from env read-only query: TotalIncome=18250.25",
        }

    monkeypatch.setattr(financial_tools, "run_quickbooks_summary_tool", fake_run_quickbooks_summary_tool)

    payload = financial_tools.get_quickbooks_live_status("revenue")

    assert payload["available"] is True
    assert payload["source_backend"] == "env"
    assert payload["confidence_label"] == "review suggested"
    assert payload["review_required"] is True
    assert "using non-sdk read-only source" in payload["review_flags"]


def test_get_softdent_claims_status_includes_review_metadata(monkeypatch):
    def fake_claim_rows():
        return [{"ClaimId": "CLM-1001", "ClaimStatus": "Denied", "Payer": "Delta Dental", "AgingDays": 42}]

    def fake_claim_source_status():
        return {
            "available": True,
            "source_backend": "csv",
            "source_file": "softdent_claims_export.csv",
            "modified_at_utc": "2026-06-15T11:47:00+00:00",
        }

    monkeypatch.setattr(financial_tools, "load_softdent_claim_rows", fake_claim_rows)
    monkeypatch.setattr(financial_tools, "get_softdent_claim_source_status", fake_claim_source_status)

    payload = financial_tools.get_softdent_claims_status()

    assert payload["available"] is True
    assert payload["confidence_label"] == "high confidence"
    assert payload["review_required"] is False
    assert payload["review_flags"] == []


def test_build_financial_snapshot_documents_handles_sparse_softdent_snapshot(monkeypatch):
    monkeypatch.setattr(financial_tools, "build_softdent_snapshot", lambda: {"available": True})

    documents = financial_tools.build_financial_snapshot_documents()

    financial_snapshot = next(item for item in documents if item["source_id"] == "softdent-financial-snapshot")
    payer_mix = next(item for item in documents if item["source_id"] == "softdent-payer-mix")

    assert "Total production 0.0." in financial_snapshot["sanitized_content"]
    assert "Total collections 0.0." in financial_snapshot["sanitized_content"]
    assert "Insurance collections share 0.0." in payer_mix["sanitized_content"]
    assert not any(item["source_id"] == "softdent-provider-ranking" for item in documents)


def test_get_softdent_live_status_handles_sparse_snapshot_and_source_status(monkeypatch):
    monkeypatch.setattr(financial_tools, "build_softdent_snapshot", lambda: {})
    monkeypatch.setattr(financial_tools, "get_softdent_source_status", lambda: {})

    payload = financial_tools.get_softdent_live_status()

    assert payload["available"] is False
    assert payload["health"] == "degraded"
    assert payload["source_backend"] == "missing"
    assert payload["source_file"] == ""
    assert payload["modified_at_utc"] == ""
    assert "not available" in payload["excerpt"]


def test_get_financial_source_status_handles_sparse_softdent_snapshot(monkeypatch):
    monkeypatch.setattr(financial_tools, "build_softdent_snapshot", lambda: {})
    monkeypatch.setattr(financial_tools, "get_softdent_data_coverage", lambda: {})
    monkeypatch.setattr(financial_tools, "get_softdent_live_status", lambda: {})
    monkeypatch.setattr(financial_tools, "get_softdent_provider_ranking_status", lambda: {})
    monkeypatch.setattr(financial_tools, "get_softdent_payer_mix_status", lambda: {})
    monkeypatch.setattr(financial_tools, "get_softdent_collection_delta_status", lambda: {})
    monkeypatch.setattr(financial_tools, "get_softdent_claims_status", lambda: {})
    monkeypatch.setattr(financial_tools, "get_softdent_clinical_notes_status", lambda: {})
    monkeypatch.setattr(financial_tools, "get_quickbooks_sdk_status", lambda: {})
    monkeypatch.setattr(financial_tools, "get_quickbooks_topic_status", lambda: {})
    monkeypatch.setattr(financial_tools, "get_quickbooks_live_status", lambda topic: {})

    payload = financial_tools.get_financial_source_status()

    assert payload["softdent"]["available"] is False
    assert payload["softdent"]["period"] == ""
    assert payload["softdent"]["provider_count"] == 0


def test_run_softdent_claims_tool_handles_sparse_source_status(monkeypatch):
    monkeypatch.setattr(financial_tools, "load_softdent_claim_rows", lambda: [])
    monkeypatch.setattr(financial_tools, "get_softdent_claim_source_status", lambda: {})

    payload = financial_tools.run_softdent_claims_tool("Show denied claims.")

    assert payload["source_id"] == "softdent-claims-unavailable"
    assert payload["excerpt"] == "SoftDent claims export is not available in the approved local import set."


def test_build_quickbooks_profit_loss_queries_validates_period():
    period = financial_tools.ReportPeriod(start_date="2026-06-30", end_date="2026-06-01")

    try:
        financial_tools.build_quickbooks_profit_loss_queries(period)
    except ValueError as exc:
        assert "end_date" in str(exc)
    else:
        raise AssertionError("Expected invalid report period to raise ValueError")


def test_get_profit_loss_report_returns_empty_when_sdk_is_unavailable(monkeypatch):
    period = financial_tools.ReportPeriod(start_date="2026-06-01", end_date="2026-06-30")

    def fake_fetch_quickbooks_sdk_summary(topic: str, period_dict: dict[str, str] | None = None):
        raise RuntimeError(f"sdk unavailable for {topic}")

    monkeypatch.setattr(financial_tools, "fetch_quickbooks_sdk_summary", fake_fetch_quickbooks_sdk_summary)
    monkeypatch.setattr(
        financial_tools,
        "fetch_quickbooks_data",
        lambda sql_query, dsn=None: (_ for _ in ()).throw(AssertionError("profit-and-loss report must stay on the SDK-only lane")),
        raising=False,
    )

    payload = financial_tools.get_profit_loss_report(period)

    assert payload["source_backend"] == "empty"
    assert payload["period"] == {"start_date": "2026-06-01", "end_date": "2026-06-30"}
    assert payload["summary_fields"] == {}
    assert payload["rows"] == []
    assert payload["health"]["data_complete"] is False
    assert payload["health"]["period_bound"] is False
    assert "No verified SDK profit-and-loss rows were returned" in payload["health"]["warning"]
    assert "sdk unavailable for revenue" in str(payload["health"]["error"])
    assert "sdk unavailable for expenses" in str(payload["health"]["error"])


def test_get_profit_loss_report_uses_period_bounded_sdk_rows(monkeypatch):
    period = financial_tools.ReportPeriod(start_date="2026-06-01", end_date="2026-06-30")
    captured_calls: list[tuple[str, dict[str, str] | None]] = []

    def fake_fetch_quickbooks_sdk_summary(topic: str, period_dict: dict[str, str] | None = None):
        captured_calls.append((topic, period_dict))
        if topic == "revenue":
            return [{"ReportTitle": "Profit & Loss", "ReportPeriod": "2026-06", "TotalIncome": "18250.25"}]
        if topic == "expenses":
            return [{"ReportTitle": "Profit & Loss", "ReportPeriod": "2026-06", "TotalExpense": "7450.10"}]
        return []

    def fake_fetch_quickbooks_data(sql_query: str, dsn: str | None = None):
        raise AssertionError("QODBC fallback should not run when SDK rows are returned for both profit-and-loss topics")

    monkeypatch.setattr(financial_tools, "fetch_quickbooks_sdk_summary", fake_fetch_quickbooks_sdk_summary)
    monkeypatch.setattr(financial_tools, "fetch_quickbooks_data", fake_fetch_quickbooks_data, raising=False)

    payload = financial_tools.get_profit_loss_report(period)

    assert captured_calls == [
        ("revenue", {"start_date": "2026-06-01", "end_date": "2026-06-30"}),
        ("expenses", {"start_date": "2026-06-01", "end_date": "2026-06-30"}),
    ]
    assert payload["source_backend"] == "sdk"
    assert payload["health"]["period_bound"] is True
    assert payload["summary_fields"]["total_revenue"] == 18250.25
    assert payload["summary_fields"]["total_expense"] == 7450.10
    assert payload["summary_fields"]["net_income"] == 10800.15


def test_get_balance_sheet_report_requires_configured_query(monkeypatch):
    monkeypatch.delenv("HAL_QB_BALANCE_SHEET_SQL", raising=False)

    payload = financial_tools.get_balance_sheet_report(
        financial_tools.ReportPeriod(start_date="2026-06-01", end_date="2026-06-30")
    )

    assert payload["source_backend"] == "empty"
    assert payload["rows"] == []
    assert payload["health"]["data_complete"] is False
    assert payload["health"]["error"] == "No approved balance sheet query is configured."


def test_get_ar_aging_report_normalizes_sdk_rows(monkeypatch):
    period = financial_tools.ReportPeriod(start_date="2026-06-01", end_date="2026-06-30")

    def fake_fetch_quickbooks_sdk_summary(topic: str, period_dict: dict[str, str] | None = None):
        assert topic == "ar"
        assert period_dict == {"start_date": "2026-06-01", "end_date": "2026-06-30"}
        return [{"CustomerRef": "Acme Dental", "OutstandingAR": "150.25", "ReportDate": "As of June 16, 2026", "RefNumber": ""}]

    monkeypatch.setattr(financial_tools, "fetch_quickbooks_sdk_summary", fake_fetch_quickbooks_sdk_summary)

    payload = financial_tools.get_ar_aging_report(period)

    assert payload["source_backend"] == "sdk"
    assert payload["summary_fields"]["total_outstanding_ar"] == 150.25
    assert payload["rows"] == [
        {
            "CustomerRef": "Acme Dental",
            "OutstandingAR": 150.25,
            "ReportDate": "As of June 16, 2026",
            "RefNumber": "",
        }
    ]
    assert payload["health"]["period_bound"] is True


def test_hal_status_reports_sdk_only_quickbooks_topics_when_sdk_is_unavailable():
    os.environ["HAL_QB_REVENUE_SQL"] = "SELECT TotalIncome FROM ProfitAndLossSummary"

    original_status = financial_tools.get_quickbooks_sdk_status

    def fake_sdk_status():
        payload = original_status()
        payload["com_available"] = False
        payload["company_file_exists"] = False
        return payload

    def fake_live_status(topic: str):
        return {
            "topic": topic,
            "available": False,
            "health": "warning",
            "source_backend": "unavailable",
            "source_id": f"quickbooks-{topic}-unavailable",
            "excerpt": f"QuickBooks {topic} unavailable",
            "checked_at_utc": "2026-06-15T12:00:00+00:00",
        }

    from unittest.mock import patch

    with patch.object(financial_tools, "get_quickbooks_sdk_status", fake_sdk_status), patch.object(financial_tools, "get_quickbooks_live_status", fake_live_status):
        response = client.get("/api/hal9000/status", auth=operator_auth())

    assert response.status_code == 200
    topics = response.json()["financial_sources"]["quickbooks"]["topics"]
    revenue_topic = next(item for item in topics if item["topic"] == "revenue")
    assert revenue_topic["configured"] is False
    assert revenue_topic["query_source"] == "sdk-only"


def test_get_quickbooks_topic_status_handles_sparse_sdk_status(monkeypatch):
    monkeypatch.setattr(financial_tools, "get_quickbooks_sdk_status", lambda: {})

    payload = financial_tools.get_quickbooks_topic_status()

    revenue_topic = next(item for item in payload if item["topic"] == "revenue")
    assert revenue_topic["query_source"] == "sdk-only"
    assert revenue_topic["sdk_available"] is False
    assert revenue_topic["sdk_company_file"] == ""


def test_admin_can_review_hal_audits():
    client.post("/api/hal9000/refresh-index", auth=basic_auth())
    ask_response = client.post(
        "/hal9000",
        auth=operator_auth(),
        json={"question": "Show the current KPI summary and claims context."},
    )

    assert ask_response.status_code == 200

    audit_response = client.get("/api/hal9000/audits?limit=5", auth=basic_auth())

    assert audit_response.status_code == 200
    payload = audit_response.json()
    assert payload["count"] >= 1
    assert payload["items"][0]["audit_id"].startswith("hal-")


def test_non_admin_cannot_review_hal_audits():
    audit_response = client.get("/api/hal9000/audits?limit=5", auth=operator_auth())

    assert audit_response.status_code == 403


def test_hal_patient_ar_missing_reports_unavailable_not_zero(monkeypatch):
    monkeypatch.setattr(hal_orchestrator, "load_softdent_ar_rows", lambda: [])
    monkeypatch.setattr(
        hal_orchestrator,
        "get_controlled_patient_context",
        lambda question, **_kwargs: {
            "matched": True,
            "snippets": [],
            "narrative": "Matched patient export context.",
            "summary_fields": {"patient_name": "John Doe", "claim_count": 1, "primary_claim_status": "Pending"},
        },
    )
    monkeypatch.setattr(hal_orchestrator, "retrieve_relevant_context", lambda question, **_kwargs: [])
    monkeypatch.setattr(hal_orchestrator, "get_live_financial_context", lambda question, **_kwargs: [])
    monkeypatch.setattr(hal_orchestrator, "compile_hardware_snippets", lambda question, **_kwargs: [])
    monkeypatch.setattr(hal_orchestrator, "compile_softdent_aggregate_snippets", lambda question, **_kwargs: [])
    monkeypatch.setattr(hal_orchestrator, "compile_live_report_snippets", lambda question, **_kwargs: [])

    payload = hal_orchestrator.answer_hal_question(
        question="What is patient John Doe outstanding A/R balance?",
        actor="hal_operator",
    )

    assert "unavailable" in payload["answer"].lower()
    assert "missing_softdent_ar" in payload["answer"]
    assert "$0.00" not in payload["answer"]
    assert "not be reported as $0" in payload["answer"]
    assert "John Doe" in payload["answer"]


def test_hal_memory_proposal_suggested_not_written(monkeypatch):
    memories_path = Path(__file__).resolve().parents[2] / "docs" / "hal_knowledge" / "memories.jsonl"
    before_lines = [line for line in memories_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    monkeypatch.setattr(hal_orchestrator, "retrieve_relevant_context", lambda question, **_kwargs: [])
    monkeypatch.setattr(hal_orchestrator, "get_live_financial_context", lambda question, **_kwargs: [])
    monkeypatch.setattr(hal_orchestrator, "compile_hardware_snippets", lambda question, **_kwargs: [])
    monkeypatch.setattr(hal_orchestrator, "compile_softdent_aggregate_snippets", lambda question, **_kwargs: [])
    monkeypatch.setattr(hal_orchestrator, "compile_live_report_snippets", lambda question, **_kwargs: [])
    monkeypatch.setattr(
        hal_orchestrator,
        "get_controlled_patient_context",
        lambda question, **_kwargs: {"matched": False, "snippets": [], "narrative": ""},
    )

    payload = hal_orchestrator.answer_hal_question(
        question="Remember this stable workflow: always check payer mix before lunch.",
        actor="hal_operator",
    )

    after_lines = [line for line in memories_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert hal_orchestrator.GOVERNED_MEMORY_PROPOSAL_PHRASE in payload["answer"]
    assert len(after_lines) == len(before_lines)


def test_hal_patient_answer_omits_raw_csv_mrn_and_secrets(monkeypatch):
    monkeypatch.setattr(
        financial_tools,
        "load_softdent_claim_rows",
        lambda: [
            {
                "PatientName": "John Doe",
                "MRN": "778899",
                "ClaimId": "CLM-1001",
                "ClaimStatus": "Denied",
                "Payer": "Delta Dental",
            }
        ],
    )
    monkeypatch.setattr(financial_tools, "load_softdent_clinical_note_rows", lambda: [])

    response = client.post(
        "/hal9000",
        auth=operator_auth(),
        json={"question": "Patient John Doe MRN 778899 claim status review."},
    )

    assert response.status_code == 200
    payload = response.json()
    answer = payload["answer"]
    assert "John Doe" in answer
    assert "778899" not in answer
    assert "PatientName,MRN,ClaimId" not in answer
    assert "password" not in answer.lower()
    assert "api_key" not in answer.lower()


def test_hal_claim_review_does_not_claim_external_submission(monkeypatch):
    monkeypatch.setattr(
        financial_tools,
        "load_softdent_claim_rows",
        lambda: [
            {
                "PatientName": "John Doe",
                "ClaimId": "CLM-1001",
                "ClaimStatus": "Denied",
                "Payer": "Delta Dental",
                "Procedure": "Crown buildup",
            }
        ],
    )
    monkeypatch.setattr(financial_tools, "load_softdent_clinical_note_rows", lambda: [])

    response = client.post(
        "/hal9000",
        auth=operator_auth(),
        json={"question": "Patient John Doe denied crown claim—should we resubmit today?"},
    )

    assert response.status_code == 200
    payload = response.json()
    lowered = payload["answer"].lower()
    assert "has been submitted" not in lowered
    assert "was submitted" not in lowered
    assert "i submitted" not in lowered
    assert "fax" not in lowered or "cannot" in lowered or "review" in lowered