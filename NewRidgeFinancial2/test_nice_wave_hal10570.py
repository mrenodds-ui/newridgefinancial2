"""Moonshot Better Backend Widgets NICE (hal-10576)."""

from __future__ import annotations

import unittest

from apex_backend import BUILD_ID
from apex_better_backend_widgets_pack import (
    build_ar_aging_pareto,
    build_claim_status_lanes,
    build_tax_calendar_main,
)


class NiceWaveHal10570Tests(unittest.TestCase):
    def test_build_id(self) -> None:
        self.assertEqual(BUILD_ID, "hal-10576")

    def test_aging_pareto_empty(self) -> None:
        w = build_ar_aging_pareto({"ar": {}})
        self.assertEqual(w["type"], "pareto-chart")
        self.assertEqual(w["status"], "empty")
        self.assertEqual(w["data"]["bars"], [])
        self.assertEqual(w["data"]["threshold"], 80)

    def test_aging_pareto_cumulative_100(self) -> None:
        w = build_ar_aging_pareto(
            {
                "ar": {
                    "aging_buckets": [
                        {"bucket": "120+", "amount": 8000, "count": 2},
                        {"bucket": "Current", "amount": 2000, "count": 5},
                    ]
                }
            }
        )
        self.assertEqual(w["status"], "ok")
        bars = w["data"]["bars"]
        self.assertEqual(bars[0]["code"], "120+")
        self.assertEqual(bars[0]["pct"], 80.0)
        self.assertEqual(w["data"]["cumulative"][-1], 100.0)

    def test_tax_calendar_main_root_items(self) -> None:
        w = build_tax_calendar_main({})
        self.assertEqual(w["type"], "tax-calendar")
        self.assertIn("items", w)  # Must be on root, not data.items
        self.assertIn(w["status"], {"ok", "empty"})
        if w["items"]:
            self.assertIn("label", w["items"][0])
            self.assertIn("due", w["items"][0])
            self.assertIn("logged", w["items"][0])
            self.assertIs(w["items"][0]["logged"], False)

    def test_claim_lanes_segments(self) -> None:
        w = build_claim_status_lanes(
            {
                "claims": {
                    "claims": [
                        {"payer": "Delta", "status": "Paid"},
                        {"payer": "Delta", "status": "Pending"},
                        {"payer": "Aetna", "status": "Denied"},
                    ]
                }
            }
        )
        self.assertEqual(w["type"], "timeline-lanes")
        lanes = w["data"]["lanes"]
        delta = next(l for l in lanes if l["code"] == "Delta")
        self.assertEqual(delta["total"], 2)
        segs = {s["bucket"]: s for s in delta["segments"]}
        self.assertEqual(segs["Paid"]["color"], "green")
        self.assertEqual(segs["Pending"]["color"], "amber")


if __name__ == "__main__":
    unittest.main()
