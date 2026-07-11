"""Validation gates for Moonshot HAL-said improve-fix (approve-all)."""

from __future__ import annotations

import unittest

from apex_backend import BUILD_ID, build_apex_widgets, resolve_hal_board_actions
from apex_hal_said_improve_pack import (
    auto_create_denial_tasks,
    clinical_signoff_widget,
    eob_backlog_widget,
    normalize_softdent_label,
    process_era_workflow,
    record_eob_from_era_matches,
    remember_structured,
    submit_clinical_signoff,
)


class HalSaidImproveValidationGates(unittest.TestCase):
    def test_build_id(self):
        self.assertTrue(str(BUILD_ID).startswith("hal-"))
        self.assertGreaterEqual(int(str(BUILD_ID).split("-")[1]), 10470)

    def test_denial_tasks_dry_run_no_patient_name(self):
        result = auto_create_denial_tasks(
            [
                {
                    "claimId": "CLM-99",
                    "patientName": "Jane Doe",
                    "paidAmount": 0,
                    "segment": {"status": "4", "charged": 100, "paid": 0},
                }
            ],
            dry_run=True,
        )
        self.assertTrue(result.get("ok"))
        self.assertEqual(result.get("created"), 1)
        title = result["tasks"][0]["title"]
        self.assertIn("Denial follow-up", title)
        self.assertIn("CLM-99", title)
        self.assertNotIn("Jane", title)
        self.assertNotIn("Doe", title)

    def test_era_workflow_eob_backlog(self):
        era = {
            "ok": True,
            "matches": [{"claimId": "EOB-1", "paidAmount": 10, "segment": {"status": "1"}}],
        }
        wf = process_era_workflow(era, filename="test.835")
        self.assertTrue(wf.get("ok"))
        self.assertGreaterEqual(int(wf.get("eobBacklogAdded") or 0), 0)
        # Idempotent second call should add 0 new if already recorded
        n2 = record_eob_from_era_matches(era["matches"], filename="test.835")
        self.assertEqual(n2, 0)

    def test_clinical_signoff_and_widget(self):
        r = submit_clinical_signoff({"claimId": "SIG-1", "narrativeId": "narr-1"})
        self.assertTrue(r.get("ok"))
        w = clinical_signoff_widget()
        self.assertEqual(w.get("id"), "clinical-signoff-queue")
        self.assertIn(w.get("status"), ("ok", "empty"))

    def test_eob_widget_honesty(self):
        w = eob_backlog_widget()
        self.assertEqual(w.get("id"), "eob-posting-backlog")
        self.assertTrue(w.get("emptyMessage") or w.get("items") is not None)

    def test_normalize_carrier(self):
        hit = normalize_softdent_label("METLIFE DENTAL")
        self.assertIn("matched", hit)
        self.assertIn("canonical_id", hit)

    def test_remember_structured_rejects_phi(self):
        bad = remember_structured({"fact": "Patient SSN is 123-45-6789 for follow up", "category": "payer_policy"})
        self.assertFalse(bad.get("ok"))

    def test_remember_structured_ok(self):
        ok = remember_structured(
            {
                "fact": "MetLife often downgrades composite to amalgam on posterior teeth.",
                "category": "payer_policy",
                "payerId": "nr2-metlife-dental",
            }
        )
        self.assertTrue(ok.get("ok"), ok)

    def test_hal_focus_eob_backlog(self):
        r = resolve_hal_board_actions({"query": "show eob posting backlog", "page": "financial"})
        actions = r.get("actions") or []
        self.assertTrue(any(a.get("widgetId") == "eob-posting-backlog" for a in actions))

    def test_hal_focus_clinical_signoff(self):
        r = resolve_hal_board_actions({"query": "open clinical sign-off queue", "page": "hal"})
        actions = r.get("actions") or []
        self.assertTrue(any(a.get("widgetId") == "clinical-signoff-queue" for a in actions))

    def test_pages_place_widgets(self):
        om = build_apex_widgets("office-manager")
        ids = {w.get("id") for w in om.get("widgets") or []}
        for wid in (
            "eob-posting-backlog",
            "clinical-signoff-queue",
            "payer-change-alerts",
            "policy-changelog",
            "payer-contact-admin",
            "hal-structured-remember",
        ):
            self.assertIn(wid, ids, wid)


if __name__ == "__main__":
    unittest.main()
