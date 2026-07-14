"""HAL-10601 — TP payer resolution via accepted carrier_alias."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from apex_backend import BUILD_ID
from softdent_carrier_alias import (
    ensure_carrier_alias_schema,
    reconcile_carrier_aliases,
)
from softdent_insco_ada_pct_variance import build_insco_ada_pct_variance, ensure_pct_variance_schema
from softdent_insco_ada_probabilistic import (
    build_insco_ada_probabilistic_estimates,
    ensure_probabilistic_schema,
)
from softdent_insurance_company_reference import (
    ensure_insurance_company_reference_schema,
    ingest_insurance_companies_csv,
)
from softdent_odbc_extract import ensure_sd_schema
from softdent_treatment_planning import (
    lookup_treatment_estimate,
    treatment_planning_status,
)


def _seed(db: Path) -> None:
    conn = sqlite3.connect(str(db))
    try:
        ensure_sd_schema(conn)
        ensure_probabilistic_schema(conn)
        ensure_pct_variance_schema(conn)
        ensure_insurance_company_reference_schema(conn)
        ensure_carrier_alias_schema(conn)
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sd_account_transactions (
                stable_id TEXT PRIMARY KEY,
                source_file TEXT,
                row_number INTEGER,
                account_num TEXT,
                patient_name TEXT,
                service_date TEXT,
                provider TEXT,
                procedure TEXT,
                note_flag TEXT,
                amount REAL,
                prod REAL,
                charges REAL,
                prod_adj REAL,
                cash REAL,
                "check" REAL,
                credit REAL,
                pay_adj REAL,
                period_start TEXT,
                period_end TEXT,
                extracted_at TEXT
            );
            """
        )
        conn.execute(
            """
            INSERT INTO sd_patient_insurance (
                practice_id, patient_id, priority, insurance_name, extracted_at
            ) VALUES ('', '400400', 1, 'AETNA', 'now')
            """
        )
        rn = 1
        for i in range(32):
            day = f"2025-{(i % 9) + 1:02d}-{(i % 27) + 1:02d}"
            for proc, billed, prod_adj, paid in (
                ("2391", 120.0, None, None),
                ("51", None, -24.0, None),
                ("2", None, None, 72.0),
            ):
                conn.execute(
                    """
                    INSERT INTO sd_account_transactions (
                        stable_id, source_file, row_number, account_num, patient_name,
                        service_date, provider, procedure, note_flag, amount,
                        prod, charges, prod_adj, cash, "check", credit, pay_adj,
                        period_start, period_end, extracted_at
                    ) VALUES (?, 't', ?, ?, 'Test', ?, '', ?, 'A', ?, ?, NULL, ?, NULL, ?, NULL, NULL,
                              '2021-01-01', '2026-07-01', 'now')
                    """,
                    (
                        f"tp{rn}",
                        rn,
                        "400400",
                        day,
                        proc,
                        billed or prod_adj or paid,
                        billed,
                        prod_adj,
                        paid,
                    ),
                )
                rn += 1
        conn.commit()
        build_insco_ada_probabilistic_estimates(conn)
        build_insco_ada_pct_variance(conn, years=5)
        conn.commit()
    finally:
        conn.close()


class TreatmentPlanningAliasHal10601Tests(unittest.TestCase):
    def test_build_id_coupled(self) -> None:
        self.assertEqual(BUILD_ID, "hal-10608")
        st = treatment_planning_status()
        self.assertTrue(st.get("tpCodeUsesCarrierAlias") or st.get("ok") is False)

    def test_accepted_alias_resolves_spine_dollars(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "a.db"
            _seed(db)
            csv_path = root / "c.csv"
            csv_path.write_text(
                "company_name,status,record_number\n"
                '"AETNA","likely_active","1"\n'
                '"Aetna Healthcare","likely_active","302"\n'
                '"Pending Co","likely_active","9"\n',
                encoding="utf-8",
            )
            ingest_insurance_companies_csv(
                csv_path=csv_path, db_path=db, copy_to_exports=False
            )
            reconcile_carrier_aliases(db_path=db, dest=root)

            # Seed a pending manual that must NOT auto-resolve
            conn = sqlite3.connect(str(db))
            conn.execute(
                """
                INSERT OR REPLACE INTO carrier_alias (
                    spine_carrier_name, master_company_id, master_company_name,
                    match_score, confidence, review_status, match_method, created_at_utc
                ) VALUES ('AETNA', '9', 'Pending Co', 72.0, 'manual', 'pending',
                          'fuzzy_blocked_jw', 'now')
                """
            )
            conn.commit()
            conn.close()

            miss = lookup_treatment_estimate(
                payer="Aetna Healthcare", ada_code="D2391", db_path=db
            )
            self.assertTrue(miss.get("ok"))
            self.assertTrue(miss.get("found"))
            self.assertTrue(miss.get("viaAlias"))
            self.assertTrue(miss.get("tpCodeUsesCarrierAlias"))
            self.assertEqual(miss.get("source"), "ledger_episode_5yr_via_alias")
            self.assertEqual(miss.get("def"), "HAL-10601")
            est = miss.get("estimate") or {}
            self.assertEqual(est.get("source"), "ledger_episode_5yr_via_alias")
            self.assertEqual(str(est.get("spineCarrierName") or "").upper(), "AETNA")
            self.assertEqual(str(est.get("insuranceCompany")), "Aetna Healthcare")
            self.assertIsNotNone(est.get("paidAmountAvg"))
            self.assertNotEqual(est.get("paidAmountAvg"), 0)
            self.assertTrue((miss.get("chip") or {}).get("emptyIsNotZero"))

            pending = lookup_treatment_estimate(
                payer="Pending Co", ada_code="D2391", db_path=db
            )
            self.assertTrue(pending.get("blockedPending"))
            self.assertFalse(pending.get("sufficient"))
            self.assertEqual(pending.get("credibility"), "insufficient")
            self.assertEqual(pending.get("source"), "carrier_alias_pending")
            pend_est = pending.get("estimate") or {}
            self.assertIsNone(pend_est.get("paidAmountAvg"))
            self.assertTrue((pending.get("chip") or {}).get("emptyIsNotZero"))
            self.assertFalse((pending.get("chip") or {}).get("showDollars"))


if __name__ == "__main__":
    unittest.main()
