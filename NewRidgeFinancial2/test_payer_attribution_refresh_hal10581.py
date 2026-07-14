"""HAL-10581 Sensei insurance populate + claims payer attribution refresh."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from softdent_odbc_extract import (
    attribute_sd_claims_payers_from_insurance,
    ensure_sd_schema,
    extract_claim_chart_from_id,
    load_sensei_plan_carrier_map,
    populate_sensei_patient_insurance,
    refresh_claims_payer_attribution,
)
from softdent_outstanding_claims_bridge import (
    GAP_PAYER_ATTRIBUTION,
    aggregate_sd_claims_by_carrier,
    reconcile_claims_to_aging,
)


def _write_sensei_fixture(root: Path) -> None:
    ref = root / "Reference"
    ref.mkdir(parents=True)
    (ref / "insco_701.json").write_text(
        json.dumps(
            {
                "INSURCO": {
                    "Id": "701",
                    "Name": "DELTA DENTAL OF OH",
                    "PlanArray": {
                        "ArrayOfPLAN": [
                            {"PLAN": {"Id": "3880", "Name": "DELTA DENTAL OF OHIO", "InsCo": "701", "GroupNo": ""}}
                        ]
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    (ref / "patient_574894.json").write_text(
        json.dumps(
            {
                "PATIENT": {
                    "UniqueID": "574894",
                    "Id": "1080404",
                    "InterfaceId": "1080404",
                    "ulAccountId": "1080400",
                    "Firstname": "Jeffery",
                    "Lastname": "Bernett",
                    "InsurancePolicies": [
                        {
                            "InsurancePlanKey": "3880",
                            "PolicyHolderKey": "RP0-1080400",
                            "CoverageType": 1,
                            "MemberId": "440701173",
                            "RelationshipToPolicyHolderType": "01",
                        }
                    ],
                }
            }
        ),
        encoding="utf-8",
    )


class PayerAttributionRefreshHal10581Tests(unittest.TestCase):
    def test_extract_claim_chart(self) -> None:
        self.assertEqual(extract_claim_chart_from_id("DS-20260528-1080404-1110-3"), "1080404")
        self.assertIsNone(extract_claim_chart_from_id("CLM-001"))

    def test_sensei_insurance_and_claim_attribution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "datasync" / "0000950863"
            _write_sensei_fixture(root)
            db = Path(tmp) / "analytics.db"
            conn = sqlite3.connect(str(db))
            ensure_sd_schema(conn)
            plan_map = load_sensei_plan_carrier_map(root)
            self.assertEqual(plan_map["3880"]["insurance_name"], "DELTA DENTAL OF OH")

            ins = populate_sensei_patient_insurance(conn, root, extracted_at="2026-07-13T00:00:00+00:00")
            self.assertGreater(ins["sd_patient_insurance"], 0)
            # Chart key present for daysheet MRN match
            row = conn.execute(
                "SELECT insurance_name, member_id FROM sd_patient_insurance WHERE patient_id='1080404' AND priority=1"
            ).fetchone()
            self.assertEqual(row[0], "DELTA DENTAL OF OH")
            self.assertEqual(row[1], "440701173")

            conn.execute(
                """
                INSERT INTO sd_claims
                (claim_id, patient_name, payer, service_date, claim_amount, claim_status,
                 practice_id, extracted_at, total_fee, balance)
                VALUES
                ('DS-20260528-1080404-1110-3', 'Bernett, Jeffery Adam', 'Insurance',
                 '2026-05-28', 137.0, 'Pending Review', '', 'now', 137.0, NULL),
                ('CLM-KEEP', 'Jane Doe', 'Delta Dental', '2026-05-01', 50.0, 'Pending Review', '', 'now', 50.0, NULL)
                """
            )
            conn.commit()
            attr = attribute_sd_claims_payers_from_insurance(conn)
            self.assertEqual(attr["updated"], 1)
            self.assertEqual(attr["skipped_named"], 1)
            payer = conn.execute(
                "SELECT payer FROM sd_claims WHERE claim_id='DS-20260528-1080404-1110-3'"
            ).fetchone()[0]
            self.assertEqual(payer, "DELTA DENTAL OF OH")
            keep = conn.execute("SELECT payer FROM sd_claims WHERE claim_id='CLM-KEEP'").fetchone()[0]
            self.assertEqual(keep, "Delta Dental")
            conn.close()

            claims = aggregate_sd_claims_by_carrier(db_path=db)
            self.assertEqual(claims["namedPayerClaimCount"], 2)
            self.assertEqual(claims["unnamedPayerClaimCount"], 0)
            recon = reconcile_claims_to_aging(
                claims,
                {
                    "ok": True,
                    "outstandingInsuranceTotal": 0.0,
                    "trueReceivablesTotal": 100.0,
                },
            )
            self.assertNotEqual(recon.get("gapCode"), GAP_PAYER_ATTRIBUTION)

    def test_refresh_claims_payer_attribution_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "datasync" / "0000950863"
            _write_sensei_fixture(root)
            db = Path(tmp) / "analytics.db"
            conn = sqlite3.connect(str(db))
            ensure_sd_schema(conn)
            conn.execute(
                """
                INSERT INTO sd_claims
                (claim_id, patient_name, payer, service_date, claim_amount, claim_status,
                 practice_id, extracted_at, total_fee, balance)
                VALUES
                ('DS-20260528-1080404-120-4', 'Bernett, Jeffery Adam', 'Insurance',
                 '2026-05-28', 100.0, 'Pending Review', '', 'now', 100.0, NULL)
                """
            )
            conn.commit()
            conn.close()
            result = refresh_claims_payer_attribution(db_path=db, sensei_root=root)
            self.assertTrue(result.get("ok"))
            self.assertGreater(int(result.get("sd_patient_insurance_count") or 0), 0)
            self.assertEqual(int(result["attribution"]["updated"]), 1)
            self.assertGreaterEqual(int(result.get("namedPayerClaimCount") or 0), 1)


if __name__ == "__main__":
    unittest.main()
