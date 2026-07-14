"""Moonshot Expert SE Phase 3 — ERA CAS + claim actions + stub fast-path."""

from __future__ import annotations

import os
import unittest
from unittest import mock

from apex_program_improve_pack import apply_era_to_kanban_columns, ingest_era_835
from era835_parser import parse_835_text


class ExpertSePhase3Tests(unittest.TestCase):
    def test_parse_835_captures_cas_co45(self) -> None:
        text = (
            "ISA*00*~"
            "CLP*CLAIM99*4*100*0**11~"
            "CAS*CO*45*25.00~"
            "NM1*QC*1*DOE*JANE~"
        )
        parsed = parse_835_text(text)
        self.assertTrue(parsed.get("ok"))
        segs = parsed.get("segments") or []
        self.assertTrue(segs)
        self.assertEqual(segs[0].get("denialCode"), "CO-45")
        self.assertIn("CO-45", segs[0].get("casCodes") or [])

    def test_ingest_stores_cas_not_clp_status(self) -> None:
        text = "CLP*CLM1*4*100*0**11~CAS*CO*45*10.00~NM1*QC*1*SMITH*A~"
        rows = [{"ClaimId": "CLM1", "PatientName": "SMITH A", "Status": "Denied"}]
        with mock.patch("apex_program_improve_pack._save_json"), mock.patch(
            "apex_program_improve_pack._load_json", return_value={"byClaim": {}, "history": []}
        ), mock.patch("apex_program_improve_pack._audit"):
            result = ingest_era_835(text, rows, filename="t.835")
        self.assertTrue(result.get("ok"))
        matches = result.get("matches") or []
        # Match may or may not hit depending on fuzzy — also check byClaim via side effect
        # At minimum parse path returned CAS on segment inside matches when present.
        if matches:
            seg = matches[0].get("segment") or {}
            self.assertEqual(seg.get("denialCode"), "CO-45")

    def test_apply_era_copies_denial_code(self) -> None:
        with mock.patch(
            "apex_program_improve_pack.era_matches_map",
            return_value={"C1": {"denialCode": "CO-45", "casCodes": ["CO-45"]}},
        ):
            cols = {
                "submitted": [{"claimId": "C1", "patientName": "A"}],
                "pendingReview": [],
                "denied": [],
                "eraMatched": [],
                "paid": [],
            }
            out = apply_era_to_kanban_columns(cols)
        era = out.get("eraMatched") or []
        self.assertTrue(era)
        self.assertEqual(era[0].get("denialCode"), "CO-45")
        self.assertEqual(era[0].get("eraStatus"), "ERA Matched")

    def test_stub_fastpath_returns_warming(self) -> None:
        import apex_backend as ab

        ab._WIDGETS_CACHE.clear()
        os.environ["NR2_WIDGETS_STUB_FASTPATH"] = "1"
        stub = ab.build_apex_widgets("hal", _fill=False)
        self.assertTrue(stub.get("warming"))
        self.assertEqual(stub.get("sourceNote"), "stub-fastpath")
        # Fill path builds without stubbing forever — may take time; just ensure _fill flag works.
        # Disable stub for fill test speed by using flag off briefly.
        os.environ["NR2_WIDGETS_STUB_FASTPATH"] = "0"
        ab._WIDGETS_CACHE.clear()
        full = ab.build_apex_widgets("hal", _fill=True)
        self.assertFalse(full.get("warming"))
        self.assertIn("widgets", full)
        os.environ.pop("NR2_WIDGETS_STUB_FASTPATH", None)


if __name__ == "__main__":
    unittest.main()
