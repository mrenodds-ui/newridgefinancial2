"""Validation for Moonshot OM tx/claims/schedule apply (hal-10494)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from apex_backend import BUILD_ID, build_apex_widgets
from apex_missing_widgets_pack import (
    build_claims_needing_narrative,
    build_operatory_board,
    build_provider_utilization_trend,
    build_recall_gauge,
)
from nr2_softdent_daily import (
    _hash_patient_id,
    appointments_today_snapshot,
    provider_utilization_last_7d,
)


class OmTxClaimsScheduleGates(unittest.TestCase):
    def test_build_id(self) -> None:
        self.assertEqual(BUILD_ID, "hal-10495")

    def test_operatory_board_empty_honest(self) -> None:
        w = build_operatory_board({})
        self.assertEqual(w.get("status"), "empty")
        self.assertTrue(w["data"].get("emptyMessage"))

    def test_operatory_board_live_priority(self) -> None:
        live = {
            "hasData": True,
            "date": "2026-07-11",
            "count": 1,
            "source": "sd_appointments",
            "operatories": [
                {
                    "name": "Dr A",
                    "slots": [{"time": "09:00", "status": "booked", "patientHash": "AB12"}],
                }
            ],
        }
        w = build_operatory_board({}, live_schedule=live)
        self.assertEqual(w.get("status"), "ok")
        self.assertEqual(w["data"]["operatories"][0]["slots"][0]["patientHash"], "AB12")
        self.assertNotIn("Jane", str(w["data"]))

    def test_patient_hash_phi_safe(self) -> None:
        h = _hash_patient_id("patient-12345")
        self.assertEqual(len(h), 4)
        self.assertNotIn("patient", h.lower())

    def test_claims_narrative_queue_empty(self) -> None:
        w = build_claims_needing_narrative({})
        self.assertEqual(w.get("status"), "empty")
        self.assertTrue(w["data"].get("emptyMessage"))

    def test_claims_narrative_queue_from_status(self) -> None:
        w = build_claims_needing_narrative(
            {
                "softdent": {
                    "claims": [
                        {
                            "ClaimId": "C1",
                            "Payer": "Delta",
                            "ClaimStatus": "Pending Review",
                            "ClaimAmount": "120.00",
                        }
                    ]
                }
            }
        )
        self.assertEqual(w.get("status"), "ok")
        self.assertEqual(w["data"]["items"][0]["id"], "C1")
        self.assertEqual(w["data"]["items"][0]["amount"], 120.0)

    def test_recall_booking_hint(self) -> None:
        w = build_recall_gauge(
            {"softdent": {"recall_stats": {"due_count": 10, "scheduled_count": 4, "contacted_count": 2}}}
        )
        self.assertEqual(w.get("status"), "ok")
        self.assertIn("unscheduled", str(w["data"].get("bookingHint") or "").lower())

    def test_provider_util_empty(self) -> None:
        w = build_provider_utilization_trend({"hasData": False, "providers": []})
        self.assertEqual(w.get("status"), "empty")

    def test_appointments_today_no_db(self) -> None:
        # With no SD sqlite, returns honest empty (does not invent appointments).
        payload = appointments_today_snapshot(target_date="2099-01-01")
        self.assertIn("hasData", payload)
        self.assertIn("operatories", payload)
        self.assertIsInstance(payload["operatories"], list)

    def test_om_page_includes_new_widgets(self) -> None:
        payload = build_apex_widgets("office-manager")
        widgets = payload.get("widgets") if isinstance(payload, dict) else []
        ids = {
            str(w.get("id") or "")
            for w in (widgets or [])
            if isinstance(w, dict)
        }
        self.assertIn("operatory-util-board", ids)
        self.assertIn("claims-narrative-queue", ids)
        self.assertIn("provider-util-7d", ids)


if __name__ == "__main__":
    unittest.main()
