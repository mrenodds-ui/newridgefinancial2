"""Moonshot fix-all page inspect applied packages — AR CSV + schema + patient context."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest import mock

from apex_backend import BUILD_ID
from apex_better_backend_widgets_pack import build_hal_action_list, build_softdent_patient_dossier
from import_sync import _build_ar_rows_from_account_aging_csv


class FixAllPageInspectAppliedTests(unittest.TestCase):
    def test_build_id_and_site_manifest_aligned(self) -> None:
        self.assertEqual(BUILD_ID, "hal-10608")
        site = Path(__file__).resolve().parent / "site" / "nr2-build.json"
        root = Path(__file__).resolve().parent / "nr2-build.json"
        for path in (site, root):
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data.get("schemaVersion"), "hal-10608")
            self.assertEqual(data.get("BUILD_ID"), "hal-10608")
            self.assertEqual(data.get("assetVersion"), "hal-10608")

    def test_account_aging_csv_maps_to_ar_rows(self) -> None:
        rows = _build_ar_rows_from_account_aging_csv()
        # Live SoftDentReportExports may be present; if so, expect non-empty honest totals.
        if rows:
            self.assertTrue(any(r.get("Balance") is not None for r in rows))
            self.assertTrue(any(str(r.get("Bucket") or "") for r in rows))

    def test_dossier_empty_gap_code(self) -> None:
        w = build_softdent_patient_dossier({})
        self.assertEqual(w.get("status"), "empty")
        self.assertEqual(w.get("gapCode"), "NO_PATIENT_CONTEXT")

    def test_hal_actions_include_gold_or_stale(self) -> None:
        with mock.patch(
            "softdent_gold_era_settlement_hal10608.gold_era_settlement_status",
            return_value={
                "gold": {"gapCode": "GOLD_CSV_MISSING"},
                "era": {"ready": False, "fileCount": 0},
            },
        ):
            w = build_hal_action_list({"diagnostics": {"summary": {"missing": 0, "stale": 1}}})
        self.assertEqual(w.get("status"), "ok")
        ids = {it.get("id") for it in (w.get("data") or {}).get("items") or []}
        self.assertIn("hal-act-gold-csv", ids)
        self.assertIn("hal-act-era835", ids)
        self.assertIn("hal-act-stale-imports", ids)


if __name__ == "__main__":
    unittest.main()
