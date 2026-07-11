"""Phase U0 validation — deep audit & forecast (no Ollama)."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from apex_backend import BUILD_ID, build_apex_widgets
from apex_deep_audit_pack import (
    GAP_AUDIT_DATA_PENDING,
    build_audit_snapshot,
    build_gap_insight,
    deep_audit_enabled,
    deep_audit_status,
    forecast_next_quarter,
    generate_monthly_audit,
    period_minus_months,
)
from apex_unified_db_pack import ingest_from_bundle


def _bundle() -> dict:
    return {
        "softdent": {
            "dashboard": {
                "rows": [
                    {
                        "period": "2026-06",
                        "production": 50000,
                        "collections": 42000,
                        "collectionsPending": False,
                    }
                ]
            },
            "procedures": {
                "rows": [
                    {
                        "period": "2026-06",
                        "Provider": "Reno",
                        "ProcCode": "D1110",
                        "Amount": 150,
                        "Qty": 2,
                    }
                ]
            },
            "caseAcceptance": {"rows": [{"period": "2026-06", "Presented": 10000, "Accepted": 7000}]},
            "ar": {"rows": [{"Bucket": "0-30", "Balance": 1000}]},
            "operatory": {
                "rows": [
                    {
                        "period": "2026-06",
                        "Appointments": 40,
                        "Broken": 4,
                        "Capacity": 80,
                        "Used": 60,
                    }
                ]
            },
        },
        "quickbooks": {
            "profitAndLoss": {
                "rows": [
                    {
                        "period": "2026-06",
                        "TotalIncome": 50000,
                        "TotalExpenses": 20000,
                        "Payroll": 12000,
                        "NetIncome": 18000,
                    }
                ]
            },
            "expenseCategories": {"rows": [{"Category": "Supplies", "Amount": 1000}]},
            "payroll": {
                "rows": [
                    {
                        "Employee": "Jane",
                        "Wages": 4000,
                        "period": "2026-06",
                        "NetPay": 3200,
                    }
                ]
            },
        },
    }


class DeepAuditPhaseU0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self._tmpdir.name) / "nr2_unified_u0.db"

    def tearDown(self) -> None:
        try:
            self._tmpdir.cleanup()
        except Exception:
            pass

    def test_build_id(self):
        self.assertEqual(BUILD_ID, "hal-10483")

    def test_period_math(self):
        self.assertEqual(period_minus_months("2026-06", 5), "2026-01")
        self.assertEqual(period_minus_months("2026-02", 3), "2025-11")

    def test_flag_default_on(self):
        prev = os.environ.pop("NR2_DEEP_AUDIT", None)
        try:
            self.assertTrue(deep_audit_enabled())
            st = deep_audit_status()
            self.assertTrue(st.get("deepAuditEnabled"))
        finally:
            if prev is not None:
                os.environ["NR2_DEEP_AUDIT"] = prev

    def test_flag_off(self):
        prev = os.environ.get("NR2_DEEP_AUDIT")
        os.environ["NR2_DEEP_AUDIT"] = "0"
        try:
            self.assertFalse(deep_audit_enabled())
            out = generate_monthly_audit(classify_only=True, force_orchestrator=True)
            self.assertFalse(out.get("ok"))
            self.assertEqual(out.get("reason"), "deep_audit_disabled")
        finally:
            if prev is None:
                os.environ.pop("NR2_DEEP_AUDIT", None)
            else:
                os.environ["NR2_DEEP_AUDIT"] = prev

    def test_gap_honesty_empty_db(self):
        snap = build_audit_snapshot(period="2026-06", db_path=self.db_path)
        self.assertTrue(snap.get("dataPending"))
        self.assertIn(GAP_AUDIT_DATA_PENDING, snap.get("gapCodes") or [])
        gap = build_gap_insight(snap)
        self.assertTrue(gap.get("ok"))
        insight = gap.get("insight") or {}
        self.assertEqual(insight.get("widget_type"), "alert-banner")
        self.assertIsNone((insight.get("data") or {}).get("value"))

    def test_orchestrator_disabled(self):
        result = generate_monthly_audit(
            classify_only=True,
            force_orchestrator=False,
            db_path=self.db_path,
        )
        self.assertFalse(result.get("ok"))
        self.assertEqual(result.get("reason"), "orchestrator_disabled")

    def test_classify_only_deep_lane(self):
        ingest_from_bundle(_bundle(), db_path=self.db_path)
        result = generate_monthly_audit(
            period="2026-06",
            classify_only=True,
            force_orchestrator=True,
            db_path=self.db_path,
        )
        self.assertTrue(result.get("ok"))
        self.assertEqual(result.get("phase"), "U0")
        self.assertEqual(result.get("lane"), "escalate30b")
        self.assertTrue(result.get("classifyOnly"))
        self.assertFalse((result.get("snapshot") or {}).get("dataPending"))

    def test_forecast_scaffold_null_future(self):
        ingest_from_bundle(_bundle(), db_path=self.db_path)
        result = forecast_next_quarter(
            period="2026-06",
            classify_only=True,
            force_orchestrator=True,
            db_path=self.db_path,
        )
        self.assertTrue(result.get("ok"))
        trend = result.get("trendInsight") or {}
        self.assertTrue(trend.get("ok"))
        series = ((trend.get("insight") or {}).get("data") or {}).get("series") or []
        future = [s for s in series if str(s.get("label") or "").endswith("*")]
        self.assertTrue(future)
        self.assertTrue(all(s.get("value") is None for s in future))

    def test_widget_present(self):
        out = build_apex_widgets("financial")
        ids = {w.get("id") for w in (out.get("widgets") or []) if isinstance(w, dict)}
        self.assertIn("deep-audit-status", ids)


if __name__ == "__main__":
    unittest.main()
