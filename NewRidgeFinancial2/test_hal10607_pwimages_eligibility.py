"""HAL-10607 — PWImages eligibility / remittance warehouse bridge."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from apex_backend import BUILD_ID
from softdent_pwimages_eligibility_hal10607 import (
    HONESTY_BANNER,
    PACKAGE_BUILD_ID,
    best_spine_match,
    ensure_pwimages_eligibility_schema,
    format_hal10607_reply,
    parse_plan_parameters,
    pwimages_eligibility_status,
    pwimages_eligibility_widget,
    run_hal10607_ingest,
)


class Hal10607PwimagesEligibilityTests(unittest.TestCase):
    def test_build_id(self) -> None:
        self.assertEqual(PACKAGE_BUILD_ID, "hal-10607")
        self.assertEqual(BUILD_ID, "hal-10608")

    def test_parse_plan_parameters_null_not_zero(self) -> None:
        empty = parse_plan_parameters("hello world no numbers")
        self.assertIsNone(empty["deductible_individual"])
        self.assertIsNone(empty["annual_max"])
        rich = parse_plan_parameters(
            "Individual deductible $50.00 Family deductible $150 "
            "Annual maximum $1000 Preventive 100% Basic 80% Major 50% "
            "Once per calendar year waiting period 6 months"
        )
        self.assertEqual(rich["deductible_individual"], 50.0)
        self.assertEqual(rich["deductible_family"], 150.0)
        self.assertEqual(rich["annual_max"], 1000.0)
        self.assertEqual(rich["pct_preventive"], 100.0)
        self.assertEqual(rich["pct_basic"], 80.0)
        self.assertEqual(rich["pct_major"], 50.0)
        self.assertTrue(rich["frequency_notes"])
        self.assertTrue(rich["waiting_period_notes"])

    def test_spine_match_delta(self) -> None:
        spine = ["DELTA DENTAL OF KANSAS", "CIGNA DENTAL", "AETNA"]
        hit = best_spine_match("delta dental", spine)
        self.assertGreaterEqual(float(hit["match_score"] or 0), 60.0)
        self.assertIn(hit["match_status"], ("auto", "pending"))

    def test_ingest_fixture_no_ocr_dollars_in_remit_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "analytics.db"
            mine = root / "eob_mine_all.json"
            # Seed a spine carrier so fuzzy can match
            conn = sqlite3.connect(str(db))
            conn.execute(
                """
                CREATE TABLE insco_ada_probabilistic_estimates (
                    insurance_company TEXT, ada_code TEXT, n INTEGER
                )
                """
            )
            conn.execute(
                "INSERT INTO insco_ada_probabilistic_estimates VALUES (?,?,?)",
                ("DELTA DENTAL OF KANSAS", "D1110", 10),
            )
            conn.execute(
                "INSERT INTO insco_ada_probabilistic_estimates VALUES (?,?,?)",
                ("CIGNA DENTAL", "D2740", 5),
            )
            ensure_pwimages_eligibility_schema(conn)
            conn.commit()
            conn.close()

            rows = [
                {
                    "path": str(root / "elig1.HTM"),
                    "lane": "patient_htm",
                    "account_or_claim_id": "100",
                    "category": "ELIGIBILITY_BENEFITS",
                    "confidence": 0.88,
                    "carriers": ["delta dental"],
                    "markers": ["eligibility", "deductible"],
                    "ocr_preview": (
                        "Eligibility Benefits DELTA DENTAL KS # 1 "
                        "Individual deductible $50 Annual maximum $1000 "
                        "Preventive 100% Basic 80% Major 50%"
                    ),
                    "mtime": "2026-01-01T00:00:00+00:00",
                },
                {
                    "path": str(root / "remit1.JPG"),
                    "lane": "account",
                    "account_or_claim_id": "200",
                    "category": "REMITTANCE_EOB",
                    "confidence": 0.95,
                    "carriers": ["aetna"],
                    "markers": ["explanation of benefits", "amount paid"],
                    "ocr_preview": "Explanation Of Benefits Amount Paid $127.00",
                    "mtime": "2026-02-01T00:00:00+00:00",
                },
            ]
            (root / "elig1.HTM").write_text(rows[0]["ocr_preview"], encoding="utf-8")
            (root / "remit1.JPG").write_bytes(b"\xff\xd8\xfffakejpg")
            mine.write_text(json.dumps(rows), encoding="utf-8")

            result = run_hal10607_ingest(
                mine_json=mine, db_path=db, propose_aliases=True
            )
            self.assertTrue(result.get("ok"), result)
            self.assertEqual(int(result.get("eligibilityUpserted") or 0), 1)
            self.assertEqual(int(result.get("remittanceUpserted") or 0), 1)
            self.assertFalse(result.get("writesSettlementMatrix"))
            self.assertFalse(result.get("writesPaymentLines"))
            self.assertFalse(result.get("inventedGold"))
            self.assertTrue(result.get("emptyIsNotZero"))
            self.assertIn("DO NOT POST", result.get("honestyBanner") or "")

            conn = sqlite3.connect(str(db))
            cols = [
                r[1]
                for r in conn.execute(
                    "PRAGMA table_info(warehouse_remittance_eobs)"
                ).fetchall()
            ]
            self.assertTrue(cols)
            moneyish = [
                c
                for c in cols
                if __import__("re").search(
                    r"(?i)amount|paid|payment|responsibility|allowed|write.?off", c
                )
            ]
            self.assertEqual(moneyish, [])

            elig = conn.execute(
                "SELECT raw_carrier, matched_spine, deductible_individual, annual_max "
                "FROM staging_eligibility_parameters"
            ).fetchone()
            self.assertIsNotNone(elig)
            self.assertIn("delta", (elig[0] or "").lower())
            self.assertTrue(elig[2] is None or float(elig[2]) == 50.0)

            remit = conn.execute(
                "SELECT source_path, category FROM warehouse_remittance_eobs"
            ).fetchone()
            self.assertEqual(remit[1], "REMITTANCE_EOB")
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            if "sd_insurance_payment_lines" in tables:
                n = conn.execute(
                    "SELECT COUNT(*) FROM sd_insurance_payment_lines"
                ).fetchone()[0]
                self.assertEqual(int(n or 0), 0)
            if "settlement_matrix" in tables:
                n = conn.execute("SELECT COUNT(*) FROM settlement_matrix").fetchone()[0]
                self.assertEqual(int(n or 0), 0)
            conn.close()

            st = pwimages_eligibility_status(db_path=db)
            self.assertEqual(int(st.get("eligibilityRows") or 0), 1)
            self.assertEqual(int(st.get("remittanceRows") or 0), 1)
            self.assertTrue(st.get("remittanceHasNoMoneyColumns"))
            self.assertIn(HONESTY_BANNER, format_hal10607_reply(result))

    def test_widget(self) -> None:
        w = pwimages_eligibility_widget()
        self.assertEqual(w.get("def"), "HAL-10607")
        self.assertIn("pwimages-eligibility", w.get("apiStatus") or "")
        self.assertIn("DO NOT POST", w.get("honesty") or "")


if __name__ == "__main__":
    unittest.main()
