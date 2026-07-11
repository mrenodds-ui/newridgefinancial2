"""Phase W0 — SoftDent extended metrics views (case acceptance, aging, scheduling)."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from apex_backend import BUILD_ID, build_apex_widgets
from apex_softdent_aging_schedule_pack import assess_aging_schedule_gap, ingest_aging_schedule_into_conn
from apex_softdent_extended_pack import (
    GAP_CASE_ACCEPT_DATA_PENDING,
    build_scheduling_efficiency,
    calculate_case_acceptance,
    extended_metrics_enabled,
    extended_metrics_widgets,
)
from apex_softdent_production_pack import ingest_softdent_production_into_conn
from apex_unified_db_pack import (
    ingest_from_bundle,
    list_case_acceptance,
    list_patient_aging,
    list_scheduling_efficiency,
    open_unified,
)


def _bundle() -> dict:
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
                    {"Bucket": "0-30", "Balance": 1000, "InsPending": 100},
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
                        "ScheduledProduction": 52000,
                    }
                ]
            },
        },
        "quickbooks": {"profitAndLoss": {"rows": []}, "expenseCategories": {"rows": []}},
    }


class SoftDentExtendedW0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self._tmpdir.name) / "nr2_unified_w0.db"
        self._prev = os.environ.get("NR2_EXTENDED_METRICS")

    def tearDown(self) -> None:
        if self._prev is None:
            os.environ.pop("NR2_EXTENDED_METRICS", None)
        else:
            os.environ["NR2_EXTENDED_METRICS"] = self._prev
        try:
            self._tmpdir.cleanup()
        except Exception:
            pass

    def test_build_id(self):
        self.assertEqual(BUILD_ID, "hal-10493")

    def test_helpers_honesty(self):
        empty = calculate_case_acceptance(None, None)
        self.assertEqual(empty.get("gapCode"), GAP_CASE_ACCEPT_DATA_PENDING)
        self.assertIsNone(empty.get("acceptanceRate"))
        ok = calculate_case_acceptance(10000, 7000)
        self.assertEqual(ok.get("acceptanceRate"), 0.7)
        sched = build_scheduling_efficiency(52000, 50000)
        self.assertAlmostEqual(float(sched.get("scheduleAccuracy") or 0), 50000 / 52000, places=4)

    def test_views_after_ingest(self):
        ingest_from_bundle(_bundle(), db_path=self.db_path)
        case = list_case_acceptance(db_path=self.db_path)
        aging = list_patient_aging(db_path=self.db_path)
        sched = list_scheduling_efficiency(db_path=self.db_path)
        self.assertTrue(case)
        self.assertEqual(case[0].get("acceptanceRate"), 0.7)
        self.assertTrue(aging)
        self.assertEqual(aging[0].get("totalAr"), 1700.0)
        self.assertEqual(aging[0].get("insurancePending"), 100.0)
        self.assertTrue(sched)
        self.assertEqual(sched[0].get("scheduledProduction"), 52000.0)
        self.assertEqual(sched[0].get("actualProduction"), 50000.0)
        self.assertIsNotNone(sched[0].get("scheduleAccuracy"))

    def test_operatory_chairs_fallback(self):
        bundle = {
            "softdent": {
                "ar": {"rows": [{"Bucket": "0-30", "Balance": 50}]},
                "operatory": {
                    "operatoryChairs": [
                        {"name": "Op1", "slots": [{"time": "09:00"}, {"time": "10:00"}]},
                        {"name": "Op2", "slots": [{"time": "11:00"}]},
                    ]
                },
            }
        }
        gap = assess_aging_schedule_gap(bundle)
        self.assertFalse(gap.get("schedulingPending"))
        self.assertTrue(gap.get("fromOperatoryChairs"))
        with open_unified(path=self.db_path) as conn:
            meta = ingest_aging_schedule_into_conn(conn, bundle)
            conn.commit()
        self.assertEqual(meta.get("schedulingPeriods"), 1)
        rows = list_scheduling_efficiency(db_path=self.db_path)
        self.assertEqual(rows[0].get("totalAppointments"), 3)
        self.assertIsNone(rows[0].get("fillRate"))

    def test_widgets_present(self):
        os.environ["NR2_EXTENDED_METRICS"] = "1"
        ingest_from_bundle(_bundle(), db_path=self.db_path)
        # Widgets read default unified path; exercise pack with explicit db via helpers already.
        # Also ensure financial page builder includes W0 ids when enabled.
        out = build_apex_widgets("financial")
        ids = {w.get("id") for w in (out.get("widgets") or []) if isinstance(w, dict)}
        self.assertIn("v-case-acceptance", ids)
        self.assertIn("v-patient-aging", ids)
        self.assertIn("v-scheduling-efficiency", ids)

    def test_flag_off(self):
        os.environ["NR2_EXTENDED_METRICS"] = "0"
        self.assertFalse(extended_metrics_enabled())
        widgets = extended_metrics_widgets({})
        self.assertEqual(len(widgets), 1)
        self.assertIn("disabled", str(widgets[0].get("message") or "").lower())


if __name__ == "__main__":
    unittest.main()
