"""HAL-10605 — Gold settlement_matrix + Moonshot NEW HIGH aliases."""

from __future__ import annotations

import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path

from apex_backend import BUILD_ID
from softdent_carrier_alias import (
    MOONSHOT_INDUSTRY_HIGH,
    apply_moonshot_industry_aliases,
    ensure_carrier_alias_schema,
    resolve_accepted_alias_for_tp,
)
from softdent_settlement_matrix import (
    PACKAGE_BUILD_ID,
    hydrate_settlement_matrix,
    lookup_settlement_matrix,
)
from softdent_treatment_planning import (
    ensure_treatment_planning_schema,
    lookup_treatment_estimate,
)


class Hal10605GoldSettlementTests(unittest.TestCase):
    def test_build_id(self) -> None:
        self.assertEqual(PACKAGE_BUILD_ID, "hal-10605")
        self.assertEqual(BUILD_ID, "hal-10608")

    def test_new_high_aliases_in_package(self) -> None:
        pairs = {m: s for m, s in MOONSHOT_INDUSTRY_HIGH}
        self.assertEqual(pairs.get("Great-west"), "CIGNA DENTAL")
        self.assertEqual(pairs.get("Kanawha Benefit Solutions, Inc"), "HUMANA DENTAL")

    def test_hydrate_empty_gold_clears_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "a.db"
            con = sqlite3.connect(str(db))
            ensure_treatment_planning_schema(con)
            con.execute(
                """
                CREATE TABLE insco_ada_probabilistic_estimates (
                    insurance_company TEXT, ada_code TEXT,
                    sample_size INTEGER, paid_amount_avg REAL
                )
                """
            )
            con.execute(
                "INSERT INTO insco_ada_probabilistic_estimates VALUES (?,?,?,?)",
                ("AETNA", "D2391", 20, 50.0),
            )
            con.commit()
            con.close()
            out = hydrate_settlement_matrix(db_path=db)
            self.assertEqual(out.get("gapCode"), "GOLD_CSV_MISSING")
            self.assertEqual(out.get("matrixCells"), 0)
            self.assertFalse(out.get("inventedGold"))

    def test_hydrate_and_tp_prefers_via_gold(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "a.db"
            con = sqlite3.connect(str(db))
            ensure_treatment_planning_schema(con)
            ensure_carrier_alias_schema(con)
            con.execute(
                """
                CREATE TABLE insco_ada_probabilistic_estimates (
                    insurance_company TEXT, ada_code TEXT,
                    sample_size INTEGER, paid_amount_avg REAL
                )
                """
            )
            con.execute(
                "INSERT INTO insco_ada_probabilistic_estimates VALUES (?,?,?,?)",
                ("AETNA", "D2391", 20, 1.0),
            )
            for i in range(12):
                con.execute(
                    """
                    INSERT INTO sd_insurance_payment_lines (
                        line_id, insurance_company, ada_code, paid_amount,
                        source_file, extracted_at
                    ) VALUES (?, 'AETNA', 'D2391', ?, 't.csv', 't')
                    """,
                    (f"L{i}", 60.0 + i),
                )
            con.commit()
            con.close()
            h = hydrate_settlement_matrix(db_path=db)
            self.assertEqual(h.get("gapCode"), "GOLD_OK")
            self.assertGreaterEqual(int(h.get("cellsNge10") or 0), 1)

            cell = lookup_settlement_matrix(payer="AETNA", ada_code="D2391", db_path=db)
            self.assertTrue(cell.get("viaGold"))
            self.assertTrue(cell.get("sufficient"))

            tp = lookup_treatment_estimate(payer="AETNA", ada_code="D2391", db_path=db)
            self.assertEqual(tp.get("source"), "viaGold")
            self.assertTrue(tp.get("viaGold"))
            self.assertTrue(tp.get("sufficient"))
            self.assertIsNotNone((tp.get("estimate") or {}).get("paidAmountAvg"))
            self.assertNotEqual((tp.get("estimate") or {}).get("paidAmountAvg"), 0.0)

    def test_apply_new_highs_coventry_stays_pending(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "a.db"
            con = sqlite3.connect(str(db))
            ensure_carrier_alias_schema(con)
            con.execute(
                """
                CREATE TABLE insco_ada_probabilistic_estimates (
                    insurance_company TEXT, ada_code TEXT,
                    sample_size INTEGER, paid_amount_avg REAL
                )
                """
            )
            for spine in ("CIGNA DENTAL", "HUMANA DENTAL", "AETNA"):
                con.execute(
                    "INSERT INTO insco_ada_probabilistic_estimates VALUES (?,?,?,?)",
                    (spine, "D2391", 20, 50.0),
                )
            for master in (
                "Great-west",
                "Kanawha Benefit Solutions, Inc",
                "Coventry",
                "Coventry Health Care Of Kansas",
            ):
                con.execute(
                    """
                    INSERT INTO carrier_alias (
                        spine_carrier_name, master_company_id, master_company_name,
                        match_score, confidence, review_status, match_method, created_at_utc
                    ) VALUES ('', NULL, ?, 0, 'reject', 'rejected', 'x', 't')
                    """,
                    (master,),
                )
            con.commit()
            con.close()
            out = apply_moonshot_industry_aliases(db_path=db)
            self.assertTrue(out.get("ok"))
            gw = resolve_accepted_alias_for_tp("Great-west", db_path=db)
            self.assertTrue(gw.get("viaAlias"))
            self.assertEqual(gw.get("spineCarrierName"), "CIGNA DENTAL")
            cv = resolve_accepted_alias_for_tp("Coventry", db_path=db)
            self.assertTrue(cv.get("blockedPending"))
            self.assertFalse(cv.get("viaAlias"))


if __name__ == "__main__":
    unittest.main()
