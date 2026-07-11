"""Phase U2 validation — SoftDent×QB reconciliation (no Ollama)."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from apex_backend import BUILD_ID, build_apex_widgets
from apex_reconciliation_pack import (
    GAP_RECON_PENDING,
    GAP_RECON_VARIANCE,
    build_variance_insight,
    check_production_payroll_variance,
    reconciliation_enabled,
    run_reconciliation,
    variance_threshold_abs,
    variance_threshold_pct,
)
from apex_unified_db_pack import ingest_from_bundle


def _bundle_two_periods() -> dict:
    return {
        "softdent": {
            "dashboard": {
                "rows": [
                    {
                        "period": "2026-05",
                        "production": 40000,
                        "collections": 35000,
                        "collectionsPending": False,
                    },
                    {
                        "period": "2026-06",
                        "production": 52000,
                        "collections": 48000,
                        "collectionsPending": False,
                    },
                ]
            },
            "procedures": {
                "rows": [
                    {"period": "2026-05", "Provider": "Reno", "ProcCode": "D1110", "Amount": 200, "Qty": 1},
                    {"period": "2026-06", "Provider": "Reno", "ProcCode": "D1110", "Amount": 400, "Qty": 1},
                ]
            },
            "caseAcceptance": {"rows": [{"period": "2026-06", "Presented": 10000, "Accepted": 7000}]},
            "ar": {"rows": [{"Bucket": "0-30", "Balance": 1000}]},
            "operatory": {
                "rows": [{"period": "2026-06", "Appointments": 40, "Broken": 4, "Capacity": 80, "Used": 60}]
            },
        },
        "quickbooks": {
            "profitAndLoss": {
                "rows": [
                    {
                        "period": "2026-05",
                        "TotalIncome": 40000,
                        "TotalExpenses": 15000,
                        "Payroll": 8000,
                        "NetIncome": 17000,
                    },
                    {
                        "period": "2026-06",
                        "TotalIncome": 52000,
                        "TotalExpenses": 18000,
                        "Payroll": 15000,
                        "NetIncome": 19000,
                    },
                ]
            },
            "expenseCategories": {"rows": [{"Category": "Supplies", "Amount": 1000}]},
            "payroll": {
                "rows": [
                    {"Employee": "Jane", "Wages": 3000, "period": "2026-05", "NetPay": 2400},
                    {"Employee": "Jane", "Wages": 6000, "period": "2026-06", "NetPay": 4800},
                ]
            },
            "ap": {
                "rows": [
                    {"period": "2026-05", "Vendor": "SupplyCo", "AmountDue": 500},
                    {"period": "2026-06", "Vendor": "SupplyCo", "AmountDue": 2000},
                ]
            },
        },
    }


class ReconciliationPhaseU2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self._tmpdir.name) / "nr2_unified_u2.db"

    def tearDown(self) -> None:
        try:
            self._tmpdir.cleanup()
        except Exception:
            pass

    def test_build_id(self):
        self.assertEqual(BUILD_ID, "hal-10486")

    def test_thresholds_default(self):
        prev_p = os.environ.pop("NR2_VARIANCE_PCT", None)
        prev_a = os.environ.pop("NR2_VARIANCE_ABS", None)
        try:
            self.assertAlmostEqual(variance_threshold_pct(), 0.05)
            self.assertAlmostEqual(variance_threshold_abs(), 500.0)
        finally:
            if prev_p is not None:
                os.environ["NR2_VARIANCE_PCT"] = prev_p
            if prev_a is not None:
                os.environ["NR2_VARIANCE_ABS"] = prev_a

    def test_flag_default_on(self):
        prev = os.environ.pop("NR2_RECONCILIATION", None)
        try:
            self.assertTrue(reconciliation_enabled())
        finally:
            if prev is not None:
                os.environ["NR2_RECONCILIATION"] = prev

    def test_pending_empty_db(self):
        finding = check_production_payroll_variance("2026-06", db_path=self.db_path)
        self.assertEqual(finding.get("gapCode"), GAP_RECON_PENDING)
        self.assertFalse(finding.get("alert"))

    def test_mom_variance_alert(self):
        ingest_from_bundle(_bundle_two_periods(), db_path=self.db_path)
        finding = check_production_payroll_variance("2026-06", db_path=self.db_path)
        self.assertTrue(finding.get("alert"))
        self.assertEqual(finding.get("gapCode"), GAP_RECON_VARIANCE)
        insight = build_variance_insight(finding)
        self.assertTrue(insight.get("ok"))
        self.assertEqual((insight.get("insight") or {}).get("widget_type"), "alert-banner")

    def test_run_classify_only(self):
        ingest_from_bundle(_bundle_two_periods(), db_path=self.db_path)
        result = run_reconciliation(
            period="2026-06",
            classify_only=True,
            force_orchestrator=True,
            db_path=self.db_path,
            explain=True,
        )
        self.assertTrue(result.get("ok"))
        self.assertEqual(result.get("phase"), "U2")
        self.assertGreaterEqual(int(result.get("alertCount") or 0), 1)
        orch = result.get("orchestrator") or {}
        self.assertEqual(orch.get("lane"), "escalate30b")
        self.assertTrue(orch.get("classifyOnly") or result.get("classifyOnly"))

    def test_disabled(self):
        prev = os.environ.get("NR2_RECONCILIATION")
        os.environ["NR2_RECONCILIATION"] = "0"
        try:
            result = run_reconciliation(classify_only=True, db_path=self.db_path)
            self.assertFalse(result.get("ok"))
            self.assertEqual(result.get("reason"), "reconciliation_disabled")
        finally:
            if prev is None:
                os.environ.pop("NR2_RECONCILIATION", None)
            else:
                os.environ["NR2_RECONCILIATION"] = prev

    def test_widget(self):
        out = build_apex_widgets("financial")
        ids = {w.get("id") for w in (out.get("widgets") or []) if isinstance(w, dict)}
        self.assertIn("reconciliation-status", ids)


if __name__ == "__main__":
    unittest.main()
