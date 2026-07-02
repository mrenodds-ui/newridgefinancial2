"""Tests for import diagnostics blocking vs optional datasets."""

from __future__ import annotations

from import_diagnostics import STATUS_MISSING, blocking_import_issues, evaluate_bundle


def test_blocking_import_issues_ignores_optional_missing() -> None:
    bundle = {
        "softdent": {
            "dashboard": {"sourceFile": "softdent_dashboard_data.json", "rows": [{"period": "2026-06"}]},
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
        },
    }
    diagnostics = evaluate_bundle(bundle, deep=False)
    assert diagnostics["summary"]["missingOptional"] >= 2
    assert blocking_import_issues(diagnostics) == []
