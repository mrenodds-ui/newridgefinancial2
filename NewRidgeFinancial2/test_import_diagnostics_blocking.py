"""Tests for import diagnostics blocking vs optional datasets."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from import_diagnostics import blocking_import_issues, evaluate_bundle


class ImportDiagnosticsBlockingTests(unittest.TestCase):
    def test_blocking_import_issues_ignores_optional_missing(self) -> None:
        bundle = {
            "softdent": {
                "dashboard": {
                    "sourceFile": "softdent_dashboard_data.json",
                    "rows": [
                        {"period": "2026-06", "production": 1000, "collections": 900},
                        {"period": "2026-05", "production": 900, "collections": 800},
                    ],
                },
                "claims": {"sourceFile": "softdent_claims.csv", "rows": [{"ClaimId": "1"}]},
                "clinicalNotes": {"sourceFile": "softdent_clinical_notes.csv", "rows": [{"NoteId": "1"}]},
                "ar": {"sourceFile": "softdent_ar.csv", "rows": [{"Bucket": "0-30", "Amount": 100}]},
                "newPatients": {"sourceFile": "softdent_new_patients.csv", "rows": [{"Period": "2026-06", "Count": 1}]},
            },
            "quickbooks": {
                "revenue": {"sourceFile": "quickbooks_revenue.csv", "rows": [{"Period": "2026-06", "TotalIncome": 1}]},
                "expenses": {"sourceFile": "quickbooks_expenses.csv", "rows": [{"Period": "2026-06", "TotalExpense": 1}]},
                "expenseCategories": {
                    "sourceFile": "quickbooks_expense_categories.csv",
                    "rows": [{"Category": "Supplies", "Amount": 1}],
                },
                "profitAndLoss": {
                    "sourceFile": "quickbooks_profit_and_loss.csv",
                    "rows": [{"Period": "2026-06", "TotalIncome": 1, "TotalExpense": 1, "NetIncome": 0}],
                },
            },
        }
        diagnostics = evaluate_bundle(bundle, deep=False)
        self.assertGreaterEqual(diagnostics["summary"]["missingOptional"], 2)
        self.assertEqual(blocking_import_issues(diagnostics), [])

    def test_blocking_import_issues_ignores_warning_stale(self) -> None:
        fresh = "2026-07-04T16:55:00+00:00"
        bundle = {
            "softdent": {
                "dashboard": {
                    "sourceFile": "softdent_dashboard_data.json",
                    "modifiedAt": fresh,
                    "rows": [
                        {"period": "2026-06", "production": 1000, "collections": 900},
                        {"period": "2026-05", "production": 900, "collections": 800},
                    ],
                },
                "claims": {"sourceFile": "softdent_claims.csv", "modifiedAt": fresh, "rows": [{"ClaimId": "1"}]},
                "clinicalNotes": {"sourceFile": "softdent_clinical_notes.csv", "modifiedAt": fresh, "rows": [{"NoteId": "1"}]},
                "ar": {"sourceFile": "softdent_ar.csv", "modifiedAt": fresh, "rows": [{"Bucket": "0-30", "Amount": 100}]},
                "newPatients": {"sourceFile": "softdent_new_patients.csv", "modifiedAt": fresh, "rows": [{"Period": "2026-06", "Count": 1}]},
            },
            "quickbooks": {
                "revenue": {
                    "sourceFile": "quickbooks_revenue.csv",
                    "modifiedAt": fresh,
                    "rows": [{"Period": "2026-06", "TotalIncome": 1}],
                },
                "expenses": {
                    "sourceFile": "quickbooks_expenses.csv",
                    "modifiedAt": fresh,
                    "rows": [{"Period": "2026-06", "TotalExpense": 1}],
                },
                "expenseCategories": {
                    "sourceFile": "quickbooks_expense_categories.csv",
                    "modifiedAt": "2026-07-02T12:00:00+00:00",
                    "rows": [{"Category": "Supplies", "Amount": 1}],
                },
                "profitAndLoss": {
                    "sourceFile": "quickbooks_profit_and_loss.csv",
                    "modifiedAt": fresh,
                    "rows": [{"Period": "2026-06", "TotalIncome": 1, "TotalExpense": 1, "NetIncome": 0}],
                },
            },
        }
        diagnostics = evaluate_bundle(bundle, deep=False)
        stale = next(row for row in diagnostics["datasets"] if row["datasetKey"] == "quickbooks.expenseCategories")
        self.assertEqual(stale["status"], "stale")
        self.assertEqual(stale["severity"], "warning")
        self.assertEqual(blocking_import_issues(diagnostics), [])

    def test_upstream_stale_keeps_connected_when_local_cache_fresh(self) -> None:
        import os
        import tempfile
        from pathlib import Path

        from import_diagnostics import STATUS_CONNECTED, evaluate_dataset, load_manifest_payload

        manifest = load_manifest_payload()
        contract = dict(manifest["datasets"]["softdent.dashboard"])
        with tempfile.TemporaryDirectory() as tmp:
            upstream = Path(tmp)
            upstream_file = upstream / "softdent_dashboard_data.json"
            upstream_file.write_text("[]", encoding="utf-8")
            old = datetime(2026, 6, 1, tzinfo=timezone.utc)
            ts = old.timestamp()
            os.utime(upstream_file, (ts, ts))
            fresh = datetime.now(timezone.utc).isoformat()
            item = evaluate_dataset(
                "softdent.dashboard",
                contract,
                {
                    "sourceFile": "softdent_dashboard_data.json",
                    "modifiedAt": fresh,
                    "rows": [
                        {"period": "2026-06", "production": 1000, "collections": 900},
                        {"period": "2026-05", "production": 900, "collections": 800},
                    ],
                },
                manifest=manifest,
                upstream_roots=[upstream],
            )
            self.assertEqual(item["status"], STATUS_CONNECTED)
            self.assertIn("Local cache is fresh", item["detail"])
            self.assertIn("upstream source is", item["detail"])


if __name__ == "__main__":
    unittest.main()
