"""Tesia/Vyne payer list + clearinghouse vendor wiring tests."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TesiaPayerListTests(unittest.TestCase):
    def test_summary_and_kansas_search(self) -> None:
        from tesia_payer_list_store import format_tesia_hits, payer_list_summary, search_tesia_payers

        summary = payer_list_summary()
        self.assertTrue(summary["ok"])
        self.assertGreaterEqual(summary["count"], 10)
        self.assertEqual(summary["catchAllPayerId"], "06126")

        hits = search_tesia_payers("Delta Dental of Kansas", limit=3)
        self.assertTrue(hits)
        self.assertEqual(hits[0].get("payerId"), "CDKS1")
        text = format_tesia_hits(hits)
        self.assertIn("CDKS1", text)

        ks = search_tesia_payers("", limit=20, kansas_only=True)
        self.assertTrue(any(p.get("payerId") == "47163" for p in ks))
        self.assertTrue(any(p.get("payerId") == "47171" for p in ks))

    def test_import_csv_merge(self) -> None:
        import tesia_payer_list_store as store

        fd, name = tempfile.mkstemp(prefix="tesia-import-", suffix=".csv")
        os.close(fd)
        path = Path(name)
        backup = store.PAYER_LIST_PATH.read_text(encoding="utf-8")
        try:
            path.write_text(
                "Payer ID,Payer Name,270s Available,835s Available,Notes\n"
                "TEST99,Test Kansas Dental Plan,TRUE,FALSE,Unit test import\n",
                encoding="utf-8",
            )
            result = store.import_payer_list_file(path, merge=True)
            self.assertTrue(result["ok"])
            hits = store.search_tesia_payers("TEST99", limit=1)
            self.assertTrue(hits)
            self.assertEqual(hits[0].get("payerId"), "TEST99")
        finally:
            store.PAYER_LIST_PATH.write_text(backup, encoding="utf-8")
            store.reload_payer_list()
            path.unlink(missing_ok=True)

    def test_import_office_vyne_json_shape(self) -> None:
        import tesia_payer_list_store as store

        backup = store.PAYER_LIST_PATH.read_text(encoding="utf-8")
        try:
            rows = [
                {
                    "payer_id": "0000E",
                    "vyne_payer_id": "METLIFE",
                    "insurance_name": "Metropolitan Life Insurance Company",
                    "features": "ELIGIBILITY\nCLEARCOVERAGE",
                    "alt_ids": "65978\nTLZ16\n0000E",
                }
            ]
            result = store.import_payer_rows(rows, merge=True)
            self.assertTrue(result["ok"])
            hit = store.find_payer_by_any_id("65978")
            self.assertIsNotNone(hit)
            self.assertEqual(hit.get("payerId"), "0000E")
            self.assertTrue(hit.get("eligibility270"))
        finally:
            store.PAYER_LIST_PATH.write_text(backup, encoding="utf-8")
            store.reload_payer_list()


class SoftDentTesiaJoinTests(unittest.TestCase):
    def test_candidate_ids_split_or(self) -> None:
        from softdent_tesia_join import _candidate_ids

        ids = _candidate_ids(
            {
                "payerIds": ["65978 OR 0000E", "METLIFE DENTAL"],
                "narrativeNotes": "Vyne/e-claim 65978 OR 0000E.",
            }
        )
        self.assertIn("65978", ids)
        self.assertNotIn("0000E", ids)  # skipped placeholder
        self.assertNotIn("METLIFE DENTAL", ids)

    def test_build_join_plan_has_exact_cdks1(self) -> None:
        from softdent_tesia_join import build_join_plan

        plan = build_join_plan()
        self.assertGreaterEqual(plan["counts"]["exact"], 1)
        self.assertTrue(
            any(r.get("tesiaPayerId") == "CDKS1" for r in plan["exactMatches"])
            or any(r.get("tesiaPayerId") == "CDKS1" for r in plan["expandFromSoftDent"])
        )

    def test_apply_join_stamps_tesia_id(self) -> None:
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        import payer_reference_store as pref
        import softdent_tesia_join as join
        import tesia_payer_list_store as tesia

        pref_backup = pref.PAYER_REFERENCE_PATH.read_text(encoding="utf-8")
        tesia_backup = tesia.PAYER_LIST_PATH.read_text(encoding="utf-8")
        report_path = Path(tempfile.gettempdir()) / "softdent_tesia_join_report_test.json"
        try:
            with patch.object(join, "JOIN_REPORT_PATH", report_path):
                result = join.apply_softdent_tesia_join(write_payer_reference=True, expand_tesia=True)
            self.assertTrue(result["ok"])
            self.assertGreaterEqual(result["counts"]["exact"] + result["counts"]["expand"], 20)
            data = json.loads(pref.PAYER_REFERENCE_PATH.read_text(encoding="utf-8"))
            stamped = [p for p in data["payers"] if p.get("tesiaPayerId")]
            self.assertGreaterEqual(len(stamped), 20)
            met = next(p for p in data["payers"] if p.get("id") == "metlife-dental")
            # SoftDent stores 65978; office Vyne primary is 0000E (65978 is an alt_id)
            self.assertIn(met.get("tesiaPayerId"), {"0000E", "65978"})
        finally:
            pref.PAYER_REFERENCE_PATH.write_text(pref_backup, encoding="utf-8")
            tesia.PAYER_LIST_PATH.write_text(tesia_backup, encoding="utf-8")
            pref.load_payer_reference.cache_clear()
            tesia.reload_payer_list()
            report_path.unlink(missing_ok=True)


class VyneTesiaAdapterTests(unittest.TestCase):
    def test_status_includes_vyne_tesia(self) -> None:
        from clearinghouse_eligibility_adapter import clearinghouse_status

        status = clearinghouse_status()
        self.assertIn("vyne_tesia", status.get("vendors") or {})
        self.assertEqual(status.get("preferredOfficeVendor"), "availity")

    def test_vendor_alias_tesia(self) -> None:
        from clearinghouse_eligibility_adapter import _normalize_vendor_alias, _pick_vendor

        self.assertEqual(_normalize_vendor_alias("tesia"), "vyne_tesia")
        self.assertEqual(_normalize_vendor_alias("vyne"), "vyne_tesia")
        with patch.dict(os.environ, {"CLEARINGHOUSE_MOCK": "0", "VYNE_API_KEY": "k"}, clear=False):
            self.assertEqual(_pick_vendor("tesia"), "vyne_tesia")

    def test_fetch_resolves_cdks1_and_calls_vyne(self) -> None:
        from clearinghouse_eligibility_adapter import fetch_eligibility_271

        fake_payload = {
            "payer": {"name": "Delta Dental of Kansas", "id": "CDKS1"},
            "deductibleRemaining": 50,
            "annualMaxRemaining": 1500,
            "preventive": 100,
            "basic": 80,
            "major": 50,
        }

        def fake_http(**kwargs):
            return 200, fake_payload, None

        with patch.dict(
            os.environ,
            {
                "CLEARINGHOUSE_MOCK": "0",
                "VYNE_API_KEY": "test-key",
                "DENTALXCHANGE_API_KEY": "",
                "CHANGE_HEALTHCARE_CLIENT_ID": "",
            },
            clear=False,
        ):
            with patch("clearinghouse_live_clients.http_json", side_effect=fake_http):
                result = fetch_eligibility_271(
                    {
                        "payerName": "Delta Dental of Kansas",
                        "memberId": "ABC123456",
                        "providerNpi": "1234567890",
                        "vendor": "tesia",
                    }
                )
        self.assertTrue(result.get("ok"))
        self.assertEqual(result.get("vendor"), "vyne_tesia")
        entry = result.get("entry") or {}
        self.assertEqual(entry.get("payerId"), "CDKS1")
        self.assertEqual(entry.get("source"), "vyne_tesia_271")

    def test_map_vyne_response(self) -> None:
        from clearinghouse_271_mapper import map_vyne_eligibility_response

        entry = map_vyne_eligibility_response(
            {"payerName": "MetLife", "payerId": "65978", "annualMaxRemaining": 900},
            {"payerName": "MetLife", "payerId": "65978", "memberId": "X999"},
        )
        self.assertEqual(entry.get("source"), "vyne_tesia_271")
        self.assertEqual(entry.get("payerId"), "65978")


if __name__ == "__main__":
    unittest.main()
