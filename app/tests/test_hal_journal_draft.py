import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.auth import clear_user_registry_cache
from app.hal.accounting_validation import build_journal_validation
import app.hal.orchestrator as orchestrator_module
from app.hal.posting_queue import DRAFT_STATUS_DRAFT_ONLY, DRAFT_STATUS_ENQUEUED, ENQUEUE_MODE_AUTO_VALIDATED_AI, POSTING_QUEUE_STATUS_PENDING_REVIEW
from app.main import app


TEST_AUTH_USERS_JSON = json.dumps(
    [
        {
            "username": "hal_operator",
            "display_name": "HAL Operator",
            "password": "hal-password",
            "roles": ["dashboard:read", "hal:operator"],
        }
    ]
)

os.environ["APP_AUTH_USERS_JSON"] = TEST_AUTH_USERS_JSON

client = TestClient(app)


def setup_function():
    os.environ["APP_AUTH_USERS_JSON"] = TEST_AUTH_USERS_JSON
    os.environ.pop("HAL_ALLOWED_BASE_PATH", None)
    os.environ.pop("HAL_AI_WORKSPACE_PATH", None)
    os.environ.pop("HAL_CHROMA_PATH", None)
    os.environ.pop("HAL_SQLITE_PATH", None)
    clear_user_registry_cache()


def operator_auth():
    return ("hal_operator", "hal-password")


def test_journal_draft_returns_balanced_lines(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HAL_ALLOWED_BASE_PATH", str(tmp_path))
    workspace_root = tmp_path / "AI_Workspace"
    monkeypatch.setenv("HAL_AI_WORKSPACE_PATH", str(workspace_root))
    response = client.post(
        "/api/hal9000/accounting/journal-draft",
        auth=operator_auth(),
        json={
            "description": "Record prepaid insurance for June coverage.",
            "transaction_date": "2026-06-15",
            "accounting_period": "2026-06",
            "amount": 1200.0,
            "context": {},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "local-rag-phase-1"
    assert payload["review_required"] is True
    assert payload["validation"]["balanced"] is True
    assert payload["validation"]["debit_total"] == 1200.0
    assert payload["validation"]["credit_total"] == 1200.0
    assert payload["validation"]["open_period"] is True
    assert payload["lines"][0]["account_code"] == "1310"
    assert payload["lines"][1]["account_code"] == "1010"
    assert payload["audit_id"].startswith("hal-")
    assert payload["review_plan_path"] is None
    assert payload["access_policy"]["workspace_root"] == ""
    assert payload["access_policy"]["activity_log_path"] == ""
    assert payload["access_policy"]["review_plan_directory"] == ""
    review_plan = next((workspace_root / "review_plans").glob("*.json"), None)
    assert review_plan is not None and review_plan.exists()
    assert (workspace_root / "ai_activity.log").read_text(encoding="utf-8")


def test_journal_draft_flags_closed_period():
    response = client.post(
        "/api/hal9000/accounting/journal-draft",
        auth=operator_auth(),
        json={
            "description": "Record prepaid insurance for prior year coverage.",
            "transaction_date": "2024-12-15",
            "accounting_period": "2024-12",
            "amount": 500.0,
            "context": {},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["validation"]["open_period"] is False
    assert "Accounting period is closed." in payload["validation"]["issues"]


def test_journal_draft_rejects_invalid_transaction_date():
    response = client.post(
        "/api/hal9000/accounting/journal-draft",
        auth=operator_auth(),
        json={
            "description": "Record prepaid insurance for June coverage.",
            "transaction_date": "2026-99-99",
            "accounting_period": "2026-06",
            "amount": 1200.0,
            "context": {},
        },
    )

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any(error.get("loc") == ["body", "transaction_date"] for error in errors)


def test_journal_draft_uses_explicit_transaction_type_context():
    response = client.post(
        "/api/hal9000/accounting/journal-draft",
        auth=operator_auth(),
        json={
            "description": "Apply June patient payment batch.",
            "transaction_date": "2026-06-15",
            "accounting_period": "2026-06",
            "amount": 350.0,
            "context": {"transaction_type": "patient_cash_receipt"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["validation"]["balanced"] is True
    assert payload["lines"][0]["account_code"] == "1010"
    assert payload["lines"][1]["account_code"] == "1100"


def test_journal_draft_infers_payroll_accrual_from_description():
    response = client.post(
        "/api/hal9000/accounting/journal-draft",
        auth=operator_auth(),
        json={
            "description": "Record payroll accrual for the final June pay period.",
            "transaction_date": "2026-06-30",
            "accounting_period": "2026-06",
            "amount": 4200.0,
            "context": {},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["validation"]["balanced"] is True
    assert payload["lines"][0]["account_code"] == "6200"
    assert payload["lines"][1]["account_code"] == "2200"


def test_journal_draft_can_use_local_ai_workflow_when_enabled(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("HAL_ALLOWED_BASE_PATH", str(tmp_path))
    monkeypatch.setenv("HAL_AI_WORKSPACE_PATH", str(tmp_path / "AI_Workspace"))
    monkeypatch.setattr("app.hal.orchestrator.check_ollama_available", lambda base_url, timeout_seconds=5: (True, None))
    monkeypatch.setattr(
        "app.hal.orchestrator.load_json_file",
        lambda path: {"profiles": {"coder": {"model": "qwen", "seed": 23}, "chat": {"model": "mistral", "seed": 17}}},
    )

    def fake_workflow(**kwargs):
        return {
            "parsed_payload": {
                "transaction_type": "vendor_bill",
                "lines": [
                    {"account_code": "5200", "account_name": "Dental Supplies Expense", "debit": 700.0, "credit": 0.0, "memo": "AI draft"},
                    {"account_code": "2100", "account_name": "Accounts Payable", "debit": 0.0, "credit": 700.0, "memo": "AI draft"},
                ],
            },
            "summary_text": "AI drafted a balanced vendor bill journal entry for review.",
        }

    monkeypatch.setattr("app.hal.orchestrator.run_structured_output_workflow", fake_workflow)

    response = client.post(
        "/api/hal9000/accounting/journal-draft",
        auth=operator_auth(),
        json={
            "description": "Queue vendor bill for review.",
            "transaction_date": "2026-06-15",
            "accounting_period": "2026-06",
            "amount": 700.0,
            "context": {"use_local_ai_workflow": True, "source_text": "Vendor invoice for dental supplies, $700 due next month."},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"] == "AI drafted a balanced vendor bill journal entry for review."
    assert payload["validation"]["balanced"] is True
    assert payload["lines"][0]["account_code"] == "5200"
    assert payload["lines"][1]["account_code"] == "2100"
    assert payload["review_plan_path"] is None
    review_plan = next((tmp_path / "AI_Workspace" / "review_plans").glob("*.json"), None)
    assert review_plan is not None
    assert review_plan.exists()
    review_plan_payload = json.loads(review_plan.read_text(encoding="utf-8"))
    assert review_plan_payload["status"] == "pending_human_approval"


def test_journal_draft_falls_back_when_local_ai_workflow_is_unavailable(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.hal.orchestrator.check_ollama_available", lambda base_url, timeout_seconds=5: (False, "offline"))

    response = client.post(
        "/api/hal9000/accounting/journal-draft",
        auth=operator_auth(),
        json={
            "description": "Record prepaid insurance for June coverage.",
            "transaction_date": "2026-06-15",
            "accounting_period": "2026-06",
            "amount": 1200.0,
            "context": {"use_local_ai_workflow": True},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["validation"]["balanced"] is True
    assert payload["lines"][0]["account_code"] == "1310"
    assert payload["lines"][1]["account_code"] == "1010"


def test_journal_draft_can_auto_enqueue_validated_ai_draft(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.hal.orchestrator.check_ollama_available", lambda base_url, timeout_seconds=5: (True, None))
    monkeypatch.setattr(
        "app.hal.orchestrator.load_json_file",
        lambda path: {"profiles": {"coder": {"model": "qwen", "seed": 23}, "chat": {"model": "mistral", "seed": 17}}},
    )

    def fake_workflow(**kwargs):
        return {
            "parsed_payload": {
                "transaction_type": "vendor_bill",
                "lines": [
                    {"account_code": "5200", "account_name": "Dental Supplies Expense", "debit": 700.0, "credit": 0.0, "memo": "AI draft"},
                    {"account_code": "2100", "account_name": "Accounts Payable", "debit": 0.0, "credit": 700.0, "memo": "AI draft"},
                ],
            },
            "summary_text": "AI drafted a balanced vendor bill journal entry for review.",
        }

    monkeypatch.setattr("app.hal.orchestrator.run_structured_output_workflow", fake_workflow)

    response = client.post(
        "/api/hal9000/accounting/journal-draft",
        auth=operator_auth(),
        json={
            "description": "Queue vendor bill for review.",
            "transaction_date": "2026-06-15",
            "accounting_period": "2026-06",
            "amount": 700.0,
            "context": {
                "use_local_ai_workflow": True,
                "auto_enqueue_validated_draft": True,
                "source_text": "Vendor invoice for dental supplies, $700 due next month.",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["draft_status"] == DRAFT_STATUS_ENQUEUED
    assert payload["queue_id"].startswith("qbd-queue-")
    assert payload["queue_status"] == POSTING_QUEUE_STATUS_PENDING_REVIEW
    assert payload["enqueue_error"] is None

    listing = client.get("/api/hal9000/accounting/posting-queue?limit=20", auth=operator_auth())
    assert listing.status_code == 200
    queued_item = next(item for item in listing.json()["items"] if item["queue_id"] == payload["queue_id"])
    assert queued_item["enqueue_mode"] == ENQUEUE_MODE_AUTO_VALIDATED_AI


def test_journal_draft_returns_draft_when_auto_enqueue_fails(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.hal.orchestrator.check_ollama_available", lambda base_url, timeout_seconds=5: (True, None))
    monkeypatch.setattr(
        "app.hal.orchestrator.load_json_file",
        lambda path: {"profiles": {"coder": {"model": "qwen", "seed": 23}, "chat": {"model": "mistral", "seed": 17}}},
    )

    def fake_workflow(**kwargs):
        return {
            "parsed_payload": {
                "transaction_type": "vendor_bill",
                "lines": [
                    {"account_code": "5200", "account_name": "Dental Supplies Expense", "debit": 700.0, "credit": 0.0, "memo": "AI draft"},
                    {"account_code": "2100", "account_name": "Accounts Payable", "debit": 0.0, "credit": 700.0, "memo": "AI draft"},
                ],
            },
            "summary_text": "AI drafted a balanced vendor bill journal entry for review.",
        }

    monkeypatch.setattr("app.hal.orchestrator.run_structured_output_workflow", fake_workflow)
    monkeypatch.setattr(
        "app.hal.orchestrator.queue_accounting_posting_draft",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("database unavailable")),
    )

    response = client.post(
        "/api/hal9000/accounting/journal-draft",
        auth=operator_auth(),
        json={
            "description": "Queue vendor bill for review.",
            "transaction_date": "2026-06-15",
            "accounting_period": "2026-06",
            "amount": 700.0,
            "context": {
                "use_local_ai_workflow": True,
                "auto_enqueue_validated_draft": True,
                "source_text": "Vendor invoice for dental supplies, $700 due next month.",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["draft_status"] == DRAFT_STATUS_DRAFT_ONLY
    assert payload["queue_id"] is None
    assert payload["queue_status"] is None
    assert "database unavailable" in payload["enqueue_error"]


def test_local_ai_journal_validator_rejects_negative_lines_and_closed_period():
    validator = orchestrator_module._build_local_ai_journal_validator(
        chart_of_accounts=orchestrator_module.get_chart_of_accounts(),
        accounting_period="2024-12",
        description="AI-generated journal draft",
    )

    result = validator(
        {
            "lines": [
                {
                    "account_code": "1310",
                    "account_name": "Prepaid Insurance",
                    "debit": -1200.0,
                    "credit": 0.0,
                    "memo": "AI draft",
                },
                {
                    "account_code": "1010",
                    "account_name": "Cash",
                    "debit": 0.0,
                    "credit": -1200.0,
                    "memo": "AI draft",
                },
            ]
        }
    )

    assert result["passed"] is False
    assert "Journal line amounts must be non-negative." in result["error"]
    assert "Accounting period is closed." in result["error"]


def test_build_journal_validation_rejects_non_numeric_line_amounts():
    validation = build_journal_validation(
        lines=[
            {
                "account_code": "1310",
                "account_name": "Prepaid Insurance",
                "debit": "abc",
                "credit": 0.0,
                "memo": "AI draft",
            },
            {
                "account_code": "1010",
                "account_name": "Cash",
                "debit": 0.0,
                "credit": "12oo",
                "memo": "AI draft",
            },
        ],
        chart_of_accounts=orchestrator_module.get_chart_of_accounts(),
        open_period=True,
    )

    assert validation["balanced"] is False
    assert validation["amount_validation_passed"] is False
    assert "Journal line amounts must be numeric: line 1 debit, line 2 credit" in validation["issues"]