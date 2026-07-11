"""Phase I4 — MUST-wave integration gates (I0–I3 contracts; no Ollama required)."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from apex_backend import BUILD_ID, build_apex_widgets, resolve_hal_board_actions
from apex_orchestrator_pack import classify_intent, orchestrate, orchestrator_enabled, orchestrator_status
from apex_softdent_hardening_pack import GAP_COLLECTIONS_PENDING, assess_collections_gap
from apex_structured_insight_pack import validate_insight
from apex_unified_db_pack import ingest_from_bundle, list_practice_health_snapshots, unified_db_path


GOOD_KPI = {
    "widget_type": "kpi-card",
    "title": "Production snapshot",
    "data": {"value": 12000.5, "unit": "dollars", "trend_direction": "up", "trend_percent": 3.2},
    "source_refs": ["softdent:register:2026-07-11"],
    "confidence": "high",
    "explanation": "From SoftDent register import.",
}


class AiPmMustWaveI4Gates(unittest.TestCase):
    def test_build_id_i4(self):
        self.assertEqual(BUILD_ID, "hal-10490")

    def test_flag_still_default_on(self):
        prev = os.environ.pop("NR2_AI_ORCHESTRATOR", None)
        try:
            self.assertTrue(orchestrator_enabled())
        finally:
            if prev is not None:
                os.environ["NR2_AI_ORCHESTRATOR"] = prev

    def test_orchestrator_status_must_wave_complete(self):
        st = orchestrator_status()
        self.assertTrue(st.get("ok"))
        self.assertEqual(st.get("phase"), "S3")
        self.assertEqual(st.get("flag"), "NR2_AI_ORCHESTRATOR")
        self.assertTrue(st.get("structuredInsights"))
        self.assertTrue(st.get("unifiedDb"))
        self.assertTrue(st.get("mustWaveComplete"))
        self.assertTrue(st.get("shouldWaveComplete"))
        self.assertIn("chat8b", st.get("lanes") or [])
        self.assertIn("escalate30b", st.get("lanes") or [])

    def test_i0_i1_classify_and_structured_pipeline(self):
        deep = classify_intent("Forecast next quarter and cross-reference SoftDent with QuickBooks")
        self.assertEqual(deep.get("lane"), "escalate30b")
        result = orchestrate(
            "Summarize import health as a kpi card insight",
            classify_only=True,
            force_enabled=True,
            require_structured=True,
        )
        self.assertTrue(result.get("ok"))
        self.assertTrue(result.get("requireStructured"))
        self.assertEqual(result.get("phase"), "S3")

    def test_i1_schema_files_present(self):
        root = Path(__file__).resolve().parent / "data" / "insight_schemas"
        for name in ("kpi-card.json", "trend-chart.json", "alert-banner.json"):
            self.assertTrue((root / name).is_file(), name)

    def test_i1_phi_rejected(self):
        bad = dict(GOOD_KPI)
        bad["explanation"] = "Patient SSN 123-45-6789"
        r = validate_insight(bad)
        self.assertFalse(r.get("ok"))
        self.assertIn("PHI", str(r.get("error") or ""))

    def test_i2_collections_pending_honesty(self):
        gap = assess_collections_gap(
            {
                "softdent": {
                    "dashboard": {
                        "rows": [
                            {
                                "period": "2026-06",
                                "production": 100000,
                                "collectionsPending": True,
                            }
                        ]
                    }
                }
            }
        )
        self.assertEqual(gap.get("gapCode"), GAP_COLLECTIONS_PENDING)
        # Empty/pending must not be treated as invented $0 collections for display honesty
        self.assertTrue(gap.get("collectionsPending") or gap.get("gapCode") == GAP_COLLECTIONS_PENDING)

    def test_i3_unified_ingest_roundtrip(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            db = Path(td) / "nr2_unified_i4.db"
            bundle = {
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
                    "expenseCategories": {
                        "rows": [{"category": "Supplies", "amount": 1200, "period": "2026-06"}]
                    }
                },
            }
            got = ingest_from_bundle(bundle, db_path=db)
            self.assertTrue(got.get("ok"))
            self.assertGreaterEqual(int(got.get("softdentPeriods") or 0), 1)
            snaps = list_practice_health_snapshots(limit=3, db_path=db)
            self.assertTrue(snaps)
            self.assertEqual(snaps[0].get("period"), "2026-06")
            self.assertIsNotNone(snaps[0].get("collections"))

    def test_widgets_and_board_actions_wired(self):
        page_widgets = {
            "hal": "hal-ai-insight",
            "softdent": "softdent-collections-gap",
            "financial": "unified-db-snapshot",
        }
        for page, wid in page_widgets.items():
            out = build_apex_widgets(page)
            ids = {w.get("id") for w in (out.get("widgets") or []) if isinstance(w, dict)}
            self.assertIn(wid, ids, f"{page} missing {wid}")

        for phrase, wid in (
            ("show ai insight widget", "hal-ai-insight"),
            ("why are collections empty", "softdent-collections-gap"),
            ("show unified db snapshot", "unified-db-snapshot"),
        ):
            r = resolve_hal_board_actions({"query": phrase, "page": "hal"})
            actions = r.get("actions") or []
            self.assertTrue(
                any(a.get("widgetId") == wid for a in actions if isinstance(a, dict)),
                f"{phrase} → {wid}",
            )

    def test_unified_db_path_is_additive(self):
        p = unified_db_path()
        self.assertEqual(p.name, "nr2_unified.db")
        self.assertNotEqual(p.name, "nr2_local.sqlite3")


if __name__ == "__main__":
    unittest.main()
