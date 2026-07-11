"""Tests for HAL patient dossier + Mon–Thu schedule (hal-10497). SoftDent read-only; empty≠$0."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from apex_backend import BUILD_ID
from apex_missing_widgets_pack import (
    build_claims_review_detail,
    build_eligibility_card_widget,
    build_patient_dossier_card,
    build_weekly_schedule_list,
    render_eligibility_card,
)
from patient_dossier import (
    _normalize_eligibility_benefits,
    _resolve_eligibility_for_patient,
    _safe_money,
    build_patient_dossier,
    format_dossier_markdown,
    patient_hash,
)
from patient_dossier_prompts import DOSSIER_SUMMARY_PROMPT
from nr2_softdent_daily import appointments_range_snapshot, monday_of_week_iso
from nr2_rbac import has_capability


def _seed_sd_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE sd_patients (
            patient_id TEXT NOT NULL,
            patient_name TEXT,
            first_visit_date TEXT,
            last_visit_date TEXT,
            practice_id TEXT NOT NULL DEFAULT '',
            extracted_at TEXT,
            PRIMARY KEY (practice_id, patient_id)
        );
        CREATE TABLE sd_appointments (
            practice_id TEXT NOT NULL DEFAULT '',
            patient_id TEXT,
            appt_date TEXT,
            provider_code TEXT,
            status TEXT,
            extracted_at TEXT
        );
        CREATE TABLE sd_procedures (
            practice_id TEXT NOT NULL DEFAULT '',
            patient_id TEXT,
            proc_date TEXT,
            ada_code TEXT,
            tooth TEXT,
            surface TEXT,
            provider_code TEXT,
            description TEXT,
            production REAL,
            extracted_at TEXT
        );
        CREATE TABLE sd_payments (
            practice_id TEXT NOT NULL DEFAULT '',
            patient_id TEXT,
            payment_date TEXT,
            amount REAL,
            payer TEXT,
            method TEXT,
            extracted_at TEXT
        );
        CREATE TABLE sd_adjustments (
            practice_id TEXT NOT NULL DEFAULT '',
            patient_id TEXT,
            adj_date TEXT,
            ada_code TEXT,
            amount REAL,
            description TEXT,
            extracted_at TEXT
        );
        CREATE TABLE sd_claims (
            claim_id TEXT NOT NULL,
            patient_name TEXT,
            payer TEXT,
            service_date TEXT,
            claim_amount REAL,
            claim_status TEXT,
            practice_id TEXT NOT NULL DEFAULT '',
            extracted_at TEXT,
            PRIMARY KEY (practice_id, claim_id)
        );
        """
    )
    conn.execute(
        "INSERT INTO sd_patients VALUES ('P100','Jane Doe','2020-01-01','2026-07-01','',NULL)"
    )
    conn.execute(
        "INSERT INTO sd_appointments VALUES ('','P100','2026-07-14','DR1','booked',NULL)"
    )
    conn.execute(
        "INSERT INTO sd_procedures VALUES ('','P100','2026-06-01','D1110','','','DR1','prophy',NULL,NULL)"
    )
    conn.execute(
        "INSERT INTO sd_payments VALUES ('','P100','2026-06-15',NULL,'Delta','check',NULL)"
    )
    conn.execute(
        "INSERT INTO sd_payments VALUES ('','P100','2026-06-16',0,'Delta','check',NULL)"
    )
    conn.execute(
        "INSERT INTO sd_claims VALUES ('C9','Jane Doe','Delta','2026-06-01',NULL,'pending','',NULL)"
    )
    conn.commit()
    conn.close()


def _seed_sd_db_with_insurance(path: Path) -> None:
    _seed_sd_db(path)
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE sd_patient_insurance (
            patient_id TEXT,
            member_id TEXT,
            subscriber_id TEXT,
            insurance_name TEXT,
            payer_id TEXT
        );
        INSERT INTO sd_patient_insurance VALUES ('P100','MEM123',NULL,'Delta Dental','DELTA');
        """
    )
    conn.commit()
    conn.close()


class SafeMoneyTests(unittest.TestCase):
    def test_null_empty_zero_unknown(self) -> None:
        self.assertEqual(_safe_money(None), "unknown")
        self.assertEqual(_safe_money(""), "unknown")
        self.assertEqual(_safe_money(0), "unknown")
        self.assertEqual(_safe_money(0.0), "unknown")
        self.assertEqual(_safe_money(12.5), "$12.50")

    def test_never_literal_zero_dollars_for_falsy(self) -> None:
        for v in (None, "", 0, 0.0):
            out = _safe_money(v)
            self.assertNotIn("$0", out)
            self.assertEqual(out, "unknown")


class PatientDossierTests(unittest.TestCase):
    def test_build_id(self) -> None:
        self.assertEqual(BUILD_ID, "hal-10497")

    def test_dossier_empty_money_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "sd.db"
            _seed_sd_db(db)
            with mock.patch("patient_dossier.resolve_sd_sqlite_db", return_value=db):
                with mock.patch("patient_dossier.load_clinical_context", create=True):
                    # Patch clinical import inside build
                    with mock.patch.dict("sys.modules", {}):
                        dossier = build_patient_dossier("P100", use_cache=False, include_clinical=False, include_estimates=False)
            self.assertTrue(dossier.get("ok"))
            self.assertEqual(dossier["patientHash"], patient_hash("P100"))
            self.assertEqual(len(dossier["procedures"]), 1)
            self.assertEqual(dossier["procedures"][0]["production"], "unknown")
            pays = dossier["transactions"]["payments"]
            self.assertTrue(pays)
            for p in pays:
                self.assertEqual(p["amount"], "unknown")
                self.assertNotIn("$0", p["amount"])
            self.assertTrue(dossier["claims"])
            self.assertEqual(dossier["claims"][0]["amount"], "unknown")
            md = format_dossier_markdown(dossier)
            self.assertIn("unknown", md)
            self.assertNotIn("$0.00", md)
            self.assertNotIn("Jane Doe", md)  # PHI: hash/initials only in demographics
            self.assertIn("### Eligibility", md)

    def test_rbac_capability(self) -> None:
        self.assertTrue(has_capability("read_patient_dossier", "office_manager"))
        self.assertTrue(has_capability("read_patient_dossier", "dentist"))
        self.assertFalse(has_capability("read_patient_dossier", "front_desk"))
        self.assertFalse(has_capability("read_patient_dossier", "hygienist"))


class EligibilityDossierTests(unittest.TestCase):
    def test_eligibility_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "sd.db"
            _seed_sd_db(db)
            with mock.patch("patient_dossier.resolve_sd_sqlite_db", return_value=db):
                dossier = build_patient_dossier(
                    "P100", use_cache=False, include_clinical=False, include_estimates=False
                )
        elig = dossier.get("eligibility") or {}
        for key in ("queriedAt", "source", "live", "demo", "gaps", "benefits", "error", "cacheHit"):
            self.assertIn(key, elig)
        self.assertEqual(elig.get("source"), "availity_271")

    def test_eligibility_unknown_money_not_zero(self) -> None:
        benefits = _normalize_eligibility_benefits(
            {"deductibleRemaining": 0, "annualMaxRemaining": None, "annualMax": ""}
        )
        self.assertEqual(benefits["deductibleRemaining"], "unknown")
        self.assertEqual(benefits["annualMaxRemaining"], "unknown")
        self.assertNotIn("$0", str(benefits["deductibleRemaining"]))

    def test_eligibility_gaps_when_softdent_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "sd.db"
            _seed_sd_db(db)
            with mock.patch("patient_dossier.resolve_sd_sqlite_db", return_value=db):
                with mock.patch.dict(os.environ, {}, clear=False):
                    os.environ.pop("NR2_PROVIDER_NPI", None)
                    dossier = build_patient_dossier(
                        "P100", use_cache=False, include_clinical=False, include_estimates=False
                    )
        gaps = (dossier.get("eligibility") or {}).get("gaps") or []
        self.assertIn("memberId", gaps)
        self.assertIn("providerNPI", gaps)

    def test_cache_hit_skips_http_with_temp_cache_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "sd.db"
            cache_dir = Path(tmp) / "cache"
            _seed_sd_db_with_insurance(db)
            cache_key = patient_hash("P100:MEM123:DELTA:1234567890")
            with mock.patch("patient_dossier.resolve_sd_sqlite_db", return_value=db):
                with mock.patch.dict(os.environ, {"NR2_PROVIDER_NPI": "1234567890"}):
                    with mock.patch("eligibility_cache_store.CACHE_DIR", cache_dir):
                        with mock.patch("eligibility_cache_store.INDEX_PATH", cache_dir / "index.jsonl"):
                            from eligibility_cache_store import store_eligibility_snapshot

                            store_eligibility_snapshot(
                                cache_key,
                                {
                                    "planDescription": "Delta PPO",
                                    "payerName": "Delta Dental",
                                    "deductibleRemaining": 100,
                                    "annualMaxRemaining": 1200,
                                    "coinsurancePreventive": "100%",
                                    "demo": True,
                                },
                                ttl_sec=300,
                            )
                            with mock.patch(
                                "clearinghouse_eligibility_adapter.fetch_eligibility_271"
                            ) as fetch_mock:
                                dossier = build_patient_dossier(
                                    "P100",
                                    use_cache=False,
                                    include_clinical=False,
                                    include_estimates=False,
                                )
                            fetch_mock.assert_not_called()
            elig = dossier.get("eligibility") or {}
            self.assertTrue(elig.get("cacheHit"))
            self.assertTrue(elig.get("demo"))
            self.assertEqual((elig.get("benefits") or {}).get("deductibleRemaining"), 100)

    def test_prompt_includes_demo_and_eligibility(self) -> None:
        self.assertIn("Eligibility", DOSSIER_SUMMARY_PROMPT)
        self.assertIn("[DEMO DATA]", DOSSIER_SUMMARY_PROMPT)
        self.assertIn("fetch_eligibility_271", DOSSIER_SUMMARY_PROMPT)

    def test_render_eligibility_card(self) -> None:
        card = render_eligibility_card(
            {
                "demo": True,
                "gaps": ["memberId"],
                "benefits": {
                    "planName": "Delta PPO",
                    "payerName": "Delta",
                    "deductibleRemaining": "unknown",
                    "annualMaxRemaining": 1200,
                    "preventive": "100%",
                    "basic": "80%",
                    "major": "50%",
                    "limitations": ["Waiting period"],
                },
                "queriedAt": "2026-07-11T21:30:00Z",
            }
        )
        self.assertEqual(card["widget"], "eligibility-card")
        self.assertEqual(card["badge"], "DEMO")
        self.assertIn("memberId", card.get("warning") or "")
        self.assertEqual(card["rows"][2]["value"], "unknown")

    def test_dossier_card_embeds_eligibility(self) -> None:
        dossier = {
            "ok": True,
            "patientHash": "ABCD",
            "demographics": {"initials": "JD"},
            "eligibility": {"demo": True, "gaps": [], "benefits": {"planName": "Test Plan"}},
        }
        w = build_patient_dossier_card(dossier)
        self.assertIn("eligibilityCard", w["data"])
        self.assertEqual(w["data"]["eligibilityCard"]["widget"], "eligibility-card")

    def test_eligibility_card_widget_registered(self) -> None:
        w = build_eligibility_card_widget({"demo": True, "benefits": {"planName": "X"}})
        self.assertEqual(w["widgetId"], "eligibility-card")
        self.assertEqual(w["type"], "eligibility-card")

    def test_format_dossier_markdown_demo_prefix(self) -> None:
        md = format_dossier_markdown(
            {
                "demographics": {},
                "eligibility": {
                    "demo": True,
                    "benefits": {
                        "planName": "Delta PPO",
                        "payerName": "Delta",
                        "deductibleRemaining": "unknown",
                        "annualMaxRemaining": 1200,
                        "preventive": "100%",
                        "basic": "80%",
                        "major": "50%",
                    },
                },
            }
        )
        self.assertIn("[DEMO DATA]", md)
        self.assertIn("### Eligibility", md)

    def test_resolve_eligibility_not_queried_without_force(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            "CREATE TABLE sd_patient_insurance (patient_id TEXT, member_id TEXT, payer_id TEXT, insurance_name TEXT)"
        )
        conn.execute(
            "INSERT INTO sd_patient_insurance VALUES ('P1','M1','PAY1','Delta')"
        )
        conn.commit()
        with mock.patch.dict(os.environ, {"NR2_PROVIDER_NPI": "9999999999"}):
            with mock.patch("eligibility_cache_store.get_cached_eligibility", return_value=None):
                with mock.patch(
                    "clearinghouse_eligibility_adapter.fetch_eligibility_271"
                ) as fetch_mock:
                    result = _resolve_eligibility_for_patient(conn, "P1", "", force_fetch=False)
                fetch_mock.assert_not_called()
        self.assertIn("not queried", str(result.get("error") or "").lower())


class AppointmentsRangeTests(unittest.TestCase):
    def test_monday_helper(self) -> None:
        # 2026-07-11 is Saturday → Monday 2026-07-06
        self.assertEqual(monday_of_week_iso("2026-07-11"), "2026-07-06")

    def test_range_snapshot_hashes_no_pii(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "sd.db"
            _seed_sd_db(db)
            with mock.patch("nr2_softdent_daily.resolve_sd_sqlite_db", return_value=db):
                payload = appointments_range_snapshot("2026-07-14", days=4)
            self.assertTrue(payload.get("hasData"))
            day0 = payload["days"][0]
            self.assertEqual(day0["date"], "2026-07-14")
            self.assertEqual(day0["count"], 1)
            slot = day0["slots"][0]
            self.assertEqual(len(slot["patientHash"]), 4)
            self.assertEqual(slot["time"], "—")
            blob = str(payload)
            self.assertNotIn("Jane Doe", blob)

    def test_empty_days_honest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "sd.db"
            _seed_sd_db(db)
            with mock.patch("nr2_softdent_daily.resolve_sd_sqlite_db", return_value=db):
                payload = appointments_range_snapshot("2099-01-06", days=4)
            self.assertFalse(payload.get("hasData"))
            self.assertEqual(len(payload.get("days") or []), 4)
            self.assertTrue(payload["days"][0].get("emptyMessage"))


class WidgetBuildersTests(unittest.TestCase):
    def test_weekly_schedule_widget(self) -> None:
        w = build_weekly_schedule_list({}, live_range={"hasData": False, "days": []})
        self.assertEqual(w["widgetId"], "weekly-schedule-list")
        self.assertEqual(w["status"], "empty")

    def test_dossier_card_empty(self) -> None:
        w = build_patient_dossier_card(None)
        self.assertEqual(w["widgetId"], "patient-dossier-card")
        self.assertTrue(w["data"].get("emptyMessage"))

    def test_claims_review_empty(self) -> None:
        w = build_claims_review_detail(None)
        self.assertEqual(w["status"], "empty")


class AuditTests(unittest.TestCase):
    def test_audit_tables(self) -> None:
        from hal_patient_audit import init_audit, log_patient_query, recent_dossier_queries

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "audit.db"
            with mock.patch("hal_patient_audit.AUDIT_DB", db):
                init_audit()
                log_patient_query("office_manager", "P100", "dossier")
                rows = recent_dossier_queries(limit=5)
            self.assertTrue(rows)
            self.assertEqual(rows[0]["patient_hash"], patient_hash("P100"))
            self.assertNotEqual(rows[0]["patient_hash"], "P100")


if __name__ == "__main__":
    unittest.main()
