"""Tests for SoftDent insurance payment → ADA treatment-planning estimates."""

from __future__ import annotations

import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path

from softdent_treatment_planning import (
    format_treatment_estimate_reply,
    ingest_insurance_payment_csv,
    ingest_procedure_code_csv,
    lookup_treatment_estimate,
    normalize_ada_code,
    parse_treatment_estimate_query,
    rebuild_treatment_planning_estimates,
    run_treatment_planning_ingest,
)


class NormalizeAdaTests(unittest.TestCase):
    def test_canonical_and_softdent_internal(self) -> None:
        self.assertEqual(normalize_ada_code("D0274"), "D0274")
        self.assertEqual(normalize_ada_code("0274"), "D0274")
        self.assertEqual(normalize_ada_code("111000"), "D1110")
        self.assertEqual(normalize_ada_code("12000"), "D0120")
        self.assertEqual(normalize_ada_code("275000"), "D2750")


class ParseQueryTests(unittest.TestCase):
    def test_delta_d0274(self) -> None:
        parsed = parse_treatment_estimate_query("How much will Delta Dental typically pay for D0274?")
        assert parsed is not None
        self.assertIn("delta", parsed["payer"].lower())
        self.assertEqual(parsed["adaCode"], "D0274")

    def test_non_estimate_ignored(self) -> None:
        self.assertIsNone(parse_treatment_estimate_query("Focus 90-day claims"))


class IngestAndEstimateTests(unittest.TestCase):
    def test_ingest_aggregate_and_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "analytics.sqlite3"
            sqlite3.connect(db_path).close()

            pay = root / "insurance_payments_20260710.csv"
            with pay.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "Insurance Company",
                        "Procedure Code",
                        "Submitted Fee",
                        "Allowed Amount",
                        "Paid Amount",
                        "Write-Off Amount",
                        "Patient Portion",
                        "Claim Number",
                    ],
                )
                writer.writeheader()
                for i in range(12):
                    writer.writerow(
                        {
                            "Insurance Company": "Delta Dental PPO",
                            "Procedure Code": "D0274",
                            "Submitted Fee": "150.00",
                            "Allowed Amount": "120.00",
                            "Paid Amount": "96.00",
                            "Write-Off Amount": "30.00",
                            "Patient Portion": "24.00",
                            "Claim Number": f"C{i}",
                        }
                    )

            codes = root / "procedure_codes_20260710.csv"
            with codes.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["Internal Code", "ADA Code", "Description", "UCR Fee"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "Internal Code": "27400",
                        "ADA Code": "D0274",
                        "Description": "Bitewings - four films",
                        "UCR Fee": "150",
                    }
                )

            result = run_treatment_planning_ingest(search_dir=root, db_path=db_path)
            self.assertTrue(result["ok"])
            self.assertEqual(result["paymentLines"], 12)
            self.assertEqual(result["procedureCodes"], 1)
            self.assertGreaterEqual(result["estimates"], 1)

            est = lookup_treatment_estimate(payer="Delta Dental", ada_code="D0274", db_path=db_path)
            self.assertTrue(est["found"])
            self.assertTrue(est["sufficient"])
            self.assertEqual(est["estimate"]["sampleSize"], 12)
            self.assertAlmostEqual(float(est["estimate"]["paidAmountAvg"]), 96.0)
            reply = format_treatment_estimate_reply(est)
            self.assertIn("D0274", reply)
            self.assertIn("96.00", reply)
            self.assertIn("estimate", reply.lower())

            thin = lookup_treatment_estimate(payer="Cigna", ada_code="D1110", db_path=db_path)
            self.assertFalse(thin["found"])

    def test_insufficient_sample(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "analytics.sqlite3"
            conn = sqlite3.connect(db_path)
            try:
                pay = root / "insurance_payments_thin.csv"
                with pay.open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(
                        handle,
                        fieldnames=["Payer", "ADACode", "Paid", "Allowed", "WriteOff"],
                    )
                    writer.writeheader()
                    writer.writerow(
                        {
                            "Payer": "Cigna",
                            "ADACode": "D1110",
                            "Paid": "50",
                            "Allowed": "80",
                            "WriteOff": "20",
                        }
                    )
                ingest_insurance_payment_csv(pay, conn)
                rebuild_treatment_planning_estimates(conn)
                conn.commit()
            finally:
                conn.close()

            est = lookup_treatment_estimate(payer="Cigna", ada_code="D1110", db_path=db_path)
            self.assertTrue(est["found"])
            self.assertFalse(est["sufficient"])
            self.assertIn("need >=10", format_treatment_estimate_reply(est))

    def test_crosswalk_maps_internal_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "analytics.sqlite3"
            conn = sqlite3.connect(db_path)
            try:
                pay = root / "insurance_payments_internal.csv"
                with pay.open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(
                        handle,
                        fieldnames=["Insurance Company", "Procedure Code", "Paid Amount", "Allowed Amount"],
                    )
                    writer.writeheader()
                    for i in range(10):
                        writer.writerow(
                            {
                                "Insurance Company": "MetLife",
                                "Procedure Code": "111000",
                                "Paid Amount": "70",
                                "Allowed Amount": "90",
                            }
                        )
                codes = root / "procedure_codes.csv"
                with codes.open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=["Internal Code", "ADA Code"])
                    writer.writeheader()
                    writer.writerow({"Internal Code": "111000", "ADA Code": "D1110"})
                ingest_insurance_payment_csv(pay, conn)
                # Payment ingest already normalizes 111000 → D1110 via heuristic;
                # also verify explicit crosswalk ingest works.
                ingest_procedure_code_csv(codes, conn)
                rebuild_treatment_planning_estimates(conn)
                conn.commit()
            finally:
                conn.close()

            est = lookup_treatment_estimate(payer="MetLife", ada_code="D1110", db_path=db_path)
            self.assertTrue(est["found"])
            self.assertTrue(est["sufficient"])


if __name__ == "__main__":
    unittest.main()
