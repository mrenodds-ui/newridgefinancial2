"""HAL-10604 — Moonshot industry HIGH carrier aliases (applied package)."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from apex_backend import BUILD_ID
from softdent_carrier_alias import (
    MOONSHOT_INDUSTRY_HIGH,
    MOONSHOT_INDUSTRY_MEDIUM,
    apply_moonshot_industry_aliases,
    ensure_carrier_alias_schema,
    resolve_accepted_alias_for_tp,
)


PACKAGE_BUILD_ID = "hal-10604"


class Hal10604MoonshotIndustryAliasTests(unittest.TestCase):
    def test_build_id(self) -> None:
        self.assertEqual(PACKAGE_BUILD_ID, "hal-10604")
        self.assertEqual(BUILD_ID, "hal-10608")

    def test_apply_high_accepts_medium_pending(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "a.db"
            con = sqlite3.connect(str(db))
            ensure_carrier_alias_schema(con)
            # Minimal spine table for list_spine_carriers
            con.execute(
                """
                CREATE TABLE insco_ada_probabilistic_estimates (
                    insurance_company TEXT,
                    ada_code TEXT,
                    sample_size INTEGER,
                    paid_amount_avg REAL
                )
                """
            )
            for spine in {
                "SUN LIFE FINANCIAL",
                "CIGNA DENTAL",
                "METLIFE DENTAL",
                "ANTHEM - 1115",
                "AETNA",
                "HUMANA DENTAL",
            }:
                con.execute(
                    "INSERT INTO insco_ada_probabilistic_estimates VALUES (?,?,?,?)",
                    (spine, "D2391", 20, 50.0),
                )
            for master, _ in MOONSHOT_INDUSTRY_HIGH + MOONSHOT_INDUSTRY_MEDIUM:
                con.execute(
                    """
                    INSERT INTO carrier_alias (
                        spine_carrier_name, master_company_id, master_company_name,
                        match_score, confidence, review_status, match_method, created_at_utc
                    ) VALUES ('', NULL, ?, 0, 'reject', 'rejected', 'reject_no_safe_partner', 't')
                    """,
                    (master,),
                )
            con.commit()
            con.close()

            out = apply_moonshot_industry_aliases(db_path=db)
            self.assertTrue(out.get("ok"))
            self.assertGreaterEqual(int(out.get("highAccepted") or 0), 2)
            self.assertEqual(out.get("mediumPending"), 2)

            a = resolve_accepted_alias_for_tp("Assurant", db_path=db)
            self.assertTrue(a.get("viaAlias"))
            self.assertEqual(a.get("spineCarrierName"), "SUN LIFE FINANCIAL")
            self.assertFalse(a.get("blockedPending"))

            c = resolve_accepted_alias_for_tp("Coventry", db_path=db)
            self.assertTrue(c.get("blockedPending"))
            self.assertFalse(c.get("viaAlias"))
            self.assertEqual(c.get("spineCarrierName"), "AETNA")


if __name__ == "__main__":
    unittest.main()
