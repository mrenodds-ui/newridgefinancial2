"""HAL-10584 InsCo × ADA pay/WO % +/- variance from SoftDent codes 2/51."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from softdent_insco_ada_pct_variance import (
    build_insco_ada_pct_variance,
    ensure_pct_variance_schema,
    lookup_pct_variance,
)
from softdent_insco_ada_probabilistic import ensure_probabilistic_schema
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
            ) VALUES ('', '200200', 1, 'DELTA DENTAL OF KS', 'now')
            """
        )
        rows: list[tuple] = []
        rn = 1
        for i in range(12):
            day = f"2025-{(i % 9) + 1:02d}-{(i % 27) + 1:02d}"
            rows.append(("200200", day, "1110", 140.0, None, None, rn))
            rn += 1
            rows.append(("200200", day, "51", None, -28.0, None, rn))
            rn += 1
            rows.append(("200200", day, "2", None, None, 84.0, rn))
            rn += 1
        for acct, d, proc, billed, prod_adj, paid, row_n in rows:
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
                    f"p{row_n}",
                    row_n,
                    acct,
                    d,
                    proc,
                    billed or prod_adj or paid,
                    billed,
                    prod_adj,
                    paid,
                ),
            )
        conn.commit()
    finally:
        conn.close()


class InscoAdaPctVarianceHal10584Tests(unittest.TestCase):
    def test_exact_pct_and_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "analytics.db"
            _seed(db)
            conn = sqlite3.connect(str(db))
            try:
                built = build_insco_ada_pct_variance(conn, years=5)
                self.assertTrue(built.get("ok"))
                self.assertGreaterEqual(int(built.get("episodes") or 0), 10)
                row = conn.execute(
                    """
                    SELECT tier, credibility, sample_size, paid_pct_median, write_off_pct_median
                    FROM insco_ada_pct_variance
                    WHERE ada_code='D1110' AND tier='exact'
                    """
                ).fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(row[0], "exact")
                self.assertIn(row[1], {"usable", "high"})
                self.assertGreaterEqual(int(row[2]), 10)
                # 84/140 = 60%, 28/140 = 20%
                self.assertAlmostEqual(float(row[3]), 60.0, delta=0.5)
                self.assertAlmostEqual(float(row[4]), 20.0, delta=0.5)
            finally:
                conn.close()

            hit = lookup_pct_variance(
                payer="DELTA DENTAL OF KS", ada_code="D1110", db_path=db
            )
            self.assertIsNotNone(hit)
            assert hit is not None
            self.assertEqual(hit.get("adaCode"), "D1110")
            self.assertAlmostEqual(float(hit.get("paidPctMedian") or 0), 60.0, delta=0.5)


if __name__ == "__main__":
    unittest.main()
