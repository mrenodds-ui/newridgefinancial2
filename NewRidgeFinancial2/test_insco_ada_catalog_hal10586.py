"""HAL-10586 full InsCo × ADA catalog matrix (includes insufficient)."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from softdent_insco_ada_catalog_matrix import (
    catalog_matrix_status,
    insco_ada_catalog_widget,
    list_catalog_matrix_rows,
    run_insco_ada_catalog_matrix_report,
)
from softdent_insco_ada_pct_variance import build_insco_ada_pct_variance, ensure_pct_variance_schema
from softdent_insco_ada_probabilistic import (
    build_insco_ada_probabilistic_estimates,
    ensure_probabilistic_schema,
)
from softdent_odbc_extract import ensure_sd_schema


def _seed(db: Path) -> None:
    conn = sqlite3.connect(str(db))
    try:
        ensure_sd_schema(conn)
        ensure_probabilistic_schema(conn)
        ensure_pct_variance_schema(conn)
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
            ) VALUES ('', '400400', 1, 'DELTA DENTAL OF KS', 'now')
            """
        )
        rn = 1
        # 12 exact D1110 episodes (usable)
        for i in range(12):
            day = f"2025-{(i % 9) + 1:02d}-{(i % 27) + 1:02d}"
            for proc, billed, prod_adj, paid in (
                ("1110", 140.0, None, None),
                ("51", None, -28.0, None),
                ("2", None, None, 84.0),
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
                        f"c{rn}",
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
        # Rare CDT with only 2 episodes → insufficient
        for i in range(2):
            day = f"2024-06-{i + 1:02d}"
            for proc, billed, prod_adj, paid in (
                ("2740", 1200.0, None, None),
                ("51", None, -200.0, None),
                ("2", None, None, 800.0),
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
                        f"c{rn}",
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
        # Production CDT with no settlement → uncovered universe
        conn.execute(
            """
            INSERT INTO sd_account_transactions (
                stable_id, source_file, row_number, account_num, patient_name,
                service_date, provider, procedure, note_flag, amount,
                prod, charges, prod_adj, cash, "check", credit, pay_adj,
                period_start, period_end, extracted_at
            ) VALUES ('c999', 't', 999, '400400', 'Test', '2025-03-15', '', '1351', 'A', 45,
                      45, NULL, NULL, NULL, NULL, NULL, NULL,
                      '2021-01-01', '2026-07-01', 'now')
            """
        )
        conn.commit()
    finally:
        conn.close()


class InscoAdaCatalogHal10586Tests(unittest.TestCase):
    def test_catalog_includes_insufficient_not_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "analytics.db"
            _seed(db)
            conn = sqlite3.connect(str(db))
            try:
                build_insco_ada_probabilistic_estimates(conn, years=5)
                build_insco_ada_pct_variance(conn, years=5)
            finally:
                conn.close()

            st = catalog_matrix_status(db_path=db)
            self.assertTrue(st.get("ok"))
            self.assertGreaterEqual(int(st.get("exactUsableCells") or 0), 1)
            self.assertGreaterEqual(int(st.get("insufficientCells") or 0), 1)

            all_rows = list_catalog_matrix_rows(
                db_path=db, include_insufficient=True, include_inferred=True, limit=100
            )
            self.assertGreaterEqual(len(all_rows), 2)
            insuff = [r for r in all_rows if r.get("credibility") == "insufficient"]
            self.assertTrue(insuff)
            for r in insuff:
                self.assertTrue(r.get("emptyIsNotZero"))
                # never invent literal zero when empty
                if int(r.get("sampleSize") or 0) <= 0:
                    self.assertIsNone(r.get("paidMedian"))

            exact = list_catalog_matrix_rows(
                db_path=db, include_insufficient=False, include_inferred=False, limit=20
            )
            self.assertTrue(any(r.get("adaCode") == "D1110" for r in exact))

            rep = run_insco_ada_catalog_matrix_report(db_path=db)
            self.assertTrue(rep.get("ok"))
            self.assertGreaterEqual(int((rep.get("export") or {}).get("cellCount") or 0), 2)

            w = insco_ada_catalog_widget()
            # widget uses live DB; just check shape when live empty is ok
            self.assertEqual(w.get("id"), "softdent-insco-ada-catalog")
            self.assertEqual(w.get("def"), "HAL-10596")


if __name__ == "__main__":
    unittest.main()
