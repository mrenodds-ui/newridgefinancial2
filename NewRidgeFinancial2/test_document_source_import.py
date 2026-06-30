"""Verification tests for SoftDent/QuickBooks document source import."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from document_source_import import build_source_import_documents, merge_source_documents, sync_source_documents


class DocumentSourceImportTests(unittest.TestCase):
    def test_builds_rows_from_sample_bundle(self) -> None:
        bundle = {
            "quickbooks": {
                "expenseCategories": {
                    "sourceFile": "quickbooks_expense_categories.csv",
                    "rows": [{"Category": "Laboratory Fees", "Amount": "100.50"}],
                },
                "expenses": {
                    "sourceFile": "quickbooks_expenses.csv",
                    "rows": [{"Period": "2026-06", "TotalExpense": "2500"}],
                },
                "revenue": {
                    "sourceFile": "quickbooks_revenue.csv",
                    "rows": [{"Period": "2026-06", "TotalIncome": "9000"}],
                },
            },
            "softdent": {
                "ar": {
                    "sourceFile": "softdent_ar_aging.csv",
                    "rows": [{"Bucket": "Current", "Balance": "42965.29"}],
                },
                "dashboard": {
                    "sourceFile": "softdent_dashboard_data.json",
                    "rows": [{"period": "2026-06", "production": 167536.0, "collections": 0.0}],
                },
            },
        }
        payload = build_source_import_documents(bundle)
        self.assertGreaterEqual(payload["counts"]["quickbooks"], 3)
        self.assertGreaterEqual(payload["counts"]["softdent"], 2)
        ids = {doc["id"] for doc in payload["queue"]}
        self.assertIn("QB-CAT-LABORATORY-FEES", ids)
        self.assertIn("QB-EXP-2026-06", ids)
        self.assertIn("SD-AR-CURRENT", ids)
        self.assertIn("SD-DASH-2026-06", ids)
        for doc in payload["queue"]:
            self.assertTrue(doc.get("autoImported"))
            self.assertIn(doc.get("sourceSystem"), ("quickbooks", "softdent"))

    def test_merge_preserves_manual_rows(self) -> None:
        state = {
            "entity": "Test",
            "queue": [
                {"id": "MANUAL-1", "type": "Invoice", "vendor": "Manual Vendor", "autoImported": False},
                {"id": "QB-CAT-OLD", "type": "Bill", "vendor": "Old", "autoImported": True, "sourceSystem": "quickbooks"},
            ],
            "previewById": {"MANUAL-1": {"vendor": "MANUAL"}},
        }
        payload = {
            "queue": [
                {"id": "QB-CAT-NEW", "type": "Bill", "vendor": "New", "autoImported": True, "sourceSystem": "quickbooks"},
            ],
            "previewById": {"QB-CAT-NEW": {"vendor": "NEW"}},
        }
        merged = merge_source_documents(state, payload)
        ids = [doc["id"] for doc in merged["queue"]]
        self.assertEqual(ids[0], "MANUAL-1")
        self.assertIn("QB-CAT-NEW", ids)
        self.assertNotIn("QB-CAT-OLD", ids)

    def test_sync_writes_to_local_store(self) -> None:
        bundle = {
            "quickbooks": {
                "expenseCategories": {
                    "sourceFile": "quickbooks_expense_categories.csv",
                    "rows": [{"Category": "Rent", "Amount": "1000"}],
                },
            },
            "softdent": {},
        }

        class FakeStore:
            def __init__(self) -> None:
                self.values: dict[str, str] = {}

            def get(self, key: str) -> str | None:
                return self.values.get(key)

            def set(self, key: str, value: str) -> None:
                self.values[key] = value

        store = FakeStore()
        with patch("document_source_import.build_source_import_documents", return_value=build_source_import_documents(bundle)):
            result = sync_source_documents(store)
        self.assertGreaterEqual(result["counts"]["quickbooks"], 1)
        raw = store.get("nr2:v2:documents")
        self.assertIsNotNone(raw)
        state = json.loads(raw or "{}")
        self.assertTrue(any(doc.get("sourceSystem") == "quickbooks" for doc in state.get("queue") or []))


if __name__ == "__main__":
    unittest.main()
