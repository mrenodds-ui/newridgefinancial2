"""Phase I3 validation — additive nr2_unified.db ingest + snapshot."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from apex_backend import build_apex_widgets, resolve_hal_board_actions
from apex_orchestrator_pack import orchestrate, orchestrator_status
from apex_unified_db_pack import (
    ingest_from_bundle,
    list_practice_health_snapshots,
    orchestrator_context_snapshot,
    unified_db_widget,
)


def _bundle() -> dict:
    return {
        "softdent": {
            "dashboard": {
                "rows": [
                    {
                        "period": "2026-07",
                        "provider": "New Ridge",
                        "production": 50000,
                        "collectionsPending": True,
                        "insurance": 0,
                        "patient": 0,
                    },
                    {
                        "period": "2026-06",
                        "provider": "New Ridge",
                        "production": 48000,
                        "collections": 41000,
                        "collectionsReported": True,
                        "insurance": 28000,
                        "patient": 13000,
                    },
                ]
            }
        },
        "quickbooks": {
            "expenseCategories": {
                "rows": [
                    {"Category": "Dental Supplies", "Amount": 3200},
                    {"Category": "Lab", "Amount": 2100},
                ]
            },
            "profitAndLoss": {"rows": [{"period": "2026-06", "NetIncome": 10000}]},
        },
        "diagnostics": {"summary": {"connected": 4, "total": 5, "missing": 1}},
    }


class UnifiedDbPhaseI3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self._tmpdir.name) / "nr2_unified_test.db"

    def tearDown(self) -> None:
        try:
            self._tmpdir.cleanup()
        except Exception:
            pass

    def test_ingest_and_snapshot(self):
        result = ingest_from_bundle(_bundle(), db_path=self.db_path)
        self.assertTrue(result.get("ok"))
        self.assertGreaterEqual(result.get("softdentPeriods"), 2)
        self.assertGreaterEqual(result.get("qbExpenseRows"), 2)

        snaps = list_practice_health_snapshots(limit=10, db_path=self.db_path)
        self.assertGreaterEqual(len(snaps), 2)
        by_period = {s["period"]: s for s in snaps}
        self.assertIn("2026-06", by_period)
        # Pending period must not invent collections
        if "2026-07" in by_period:
            self.assertIsNone(by_period["2026-07"].get("collections"))
        # Reported period has collections
        self.assertEqual(by_period["2026-06"].get("collections"), 41000)
        # QB expenses join onto period_qb (current/2026-06 depending on P&L)
        ctx = orchestrator_context_snapshot(limit=6, db_path=self.db_path)
        self.assertTrue(ctx.get("ok"))
        self.assertTrue(ctx.get("periods"))

    def test_widget(self):
        ingest_from_bundle(_bundle(), db_path=self.db_path)
        # Widget uses default path — just ensure builder returns a widget shape
        w = unified_db_widget(_bundle())
        self.assertEqual(w.get("id"), "unified-db-snapshot")
        self.assertIn(w.get("status"), ("ok", "empty"))

    def test_pages_place_widget(self):
        out = build_apex_widgets("financial")
        ids = {w.get("id") for w in (out.get("widgets") or []) if isinstance(w, dict)}
        self.assertIn("unified-db-snapshot", ids)

    def test_hal_focus(self):
        r = resolve_hal_board_actions({"query": "show unified db snapshot", "page": "hal"})
        actions = r.get("actions") or []
        self.assertTrue(any(a.get("widgetId") == "unified-db-snapshot" for a in actions))

    def test_orchestrator_status_i3(self):
        st = orchestrator_status()
        self.assertEqual(st.get("phase"), "I4")
        self.assertTrue(st.get("unifiedDb"))

    def test_classify_only_includes_unified_for_deep(self):
        # Ingest into real default path is heavy — classify_only just needs deep lane + optional ctx
        r = orchestrate(
            "Forecast collections and cross-reference SoftDent with QuickBooks",
            classify_only=True,
            force_enabled=True,
        )
        self.assertEqual(r.get("lane"), "escalate30b")
        self.assertEqual(r.get("phase"), "I4")
        # unifiedContext may be empty periods if no prior ingest — key should still exist
        self.assertIn("unifiedContext", r)


if __name__ == "__main__":
    unittest.main()
