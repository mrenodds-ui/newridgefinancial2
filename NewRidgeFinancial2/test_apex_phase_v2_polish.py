"""Phase V2 validation — 30B explain cache + mobile polish assets."""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from apex_backend import BUILD_ID
from apex_reconciliation_pack import (
    explain_cache_enabled,
    explain_cache_stats,
    explain_variance,
    invalidate_explain_cache,
    variance_delta_hash,
)


ROOT = Path(__file__).resolve().parent
SITE = ROOT / "site"


class PhaseV2PolishTests(unittest.TestCase):
    def setUp(self) -> None:
        self._prev_cache = os.environ.get("NR2_EXPLAIN_CACHE")
        invalidate_explain_cache(reason="test_setup")

    def tearDown(self) -> None:
        if self._prev_cache is None:
            os.environ.pop("NR2_EXPLAIN_CACHE", None)
        else:
            os.environ["NR2_EXPLAIN_CACHE"] = self._prev_cache
        invalidate_explain_cache(reason="test_teardown")

    def test_build_id(self):
        self.assertEqual(BUILD_ID, "hal-10490")

    def test_explain_cache_default_off(self):
        os.environ.pop("NR2_EXPLAIN_CACHE", None)
        self.assertFalse(explain_cache_enabled())

    def test_delta_hash_stable(self):
        finding = {
            "period": "2026-06",
            "kind": "production_vs_payroll",
            "reasons": ["production_mom_variance"],
            "deltas": {"productionDelta": 10000.0},
            "thresholds": {"pct": 0.05, "abs": 500.0},
            "production": 60000.0,
            "payroll": 15000.0,
        }
        a = variance_delta_hash(finding)
        b = variance_delta_hash(dict(finding))
        self.assertEqual(a, b)
        self.assertEqual(len(a), 24)

    def test_cache_hit_skips_orchestrator(self):
        os.environ["NR2_EXPLAIN_CACHE"] = "1"
        invalidate_explain_cache(reason="before_hit_test")
        finding = {
            "period": "2026-06",
            "kind": "production_vs_payroll",
            "reasons": ["production_mom_variance"],
            "deltas": {"productionDelta": 10000.0},
            "thresholds": {"pct": 0.05, "abs": 500.0},
            "production": 60000.0,
            "payroll": 15000.0,
        }
        calls = {"n": 0}

        def fake_orchestrate(*_a, **_k):
            calls["n"] += 1
            return {"ok": True, "lane": "escalate30b", "insightWidget": {"id": "x"}}

        with patch("apex_orchestrator_pack.orchestrate", side_effect=fake_orchestrate), patch(
            "apex_orchestrator_pack.orchestrator_enabled", return_value=True
        ):
            first = explain_variance(finding, classify_only=True, force_orchestrator=True)
            second = explain_variance(finding, classify_only=True, force_orchestrator=True)

        self.assertTrue(first.get("ok"))
        self.assertFalse(first.get("cacheHit"))
        self.assertTrue(second.get("cacheHit"))
        self.assertEqual(calls["n"], 1)
        stats = explain_cache_stats()
        self.assertEqual(stats.get("hits"), 1)
        self.assertEqual(stats.get("misses"), 1)
        self.assertEqual(stats.get("size"), 1)

    def test_invalidate_on_import_clears_hits(self):
        os.environ["NR2_EXPLAIN_CACHE"] = "1"
        finding = {
            "period": "2026-06",
            "kind": "production_vs_payroll",
            "reasons": ["production_mom_variance"],
            "deltas": {"productionDelta": 5000.0},
            "thresholds": {"pct": 0.05, "abs": 500.0},
        }
        with patch(
            "apex_orchestrator_pack.orchestrate",
            return_value={"ok": True, "lane": "escalate30b"},
        ), patch("apex_orchestrator_pack.orchestrator_enabled", return_value=True):
            explain_variance(finding, classify_only=True, force_orchestrator=True)
            self.assertGreaterEqual(explain_cache_stats().get("size") or 0, 1)
            out = invalidate_explain_cache(reason="import")
            self.assertTrue(out.get("ok"))
            self.assertEqual(out.get("size"), 0)
            self.assertEqual(explain_cache_stats().get("size"), 0)
            explain_variance(finding, classify_only=True, force_orchestrator=True)
        # After invalidate, second explain is a miss then store — size 1 again
        self.assertEqual(explain_cache_stats().get("size"), 1)

    def test_cache_disabled_never_stores(self):
        os.environ["NR2_EXPLAIN_CACHE"] = "0"
        invalidate_explain_cache(reason="disabled_test")
        finding = {
            "period": "2026-06",
            "kind": "collection_vs_ap",
            "reasons": ["collections_mom_variance"],
            "deltas": {"collectionsDelta": 2000.0},
        }
        with patch(
            "apex_orchestrator_pack.orchestrate",
            return_value={"ok": True, "lane": "escalate30b"},
        ), patch("apex_orchestrator_pack.orchestrator_enabled", return_value=True):
            a = explain_variance(finding, classify_only=True, force_orchestrator=True)
            b = explain_variance(finding, classify_only=True, force_orchestrator=True)
        self.assertFalse(a.get("cacheHit"))
        self.assertFalse(b.get("cacheHit"))
        self.assertEqual(explain_cache_stats().get("size"), 0)

    def test_mobile_polish_css_present(self):
        css = (SITE / "apex-mobile-polish.css").read_text(encoding="utf-8")
        self.assertIn("@media (max-width: 768px)", css)
        self.assertIn(".apex-mosaic--u3", css)
        self.assertIn(".hal-insight-banner", css)
        html = (SITE / "index.html").read_text(encoding="utf-8")
        self.assertIn("apex-mobile-polish.css?v=hal-10490", html)
        self.assertIn('data-apex-version="hal-10490"', html)


if __name__ == "__main__":
    unittest.main()
