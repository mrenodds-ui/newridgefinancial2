import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.auth import clear_user_registry_cache
from app.hal.orchestrator import queue_accounting_posting_draft
from app.hal.posting_queue import ENQUEUE_MODE_MANUAL_REVIEW_QUEUE, POSTING_QUEUE_STATUS_PENDING_REVIEW
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


def test_accounting_posting_queue_accepts_valid_draft(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HAL_ALLOWED_BASE_PATH", str(tmp_path))
    workspace_root = tmp_path / "AI_Workspace"
    monkeypatch.setenv("HAL_AI_WORKSPACE_PATH", str(workspace_root))
    response = client.post(
        "/api/hal9000/accounting/posting-queue",
        auth=operator_auth(),
        json={
            "description": "Queue prepaid insurance entry for QuickBooks Desktop review.",
            "transaction_date": "2026-06-15",
            "accounting_period": "2026-06",
            "amount": 1200.0,
            "transaction_type": "prepaid_insurance",
            "source_audit_id": "hal-source-123",
            "lines": [
                {"account_code": "1310", "account_name": "Prepaid Insurance", "debit": 1200.0, "credit": 0.0, "memo": "Queue prepaid insurance entry for QuickBooks Desktop review."},
                {"account_code": "1010", "account_name": "Cash", "debit": 0.0, "credit": 1200.0, "memo": "Queue prepaid insurance entry for QuickBooks Desktop review."},
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["queue_id"].startswith("qbd-queue-")
    assert payload["target_system"] == "quickbooks_desktop"
    assert payload["status"] == POSTING_QUEUE_STATUS_PENDING_REVIEW
    assert payload["validation"]["balanced"] is True
    assert payload["review_required"] is True
    assert payload["enqueue_mode"] == ENQUEUE_MODE_MANUAL_REVIEW_QUEUE
    assert payload["review_plan_path"] is None
    review_plan = next((workspace_root / "review_plans").glob("*.json"), None)
    assert review_plan is not None and review_plan.exists()
    assert payload["audit_id"].startswith("hal-")
    assert "queue-accounting-draft" in (workspace_root / "ai_activity.log").read_text(encoding="utf-8")

    listing = client.get("/api/hal9000/accounting/posting-queue?limit=5", auth=operator_auth())
    assert listing.status_code == 200
    listing_payload = listing.json()
    assert listing_payload["count"] >= 1
    assert any(item["queue_id"] == payload["queue_id"] and item["review_plan_path"] is None for item in listing_payload["items"])

    metrics = client.get("/api/hal9000/accounting/posting-queue/metrics", auth=operator_auth())
    assert metrics.status_code == 200
    metrics_payload = metrics.json()
    assert metrics_payload["total_count"] >= 1
    assert metrics_payload["pending_review_count"] >= 1


def test_accounting_posting_queue_rejects_invalid_transaction_date():
    response = client.post(
        "/api/hal9000/accounting/posting-queue",
        auth=operator_auth(),
        json={
            "description": "Queue prepaid insurance entry for QuickBooks Desktop review.",
            "transaction_date": "2026-99-99",
            "accounting_period": "2026-06",
            "amount": 1200.0,
            "transaction_type": "prepaid_insurance",
            "source_audit_id": "hal-source-invalid-date",
            "lines": [
                {"account_code": "1310", "account_name": "Prepaid Insurance", "debit": 1200.0, "credit": 0.0, "memo": "Queue prepaid insurance entry for QuickBooks Desktop review."},
                {"account_code": "1010", "account_name": "Cash", "debit": 0.0, "credit": 1200.0, "memo": "Queue prepaid insurance entry for QuickBooks Desktop review."},
            ],
        },
    )

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any(error.get("loc") == ["body", "transaction_date"] for error in errors)


def test_accounting_posting_queue_list_filters_and_paginates():
    pending = client.post(
        "/api/hal9000/accounting/posting-queue",
        auth=operator_auth(),
        json={
            "description": "Queue supplies accrual for review.",
            "transaction_date": "2026-06-15",
            "accounting_period": "2026-06",
            "amount": 300.0,
            "transaction_type": "supplies_accrual",
            "source_audit_id": "hal-source-201",
            "lines": [
                {"account_code": "5200", "account_name": "Dental Supplies Expense", "debit": 300.0, "credit": 0.0, "memo": "Queue supplies accrual for review."},
                {"account_code": "2200", "account_name": "Accrued Expenses", "debit": 0.0, "credit": 300.0, "memo": "Queue supplies accrual for review."},
            ],
        },
    )
    assert pending.status_code == 200

    approved = client.post(
        "/api/hal9000/accounting/posting-queue",
        auth=operator_auth(),
        json={
            "description": "Queue equipment purchase for review.",
            "transaction_date": "2026-06-15",
            "accounting_period": "2026-06",
            "amount": 900.0,
            "transaction_type": "equipment_purchase",
            "source_audit_id": "hal-source-202",
            "lines": [
                {"account_code": "1500", "account_name": "Equipment", "debit": 900.0, "credit": 0.0, "memo": "Queue equipment purchase for review."},
                {"account_code": "1010", "account_name": "Cash", "debit": 0.0, "credit": 900.0, "memo": "Queue equipment purchase for review."},
            ],
        },
    )
    assert approved.status_code == 200
    approved_queue_id = approved.json()["queue_id"]

    approved_review = client.post(
        f"/api/hal9000/accounting/posting-queue/{approved_queue_id}/review",
        auth=operator_auth(),
        json={"action": "approved", "review_note": "Approved for test pagination."},
    )
    assert approved_review.status_code == 200

    filtered = client.get("/api/hal9000/accounting/posting-queue?limit=10&status=approved", auth=operator_auth())
    assert filtered.status_code == 200
    filtered_payload = filtered.json()
    assert filtered_payload["status"] == "approved"
    assert filtered_payload["total_count"] >= 1
    assert filtered_payload["range_start"] >= 1
    assert filtered_payload["range_end"] >= filtered_payload["range_start"]
    assert all(item["status"] == "approved" for item in filtered_payload["items"])
    assert filtered_payload["cursor"] is None

    first_page = client.get("/api/hal9000/accounting/posting-queue?limit=1", auth=operator_auth())
    assert first_page.status_code == 200
    first_page_payload = first_page.json()
    assert first_page_payload["limit"] == 1
    assert first_page_payload["count"] == 1
    assert first_page_payload["range_start"] == 1
    assert first_page_payload["range_end"] == 1
    assert first_page_payload["next_cursor"]

    second_page = client.get(
        "/api/hal9000/accounting/posting-queue",
        params={"limit": 1, "cursor": first_page_payload["next_cursor"]},
        auth=operator_auth(),
    )
    assert second_page.status_code == 200
    second_page_payload = second_page.json()
    assert second_page_payload["limit"] == 1
    assert second_page_payload["cursor"] == first_page_payload["next_cursor"]
    assert second_page_payload["count"] == 1
    assert second_page_payload["total_count"] == first_page_payload["total_count"]
    assert second_page_payload["range_start"] == 2
    assert second_page_payload["range_end"] == 2
    assert second_page_payload["items"][0]["queue_id"] != first_page_payload["items"][0]["queue_id"]


def test_accounting_posting_queue_rejects_invalid_cursor():
    response = client.get("/api/hal9000/accounting/posting-queue?limit=5&cursor=invalid-cursor", auth=operator_auth())
    assert response.status_code == 400
    assert "Posting queue cursor is invalid." in response.json()["detail"]


def test_accounting_posting_queue_rejects_invalid_status_filter():
    response = client.get("/api/hal9000/accounting/posting-queue?limit=5&status=archived", auth=operator_auth())
    assert response.status_code == 422


def test_accounting_posting_queue_activity_returns_lightweight_recent_items():
    queued = client.post(
        "/api/hal9000/accounting/posting-queue",
        auth=operator_auth(),
        json={
            "description": "Queue supplies accrual for recent activity.",
            "transaction_date": "2026-06-15",
            "accounting_period": "2026-06",
            "amount": 250.0,
            "transaction_type": "supplies_accrual",
            "source_audit_id": "hal-source-301",
            "lines": [
                {"account_code": "5200", "account_name": "Dental Supplies Expense", "debit": 250.0, "credit": 0.0, "memo": "Queue supplies accrual for recent activity."},
                {"account_code": "2200", "account_name": "Accrued Expenses", "debit": 0.0, "credit": 250.0, "memo": "Queue supplies accrual for recent activity."},
            ],
        },
    )
    assert queued.status_code == 200

    activity = client.get("/api/hal9000/accounting/posting-queue/activity?limit=3", auth=operator_auth())
    assert activity.status_code == 200
    activity_payload = activity.json()
    assert activity_payload["limit"] == 3
    assert activity_payload["count"] >= 1
    assert activity_payload["items"][0]["enqueue_mode"] == ENQUEUE_MODE_MANUAL_REVIEW_QUEUE
    assert "lines" not in activity_payload["items"][0]
    assert "validation" not in activity_payload["items"][0]


def test_accounting_posting_queue_review_updates_status_and_reviewer(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HAL_ALLOWED_BASE_PATH", str(tmp_path))
    workspace_root = tmp_path / "AI_Workspace"
    monkeypatch.setenv("HAL_AI_WORKSPACE_PATH", str(workspace_root))
    queued = client.post(
        "/api/hal9000/accounting/posting-queue",
        auth=operator_auth(),
        json={
            "description": "Queue vendor bill for QuickBooks Desktop review.",
            "transaction_date": "2026-06-15",
            "accounting_period": "2026-06",
            "amount": 700.0,
            "transaction_type": "vendor_bill",
            "source_audit_id": "hal-source-125",
            "lines": [
                {"account_code": "5200", "account_name": "Dental Supplies Expense", "debit": 700.0, "credit": 0.0, "memo": "Queue vendor bill for QuickBooks Desktop review."},
                {"account_code": "2100", "account_name": "Accounts Payable", "debit": 0.0, "credit": 700.0, "memo": "Queue vendor bill for QuickBooks Desktop review."},
            ],
        },
    )
    assert queued.status_code == 200
    queue_id = queued.json()["queue_id"]

    reviewed = client.post(
        f"/api/hal9000/accounting/posting-queue/{queue_id}/review",
        auth=operator_auth(),
        json={
            "action": "approved",
            "review_note": "Validated against June vendor support.",
        },
    )

    assert reviewed.status_code == 200
    payload = reviewed.json()
    assert payload["status"] == "approved"
    assert payload["reviewer_actor"] == "hal_operator"
    assert payload["reviewed_at_utc"]
    assert payload["review_note"] == "Validated against June vendor support."
    assert payload["review_required"] is False
    assert payload["audit_id"].startswith("hal-")
    log_text = (workspace_root / "ai_activity.log").read_text(encoding="utf-8")
    assert "queue-accounting-draft" in log_text
    assert "posting-queue-approved" in log_text

    metrics = client.get("/api/hal9000/accounting/posting-queue/metrics", auth=operator_auth())
    assert metrics.status_code == 200
    metrics_payload = metrics.json()
    assert metrics_payload["approved_count"] >= 1


def test_accounting_posting_queue_review_rejects_second_review():
    queued = client.post(
        "/api/hal9000/accounting/posting-queue",
        auth=operator_auth(),
        json={
            "description": "Queue payroll accrual for review.",
            "transaction_date": "2026-06-30",
            "accounting_period": "2026-06",
            "amount": 4200.0,
            "transaction_type": "payroll_accrual",
            "source_audit_id": "hal-source-126",
            "lines": [
                {"account_code": "6200", "account_name": "Payroll Expense", "debit": 4200.0, "credit": 0.0, "memo": "Queue payroll accrual for review."},
                {"account_code": "2200", "account_name": "Accrued Expenses", "debit": 0.0, "credit": 4200.0, "memo": "Queue payroll accrual for review."},
            ],
        },
    )
    assert queued.status_code == 200
    queue_id = queued.json()["queue_id"]

    first_review = client.post(
        f"/api/hal9000/accounting/posting-queue/{queue_id}/review",
        auth=operator_auth(),
        json={"action": "rejected", "review_note": "Need corrected support."},
    )
    assert first_review.status_code == 200

    second_review = client.post(
        f"/api/hal9000/accounting/posting-queue/{queue_id}/review",
        auth=operator_auth(),
        json={"action": "approved", "review_note": "Retry should fail."},
    )
    assert second_review.status_code == 400
    assert "Only pending review queue entries can be approved or rejected." in second_review.json()["detail"]


def test_accounting_posting_queue_rejects_invalid_draft():
    response = client.post(
        "/api/hal9000/accounting/posting-queue",
        auth=operator_auth(),
        json={
            "description": "Queue invalid entry for review.",
            "transaction_date": "2026-06-15",
            "accounting_period": "2024-12",
            "amount": 1200.0,
            "transaction_type": "prepaid_insurance",
            "source_audit_id": "hal-source-124",
            "lines": [
                {"account_code": "1310", "account_name": "Prepaid Insurance", "debit": 1200.0, "credit": 0.0, "memo": "Queue invalid entry for review."},
                {"account_code": "1010", "account_name": "Cash", "debit": 0.0, "credit": 1100.0, "memo": "Queue invalid entry for review."},
            ],
        },
    )

    assert response.status_code == 400
    assert "Only balanced, valid, open-period drafts can be queued" in response.json()["detail"]


def test_accounting_posting_queue_rejects_negative_line_amounts(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HAL_ALLOWED_BASE_PATH", str(tmp_path))
    monkeypatch.setenv("HAL_AI_WORKSPACE_PATH", str(tmp_path / "AI_Workspace"))

    with pytest.raises(ValueError, match="Only balanced, valid, open-period drafts can be queued"):
        queue_accounting_posting_draft(
            description="Queue invalid negative journal draft.",
            transaction_date="2026-06-15",
            accounting_period="2026-06",
            amount=1200.0,
            transaction_type="prepaid_insurance",
            source_audit_id="hal-source-negative-123",
            actor="hal_operator",
            lines=[
                {
                    "account_code": "1310",
                    "account_name": "Prepaid Insurance",
                    "debit": -1200.0,
                    "credit": 0.0,
                    "memo": "Queue invalid negative journal draft.",
                },
                {
                    "account_code": "1010",
                    "account_name": "Cash",
                    "debit": 0.0,
                    "credit": -1200.0,
                    "memo": "Queue invalid negative journal draft.",
                },
            ],
        )


def test_accounting_posting_queue_rejects_invalid_enqueue_mode():
    response = client.post(
        "/api/hal9000/accounting/posting-queue",
        auth=operator_auth(),
        json={
            "description": "Queue prepaid insurance entry for QuickBooks Desktop review.",
            "transaction_date": "2026-06-15",
            "accounting_period": "2026-06",
            "amount": 1200.0,
            "transaction_type": "prepaid_insurance",
            "source_audit_id": "hal-source-123",
            "enqueue_mode": "legacy_import",
            "lines": [
                {"account_code": "1310", "account_name": "Prepaid Insurance", "debit": 1200.0, "credit": 0.0, "memo": "Queue prepaid insurance entry for QuickBooks Desktop review."},
                {"account_code": "1010", "account_name": "Cash", "debit": 0.0, "credit": 1200.0, "memo": "Queue prepaid insurance entry for QuickBooks Desktop review."},
            ],
        },
    )

    assert response.status_code == 422