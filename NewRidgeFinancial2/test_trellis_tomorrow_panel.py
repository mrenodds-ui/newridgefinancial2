"""Tests for PHI-safe tomorrow Trellis insurance OM snapshot."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from nr2_trellis_nightly import eligibility_report_html, eligibility_report_snapshot, tomorrow_insurance_snapshot


class TomorrowInsuranceSnapshotTests(unittest.TestCase):
    def test_snapshot_hash_only_no_money(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = {
                "date": "2026-07-20",
                "builtAt": "2026-07-16T12:00:00+00:00",
                "total": 1,
                "ready": 1,
                "patients": [
                    {
                        "patient_id": "577226",
                        "patient_name": "Alexis Aguilera",
                        "demo": {"first": "Alexis", "last": "Aguilera"},
                        "insurance": {"insurance_name": "METLIFE DENTAL"},
                        "ready": True,
                        "skip_reason": None,
                    }
                ],
            }
            results = {
                "date": "2026-07-20",
                "updatedAt": "2026-07-16T13:00:00+00:00",
                "results": [
                    {
                        "patient_id": "577226",
                        "patient_name": "Alexis Aguilera",
                        "status": "Eligible",
                        "carrier": "MetLife",
                        "deductibleRemaining": 0.0,
                        "maxInNetworkRemaining": 0.0,
                    }
                ],
            }
            (root / "tomorrow_trellis_add_worklist_2026-07-20.json").write_text(
                json.dumps(work), encoding="utf-8"
            )
            (root / "tomorrow_trellis_verify_results_2026-07-20.json").write_text(
                json.dumps(results), encoding="utf-8"
            )
            snap = tomorrow_insurance_snapshot(target_date="2026-07-20", out_dir=root)
            self.assertTrue(snap.get("ok"))
            self.assertTrue(snap.get("hasData"))
            self.assertTrue(snap.get("emptyNotZero"))
            rows = snap.get("patients") or []
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row.get("initials"), "AA—")
            self.assertEqual(row.get("verifyStatus"), "Eligible")
            self.assertNotIn("patient_name", row)
            self.assertNotIn("deductibleRemaining", row)
            blob = json.dumps(snap)
            self.assertNotIn("Aguilera", blob)
            self.assertNotIn("$0", blob)

    def test_eligibility_report_snapshot_and_html(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing = eligibility_report_snapshot(target_date="2026-07-20", out_dir=root)
            self.assertTrue(missing.get("ok"))
            self.assertFalse(missing.get("hasReport"))
            html_path = root / "trellis_eligibility_report_2026-07-20.html"
            html_path.write_text(
                "<!DOCTYPE html><html><body><h1>Trellis</h1><p>empty ≠ $0</p></body></html>",
                encoding="utf-8",
            )
            results = {
                "results": [
                    {
                        "benefits": {
                            "scrapeOk": True,
                            "deductibleRemaining": None,
                            "categories": {"preventive": "100%"},
                        }
                    },
                    {"benefits": {"scrapeOk": False}},
                    {"verifyStatus": "Eligible"},
                ]
            }
            (root / "tomorrow_trellis_verify_results_2026-07-20.json").write_text(
                json.dumps(results), encoding="utf-8"
            )
            meta = eligibility_report_snapshot(target_date="2026-07-20", out_dir=root)
            self.assertTrue(meta.get("hasReport"))
            self.assertEqual(meta.get("patients"), 3)
            self.assertEqual(meta.get("withBenefits"), 1)
            self.assertEqual(meta.get("statusOnly"), 2)
            self.assertIn("eligibility-report.html", str(meta.get("reportUrl") or ""))
            doc = eligibility_report_html(target_date="2026-07-20", out_dir=root)
            self.assertTrue(doc.get("hasReport"))
            self.assertIn("<h1>Trellis</h1>", str(doc.get("html") or ""))


if __name__ == "__main__":
    unittest.main()
