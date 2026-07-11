"""Validation gates for Moonshot missing-widgets coding consult (W-01..W-10)."""

from __future__ import annotations

import unittest

from apex_backend import BUILD_ID, build_apex_widgets, resolve_hal_board_actions
from apex_missing_widgets_pack import (
    build_cash_bridge,
    build_denial_pareto,
    build_expense_treemap,
    build_operatory_board,
    build_preauth_lanes,
    build_procedure_scatter,
    build_recall_gauge,
    build_treatment_pipeline,
    build_unapplied_float,
    build_verification_matrix,
)


class MissingWidgetsValidationGates(unittest.TestCase):
    def test_build_id(self):
        self.assertTrue(str(BUILD_ID).startswith("hal-"))

    def test_gate1_empty_honesty(self):
        builders = [
            build_expense_treemap,
            build_procedure_scatter,
            build_denial_pareto,
            build_treatment_pipeline,
            build_preauth_lanes,
            build_unapplied_float,
            build_cash_bridge,
            build_verification_matrix,
            build_operatory_board,
            build_recall_gauge,
        ]
        for fn in builders:
            w = fn({})
            self.assertEqual(w.get("status"), "empty", w.get("id"))
            self.assertIn("data", w)
            self.assertTrue(w["data"].get("emptyMessage"))
            # Never invent dollars in empty payloads
            data = w["data"]
            if "total" in data:
                self.assertTrue(data["total"] is None or data["total"] == 0 or data.get("count") == 0)

    def test_gate1_phi_hashes_only(self):
        w = build_unapplied_float(
            {
                "softdent": {
                    "unapplied_payments": [
                        {"patient_name": "Jane Doe", "amount": 12.5, "Unapplied": True},
                    ]
                }
            }
        )
        if w.get("status") == "ok":
            for c in w["data"]["credits"]:
                self.assertTrue(str(c["patientHash"]).endswith("—"))
                self.assertNotIn("Jane", c["patientHash"])
                self.assertNotIn("Doe", c["patientHash"])

    def test_hal_operatory_board_not_trend(self):
        r = resolve_hal_board_actions({"query": "open operatory board", "page": "financial"})
        actions = r.get("actions") or []
        self.assertTrue(any(a.get("widgetId") == "operatory-util-board" for a in actions))
        self.assertFalse(any(a.get("widgetId") == "operatory-util-trend" for a in actions))

    def test_hal_operatory_util_trend_still_works(self):
        r = resolve_hal_board_actions({"query": "show operatory util trend", "page": "financial"})
        actions = r.get("actions") or []
        self.assertTrue(any(a.get("widgetId") == "operatory-util-trend" for a in actions))

    def test_gate1_hal_voice(self):
        r = resolve_hal_board_actions({"query": "show denial pareto", "page": "financial"})
        actions = r.get("actions") or []
        self.assertTrue(any(a.get("widgetId") == "denial-pareto" for a in actions))

    def test_gate2_cash_bridge_grays_incomplete(self):
        w = build_cash_bridge({"quickbooks": {"cash_balance": 1000}})
        self.assertEqual(w.get("status"), "empty")
        self.assertEqual(w["data"].get("emptyMessage"), "Cash projection unavailable")

    def test_gate2_scatter_null_cost(self):
        w = build_procedure_scatter(
            {
                "softdent": {
                    "procedures": {
                        "rows": [{"code": "D1110", "Fee": 50}],  # no collection
                    }
                }
            }
        )
        # Fee-only without collection stays empty per honesty
        self.assertEqual(w.get("status"), "empty")

    def test_pages_place_widgets(self):
        expected = {
            "financial": [
                "expense-treemap",
                "procedure-profitability-scatter",
                "treatment-conversion-pipeline",
                "cash-flow-bridge",
            ],
            "quickbooks": ["expense-treemap"],
            "ar": ["unapplied-credit-float"],
            "claims": ["denial-pareto", "preauth-aging-lanes", "verification-matrix"],
            "office-manager": [
                "operatory-util-board",
                "recall-gauge",
                "treatment-conversion-pipeline",
                "verification-matrix",
            ],
        }
        for page, ids in expected.items():
            out = build_apex_widgets(page)
            have = {w.get("id") for w in (out.get("widgets") or []) if isinstance(w, dict)}
            for wid in ids:
                self.assertIn(wid, have, f"{page} missing {wid}")


if __name__ == "__main__":
    unittest.main()
