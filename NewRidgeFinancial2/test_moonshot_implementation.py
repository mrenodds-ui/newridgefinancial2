"""Moonshot implementation backlog items 1-12 — integration tests."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class _FakeStore:
    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self.db_path = Path(tempfile.gettempdir()) / f"nr2-impl-test-{id(self)}.db"

    def get(self, key: str):
        return self._data.get(key)

    def set(self, key: str, value: str) -> None:
        self._data[key] = value

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        from hal_employee_workflows import init_employee_workflow_schemas

        init_employee_workflow_schemas(conn)
        return conn


class ImportCompletenessTests(unittest.TestCase):
    def test_completeness_scores_connected_datasets(self) -> None:
        from import_diagnostics import STATUS_CONNECTED, assess_import_completeness

        diag = {
            "datasets": [
                {"severity": "critical", "automated": True, "status": STATUS_CONNECTED, "rowCount": 10},
                {"severity": "critical", "automated": True, "status": STATUS_CONNECTED, "rowCount": 5},
            ]
        }
        result = assess_import_completeness(diag)
        self.assertEqual(result["scorePct"], 100.0)
        self.assertTrue(result["ok"])

    def test_warning_gaps_do_not_fail_completeness(self) -> None:
        from import_diagnostics import STATUS_CONNECTED, STATUS_MISSING, assess_import_completeness

        diag = {
            "datasets": [
                {"severity": "critical", "automated": True, "status": STATUS_CONNECTED, "rowCount": 10, "datasetKey": "a"},
                {
                    "severity": "warning",
                    "automated": True,
                    "status": STATUS_MISSING,
                    "rowCount": 0,
                    "datasetKey": "quickbooks.expenseCategories",
                },
                {
                    "severity": "optional",
                    "automated": True,
                    "status": STATUS_MISSING,
                    "rowCount": 0,
                    "datasetKey": "quickbooks.payroll",
                },
            ]
        }
        result = assess_import_completeness(diag)
        self.assertTrue(result["ok"])
        self.assertEqual(result["required"], 1)
        self.assertEqual(result["gaps"], [])
        self.assertEqual(len(result.get("softGaps") or []), 1)

    def test_list_dataset_gaps_includes_optional_missing(self) -> None:
        from import_diagnostics import STATUS_CONNECTED, STATUS_MISSING, list_dataset_gaps

        diag = {
            "datasets": [
                {"severity": "critical", "automated": True, "status": STATUS_CONNECTED, "rowCount": 10, "datasetKey": "a"},
                {
                    "severity": "optional",
                    "automated": True,
                    "status": STATUS_MISSING,
                    "rowCount": 0,
                    "datasetKey": "quickbooks.payroll",
                    "system": "quickbooks",
                    "detail": "Dataset file not found in import cache.",
                },
                {
                    "severity": "optional",
                    "automated": True,
                    "status": STATUS_MISSING,
                    "rowCount": 0,
                    "datasetKey": "quickbooks.ap",
                    "system": "quickbooks",
                },
            ]
        }
        gaps = list_dataset_gaps(diag)
        keys = {g["datasetKey"] for g in gaps}
        self.assertEqual(keys, {"quickbooks.payroll", "quickbooks.ap"})
        self.assertTrue(all(g["severity"] == "optional" for g in gaps))

    def test_stale_critical_with_rows_counts_connected(self) -> None:
        from import_diagnostics import STATUS_CONNECTED, STATUS_STALE, assess_import_completeness

        diag = {
            "datasets": [
                {"severity": "critical", "automated": True, "status": STATUS_CONNECTED, "rowCount": 10, "datasetKey": "a"},
                {
                    "severity": "critical",
                    "automated": True,
                    "status": STATUS_STALE,
                    "rowCount": 4,
                    "datasetKey": "softdent.ar",
                },
            ]
        }
        result = assess_import_completeness(diag)
        self.assertTrue(result["ok"])
        self.assertEqual(result["connected"], 2)
        self.assertEqual(result["gaps"], [])
        self.assertEqual(len(result.get("softGaps") or []), 1)


class RbacWriteoffTests(unittest.TestCase):
    def test_tier1_office_manager(self) -> None:
        from nr2_rbac import evaluate_writeoff_approval

        r = evaluate_writeoff_approval(amount_usd=100, role="office_manager")
        self.assertTrue(r["allowed"])

    def test_dual_approval_large_amount(self) -> None:
        from nr2_rbac import evaluate_writeoff_approval

        r = evaluate_writeoff_approval(amount_usd=500, role="office_manager", prior_approvals=[])
        self.assertFalse(r["allowed"])
        r2 = evaluate_writeoff_approval(amount_usd=500, role="dentist", prior_approvals=["office_manager"])
        self.assertTrue(r2["allowed"])


class QbOAuthTests(unittest.TestCase):
    def test_exchange_requires_credentials(self) -> None:
        from qb_connector import exchange_authorization_code

        store = _FakeStore()
        with mock.patch.dict(os.environ, {}, clear=True):
            result = exchange_authorization_code(store, code="abc")
        self.assertFalse(result.get("ok"))


class DocumentVisionTests(unittest.TestCase):
    def test_heuristic_still_works(self) -> None:
        from document_classifier import classify_document_text

        r = classify_document_text("835 remittance ERA payment")
        self.assertEqual(r["category"], "EOB_ERA")


class EraPendingMatchesTests(unittest.TestCase):
    def test_list_empty(self) -> None:
        from hal_employee_workflows import list_pending_era_matches

        store = _FakeStore()
        result = list_pending_era_matches(store)
        self.assertTrue(result.get("ok"))
        self.assertEqual(result.get("count"), 0)


class SmsHardeningTests(unittest.TestCase):
    def test_rate_limit_blocks_when_exceeded(self) -> None:
        from sms_actions import SMS_RATE_LIMIT_PER_HOUR, send_billing_sms

        store = _FakeStore()
        conn = store._connect()
        with mock.patch("sms_actions._sms_rate_ok", return_value=False):
            result = send_billing_sms(conn, patient_id="P1", phone_number="+15551234567")
        self.assertEqual(result.get("error"), "sms_rate_limited")
        self.assertEqual(SMS_RATE_LIMIT_PER_HOUR, 30)


class ProductionValidatorTests(unittest.TestCase):
    def test_validator_returns_structure(self) -> None:
        import importlib.util
        from pathlib import Path

        script = Path(__file__).resolve().parent / "scripts" / "validate_production_readiness.py"
        spec = importlib.util.spec_from_file_location("validate_production_readiness", script)
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        with mock.patch("nr2_tls.ensure_localhost_tls_certificates", return_value=("cert.pem", "key.pem")):
            report = mod.run_checks()
        self.assertIn("checks", report)
        self.assertIn("ok", report)


if __name__ == "__main__":
    unittest.main()
