"""Moonshot ERA remittance discovery scanner (hal-10576)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from apex_backend import BUILD_ID
from apex_era835_pack import discover_era_candidates
from apex_softdent_hardening_pack import collections_gap_widget
from nr2_browser_security import system_status_path
from nr2_hal_gateway import try_local_policy_reply
from softdent_practice_exports import discover_era_candidates as export_discover


def _bundle_register_ins_plan_zero() -> dict:
    return {
        "softdent": {
            "dashboard": {
                "rows": [
                    {
                        "period": "2026-07",
                        "year_month": "2026-07",
                        "production": 44735.0,
                        "collections": 30626.42,
                        "collectionsReported": True,
                        "collectionsPending": False,
                        "collectionsFormatRequired": True,
                        "insurance": 0.0,
                        "patient": 0.0,
                    }
                ]
            }
        }
    }


class EraRemittanceDiscoveryHal10575Tests(unittest.TestCase):
    def test_build_id(self) -> None:
        self.assertEqual(BUILD_ID, "hal-10576")

    def test_discover_path_is_system_telemetry(self) -> None:
        self.assertTrue(system_status_path("/api/apex/hal/era-inbox/discover"))

    def test_discover_finds_835_outside_inbox(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            edi = root / "clearinghouse"
            edi.mkdir()
            sample = edi / "payer_remit.835"
            sample.write_text(
                "ISA*00*          *00*          *ZZ*PAYER         *ZZ*PROVIDER      "
                "*240101*1200*^*00501*000000001*0*P*:~"
                "GS*HP*PAYER*PROVIDER*20240101*1200*1*X*005010X221A1~"
                "ST*835*0001~",
                encoding="utf-8",
            )
            junk = edi / "notes.txt"
            junk.write_text("hello world", encoding="utf-8")
            out = discover_era_candidates(roots=[root], limit=10, max_depth=3)
            self.assertTrue(out.get("ok"))
            self.assertTrue(out.get("readOnly"))
            self.assertFalse(out.get("writeBack"))
            self.assertEqual(out.get("honesty"), "empty_not_zero")
            self.assertGreaterEqual(int(out.get("candidateCount") or 0), 1)
            paths = [c.get("path") for c in (out.get("candidates") or [])]
            self.assertTrue(any(str(sample) == p for p in paths))
            self.assertIn("candidate", str(out.get("chipStatus") or ""))

    def test_discover_empty_honesty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "empty_dir").mkdir()
            out = discover_era_candidates(roots=[root], limit=5)
            self.assertTrue(out.get("ok"))
            self.assertTrue(out.get("empty"))
            self.assertEqual(out.get("candidateCount"), 0)
            self.assertEqual(out.get("chipStatus"), "none_found")
            self.assertIn("procurement", str(out.get("chipLabel") or "").lower())

    def test_skips_synthetic_fixture_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            syn = root / "synthetic.835"
            syn.write_text("ST*835*0001~", encoding="utf-8")
            out = discover_era_candidates(roots=[root], limit=5)
            self.assertEqual(out.get("candidateCount"), 0)

    def test_gap_widget_exposes_discover_action(self) -> None:
        w = collections_gap_widget(_bundle_register_ins_plan_zero())
        self.assertEqual(w.get("eraDiscoverUrl"), "/api/apex/hal/era-inbox/discover")
        self.assertEqual(w.get("eraDiscoverLabel"), "Scan for ERA Files")
        labels = " ".join(str(c.get("label") or "") for c in (w.get("halChips") or []))
        self.assertIn("Scan for ERA", labels)

    def test_export_wrapper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = export_discover(roots=[Path(tmp)], limit=3)
            self.assertTrue(out.get("ok"))
            self.assertEqual(out.get("mode"), "discovery")

    def test_hal_policy_discover(self) -> None:
        with mock.patch(
            "apex_era835_pack.discover_era_candidates",
            return_value={
                "candidateCount": 0,
                "chipLabel": "No local ERA files detected; procurement required",
                "scannedRoots": [r"C:\SoftDentFinancialExports"],
                "candidates": [],
            },
        ):
            reply = try_local_policy_reply("scan for ERA remittance files on disk")
        self.assertIsNotNone(reply)
        assert reply is not None
        self.assertEqual(reply.get("intent"), "policy:era-discover")
        self.assertIn("procurement", str(reply.get("text") or "").lower())


if __name__ == "__main__":
    unittest.main()
