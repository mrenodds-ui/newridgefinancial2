"""Moonshot Better Backend Widgets SHOULD (hal-10608)."""

from __future__ import annotations

import unittest
from unittest import mock

from apex_backend import BUILD_ID
from apex_better_backend_widgets_pack import (
    build_ar_main_collection_task_list,
    build_hal_action_list,
    build_narratives_ai_insight,
    build_softdent_patient_dossier,
)


class BetterBackendWidgetsShouldTests(unittest.TestCase):
    def test_build_id(self) -> None:
        self.assertEqual(BUILD_ID, "hal-10629")

    def test_hal_action_list(self) -> None:
        with mock.patch(
            "softdent_gold_era_settlement_hal10608.gold_era_settlement_status",
            return_value={"gold": {"gapCode": "OK"}, "era": {"ready": True, "fileCount": 1}},
        ):
            empty = build_hal_action_list({})
        self.assertEqual(empty["type"], "action-list")
        self.assertEqual(empty["id"], "hal-recommended-actions")
        self.assertEqual(empty["status"], "empty")

        filled = build_hal_action_list(
            {"diagnostics": {"summary": {"missing": 2, "stale": 1}}}
        )
        self.assertEqual(filled["status"], "ok")
        items = filled["data"]["items"]
        self.assertGreaterEqual(len(items), 2)
        self.assertTrue(all("label" in it for it in items))

    def test_ar_collection_task_list_empty(self) -> None:
        w = build_ar_main_collection_task_list({})
        self.assertEqual(w["type"], "collection-task-list")
        self.assertEqual(w["id"], "ar-collection-task-list")
        self.assertIn("seeds", w)
        self.assertIn("notes", w)
        # Seeds stay empty without SoftDent claims; notes may exist in local SQLite.
        self.assertEqual(w["seeds"], [])
        if not w["notes"]:
            self.assertEqual(w["status"], "empty")
        else:
            self.assertEqual(w["status"], "ok")

    def test_narratives_ai_insight(self) -> None:
        w = build_narratives_ai_insight({})
        self.assertEqual(w["type"], "ai-insight")
        self.assertEqual(w["id"], "narratives-ai-insight")
        insight = w["insight"]
        self.assertIn(insight["widget_type"], {"kpi-card", "alert-banner", "trend-chart"})
        self.assertIsInstance(insight.get("action_cta"), dict)
        self.assertIn("route", insight["action_cta"])

    def test_softdent_patient_dossier_empty(self) -> None:
        w = build_softdent_patient_dossier({})
        self.assertEqual(w["type"], "patient-dossier-card")
        self.assertEqual(w["id"], "softdent-patient-dossier")
        # SoftDent knowledge surfaced as warn + select playbook (not blank empty).
        self.assertEqual(w["status"], "warn")
        self.assertEqual(w.get("gapCode"), "NO_PATIENT_CONTEXT")
        self.assertFalse(w["data"].get("patientHash"))
        self.assertIn("patient_id", str(w.get("message") or w["data"].get("emptyMessage") or ""))


if __name__ == "__main__":
    unittest.main()
