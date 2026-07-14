"""hal-10614 — SoftDent-facing widgets must not crash/blank when SoftDent data exists."""

from __future__ import annotations

import unittest

from apex_backend import _widget_has_data
from apex_reconciliation_pack import _normalize_period, _prior_period, reconciliation_widget
from softdent_outstanding_claims_bridge import outstanding_claims_bridge_widget


class SoftDentWidgetFillHal10614Tests(unittest.TestCase):
    def test_normalize_curr_period(self) -> None:
        n = _normalize_period("curr")
        self.assertRegex(n, r"^\d{4}-\d{2}$")
        self.assertEqual(_prior_period("current")[5:7], "06" if n.endswith("-07") else _prior_period(n)[5:7])
        p = _prior_period("curr")
        self.assertRegex(p, r"^\d{4}-\d{2}$")
        self.assertNotEqual(p, n)

    def test_reconciliation_widget_survives_curr_rows(self) -> None:
        w = reconciliation_widget()
        self.assertEqual(w.get("id"), "reconciliation-status")
        self.assertNotEqual(w.get("status"), "error")
        # Must not raise; status empty only when truly disabled/pending without rows
        self.assertIn(w.get("status"), {"ok", "warn", "empty"})

    def test_claims_bridge_warns_with_data_not_blank(self) -> None:
        w = outstanding_claims_bridge_widget()
        self.assertEqual(w.get("id"), "softdent-outstanding-claims-bridge")
        if w.get("status") == "warn":
            self.assertTrue(_widget_has_data(w))
            self.assertIn("AR", str(w.get("message") or ""))

    def test_warn_status_counts_as_data(self) -> None:
        self.assertTrue(
            _widget_has_data(
                {
                    "id": "x",
                    "type": "status",
                    "status": "warn",
                    "message": "Regular Collections: Complete ($1.00)",
                }
            )
        )

    def test_gold_pipeline_warns_with_pull_playbook(self) -> None:
        from softdent_gold_payment_pipeline import gold_payment_pipeline_widget

        w = gold_payment_pipeline_widget()
        self.assertEqual(w.get("id"), "softdent-gold-payment-pipeline")
        if int(w.get("paymentLines") or 0) <= 0:
            self.assertEqual(w.get("status"), "warn")
            self.assertTrue(_widget_has_data(w))
            self.assertIn("SoftDent", str(w.get("message") or ""))

    def test_collections_gap_warns_with_regular_dollars(self) -> None:
        from apex_softdent_hardening_pack import assess_collections_gap, collections_gap_widget
        from import_loader import load_import_bundle

        b = load_import_bundle()
        g = assess_collections_gap(b)
        w = collections_gap_widget(b)
        self.assertEqual(w.get("id"), "softdent-collections-gap")
        reg = g.get("regularCollections")
        if reg is not None and float(reg or 0) > 0:
            self.assertEqual(w.get("status"), "warn")
            self.assertTrue(_widget_has_data(w))


if __name__ == "__main__":
    unittest.main()
