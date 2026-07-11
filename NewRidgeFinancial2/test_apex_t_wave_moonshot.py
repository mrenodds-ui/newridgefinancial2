"""T-wave validation — Moonshot REAUDIT2 T0–T5 (no Ollama)."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from apex_backend import BUILD_ID, build_apex_widgets
from apex_import_watcher_pack import import_inbox_paths, poll_once, watcher_status
from apex_orchestrator_pack import orchestrator_enabled, orchestrator_status
from apex_qb_net_profit_pack import GAP_NET_PROFIT_PENDING, assess_net_profit_gap, ingest_net_profit_into_conn
from apex_softdent_aging_schedule_pack import GAP_AGING_PENDING, assess_aging_schedule_gap
from apex_softdent_production_pack import GAP_PRODUCTION_PENDING, assess_production_gap
from apex_unified_db_pack import (
    ingest_from_bundle,
    list_production_vs_payroll,
    open_unified,
    production_vs_payroll_widget,
)


def _full_bundle() -> dict:
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
            "caseAcceptance": {
                "rows": [
                    {
                        "period": "2026-06",
                        "Presented": 10000,
                        "Accepted": 7000,
                    }
                ]
            },
            "ar": {
                "rows": [
                    {"Bucket": "0-30", "Balance": 1000},
                    {"Bucket": "31-60", "Balance": 500},
                    {"Bucket": "90+", "Balance": 200},
                ]
            },
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


class TWaveMoonshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self._tmpdir.name) / "nr2_unified_t.db"

    def tearDown(self) -> None:
        try:
            self._tmpdir.cleanup()
        except Exception:
            pass

    def test_build_id(self):
        self.assertEqual(BUILD_ID, "hal-10481")

    def test_t5_orchestrator_default_on(self):
        prev = os.environ.pop("NR2_AI_ORCHESTRATOR", None)
        try:
            self.assertTrue(orchestrator_enabled())
            st = orchestrator_status()
            self.assertEqual(st.get("orchestratorDefault"), "ON")
            self.assertTrue(st.get("enabled"))
        finally:
            if prev is not None:
                os.environ["NR2_AI_ORCHESTRATOR"] = prev

    def test_t5_explicit_off(self):
        prev = os.environ.get("NR2_AI_ORCHESTRATOR")
        os.environ["NR2_AI_ORCHESTRATOR"] = "0"
        try:
            self.assertFalse(orchestrator_enabled())
        finally:
            if prev is None:
                os.environ.pop("NR2_AI_ORCHESTRATOR", None)
            else:
                os.environ["NR2_AI_ORCHESTRATOR"] = prev

    def test_t0_pending_honesty(self):
        gap = assess_production_gap({"softdent": {}})
        self.assertEqual(gap.get("gapCode"), GAP_PRODUCTION_PENDING)
        self.assertTrue(gap.get("productionPending"))

    def test_t1_pending_honesty(self):
        gap = assess_aging_schedule_gap({"softdent": {}})
        self.assertEqual(gap.get("gapCode"), GAP_AGING_PENDING)

    def test_t2_pending_honesty(self):
        gap = assess_net_profit_gap({"quickbooks": {}})
        self.assertEqual(gap.get("gapCode"), GAP_NET_PROFIT_PENDING)

    def test_t0_t1_t2_ingest(self):
        got = ingest_from_bundle(_full_bundle(), db_path=self.db_path)
        self.assertTrue(got.get("ok"))
        self.assertGreaterEqual(int(got.get("productionRows") or 0), 1)
        self.assertGreaterEqual(int(got.get("caseAcceptanceRows") or 0), 1)
        self.assertGreaterEqual(int(got.get("agingPeriods") or 0), 1)
        self.assertGreaterEqual(int(got.get("schedulingPeriods") or 0), 1)
        self.assertGreaterEqual(int(got.get("netProfitRows") or 0), 1)

    def test_t4_cross_ref_view(self):
        ingest_from_bundle(_full_bundle(), db_path=self.db_path)
        rows = list_production_vs_payroll(limit=5, db_path=self.db_path)
        self.assertTrue(rows)
        self.assertIn("totalProduction", rows[0])
        w = production_vs_payroll_widget(_full_bundle())
        self.assertEqual(w.get("id"), "production-vs-payroll")

    def test_t3_watcher_status(self):
        st = watcher_status()
        self.assertTrue(st.get("ok"))
        self.assertEqual(st.get("phase"), "T3")
        self.assertTrue(import_inbox_paths())
        # poll_once with high cutoff finds nothing — still ok
        out = poll_once(since_mtime=10**12)
        self.assertTrue(out.get("ok"))

    def test_widgets_present(self):
        for page, wid in (
            ("softdent", "softdent-production-gap"),
            ("softdent", "softdent-aging-gap"),
            ("financial", "production-vs-payroll"),
            ("quickbooks", "qb-net-profit-gap"),
        ):
            out = build_apex_widgets(page)
            ids = {w.get("id") for w in (out.get("widgets") or []) if isinstance(w, dict)}
            self.assertIn(wid, ids, f"{page}/{wid}")

    def test_t4_efficiency_audit_cross_ref(self):
        from apex_structured_insight_pack import ai_insight_widget

        ingest_from_bundle(_full_bundle(), db_path=self.db_path)
        w = ai_insight_widget(
            {
                "widget_type": "kpi-card",
                "title": "Efficiency",
                "type": "efficiency_audit",
                "data": {"value": None},
                "source_refs": ["softdent:production:2026-06"],
                "confidence": "low",
            }
        )
        self.assertEqual(w.get("id"), "hal-ai-insight")
        cross = w.get("crossRef") or {}
        self.assertEqual(cross.get("view"), "v_production_vs_payroll")


if __name__ == "__main__":
    unittest.main()
