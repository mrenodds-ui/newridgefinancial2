"""HAL-10582 InsCo × ADA probabilistic estimates from ledger + coverage."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from softdent_insco_ada_probabilistic import (
    CREDIBILITY,
    build_insco_ada_probabilistic_estimates,
    ensure_probabilistic_schema,
    format_probabilistic_estimate_reply,
    lookup_probabilistic_estimate,
)
from softdent_odbc_extract import ensure_sd_schema


def _seed(db: Path) -> None:
    conn = sqlite3.connect(str(db))
    try:
        ensure_sd_schema(conn)
        ensure_probabilistic_schema(conn)
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
            ) VALUES ('', '100100', 1, 'DELTA DENTAL OF KS', 'now')
            """
        )
        rows: list[tuple] = []
        rn = 1
        for i in range(12):
            day = f"2026-02-{(i % 28) + 1:02d}"
            rows.append(("100100", day, "1110", 137.0, None, None, rn))
            rn += 1
            rows.append(("100100", day, "51", None, -35.0, None, rn))
            rn += 1
            rows.append(("100100", day, "2", None, None, 70.0, rn))
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
                          '2026-01-01', '2026-07-01', 'now')
                """,
                (
                    f"s{row_n}",
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


class InscoAdaProbabilisticHal10582Tests(unittest.TestCase):
    def test_exact_publish_and_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "analytics.db"
            _seed(db)
            conn = sqlite3.connect(str(db))
            try:
                built = build_insco_ada_probabilistic_estimates(
                    conn, period_start="2026-01-01", period_end="2026-07-01"
                )
                self.assertTrue(built.get("ok"))
                self.assertGreaterEqual(int(built.get("publishedCells") or 0), 1)
                row = conn.execute(
                    """
                    SELECT tier, credibility, sample_size, paid_avg, write_off_avg
                    FROM insco_ada_probabilistic_estimates
                    WHERE ada_code='D1110' AND tier='exact'
                    """
                ).fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(row[0], "exact")
                self.assertIn(row[1], {"usable", "high"})
                self.assertGreaterEqual(int(row[2]), CREDIBILITY["exact_publish_n"])
            finally:
                conn.close()
            est = lookup_probabilistic_estimate(payer="Delta", ada_code="1110", db_path=db)
            self.assertIsNotNone(est)
            text = format_probabilistic_estimate_reply(est, payer="Delta", ada="D1110")
            self.assertIn("D1110", text)
            self.assertIn("badge=", text)

    def test_credibility_constants_documented(self) -> None:
        self.assertEqual(CREDIBILITY["exact_publish_n"], 10)
        self.assertEqual(CREDIBILITY["exact_high_n"], 30)
        self.assertEqual(CREDIBILITY["inferred_publish_n"], 30)
        self.assertGreaterEqual(CREDIBILITY["recommended_history_months"], 24)


if __name__ == "__main__":
    unittest.main()
