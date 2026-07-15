"""Phase S0 validation — QB payroll/AP honesty + unified ingest (no Ollama)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from apex_backend import build_apex_widgets, resolve_hal_board_actions
from nr2_contracts.qb_payroll import (
    GAP_PAYROLL_PENDING,
    assess_payroll_ap_gap,
    normalize_payroll_row,
    redact_phi,
)
from nr2_contracts.unified_db import ingest_from_bundle, list_practice_health_snapshots


def _bundle_with_payroll() -> dict:
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
            }
        },
        "quickbooks": {
            "expenseCategories": {"rows": [{"Category": "Supplies", "Amount": 1000}]},
            "profitAndLoss": {"rows": [{"period": "2026-06", "NetIncome": 5000}]},
            "payroll": {
                "rows": [
                    {
                        "Employee": "Jane Doe SSN 123-45-6789",
                        "Wages": 4000,
                        "MedicareEE": 50,
                        "SS_EE": 200,
                        "MedicareER": 50,
                        "SS_ER": 200,
                        "NetPay": 3500,
                        "period": "2026-06",
                    }
                ]
            },
            "ap": {
                "rows": [
                    {
                        "Vendor": "Lab Co",
                        "AmountDue": 800,
                        "DueDate": "2026-05-01",
                        "period": "2026-06",
                    }
                ]
            },
        },
    }


class QbPayrollPhaseS0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self._tmpdir.name) / "nr2_unified_s0.db"

    def tearDown(self) -> None:
        try:
            self._tmpdir.cleanup()
        except Exception:
            pass

    def test_redact_ssn(self):
        self.assertEqual(redact_phi("Jane 123-45-6789"), "Jane [REDACTED]")
        norm = normalize_payroll_row(
            {"Employee": "Bob 111-22-3333", "Wages": 1000, "NetPay": 800}
        )
        assert norm is not None
        self.assertNotIn("111-22-3333", norm["employee"])
        self.assertIn("[REDACTED]", norm["employee"])

    def test_pending_when_missing(self):
        gap = assess_payroll_ap_gap({"quickbooks": {}})
        self.assertTrue(gap.get("payrollPending"))
        self.assertTrue(gap.get("apPending"))
        self.assertNotEqual(gap.get("gapCode"), "OK")

    def test_ingest_payroll_ap(self):
        got = ingest_from_bundle(_bundle_with_payroll(), db_path=self.db_path)
        self.assertTrue(got.get("ok"))
        self.assertGreaterEqual(int(got.get("qbPayrollRows") or 0), 1)
        self.assertGreaterEqual(int(got.get("qbApRows") or 0), 1)
        snaps = list_practice_health_snapshots(limit=5, db_path=self.db_path)
        self.assertTrue(snaps)
        # SoftDent period 2026-06; payroll may land on period_qb from P&L
        by_p = {s["period"]: s for s in snaps}
        self.assertIn("2026-06", by_p)
        row = by_p["2026-06"]
        self.assertEqual(row.get("collections"), 42000)
        # Payroll on same period when row period matches
        if row.get("totalPayroll") is not None:
            self.assertGreater(row["totalPayroll"], 0)
            self.assertFalse(row.get("payrollPending"))

    def test_widgets_on_pages(self):
        for page in ("financial", "quickbooks"):
            out = build_apex_widgets(page)
            ids = {w.get("id") for w in (out.get("widgets") or []) if isinstance(w, dict)}
            self.assertIn("qb-payroll-gap", ids, page)
            self.assertIn("qb-ap-aging", ids, page)

    def test_hal_payroll(self):
        r = resolve_hal_board_actions({"query": "why is payroll pending", "page": "hal"})
        actions = r.get("actions") or []
        self.assertTrue(
            any(a.get("widgetId") == "qb-payroll-gap" for a in actions if isinstance(a, dict))
        )

    def test_hal_ap(self):
        r = resolve_hal_board_actions({"query": "show AP aging", "page": "hal"})
        actions = r.get("actions") or []
        self.assertTrue(
            any(a.get("widgetId") == "qb-ap-aging" for a in actions if isinstance(a, dict))
        )

    def test_gap_code_constant(self):
        self.assertEqual(GAP_PAYROLL_PENDING, "PAYROLL_PENDING")


if __name__ == "__main__":
    unittest.main()
