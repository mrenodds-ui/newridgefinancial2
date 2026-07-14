"""HAL-10585 unified InsCo×ADA spine + treatment-planning fallback."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from softdent_insco_ada_pct_variance import build_insco_ada_pct_variance, ensure_pct_variance_schema
from softdent_insco_ada_probabilistic import (
    build_insco_ada_probabilistic_estimates,
    ensure_probabilistic_schema,
)
from softdent_insco_ada_spine import collect_spine_samples, normalize_cdt
from softdent_odbc_extract import ensure_sd_schema
from softdent_treatment_planning import (
    ensure_treatment_planning_schema,
    format_treatment_estimate_reply,
    lookup_treatment_estimate,
)


def _seed(db: Path) -> None:
    conn = sqlite3.connect(str(db))
    try:
        ensure_sd_schema(conn)
        ensure_probabilistic_schema(conn)
        ensure_pct_variance_schema(conn)
        ensure_treatment_planning_schema(conn)
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
            ) VALUES ('', '300300', 1, 'DELTA DENTAL OF KS', 'now')
            """
        )
        rn = 1
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
                        f"s{rn}",
                        rn,
                        "300300",
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
    finally:
        conn.close()


class InscoAdaSpineHal10585Tests(unittest.TestCase):
    def test_normalize_cdt_excludes_internals(self) -> None:
        self.assertEqual(normalize_cdt("1110"), "D1110")
        self.assertEqual(normalize_cdt("220"), "D0220")
        self.assertEqual(normalize_cdt("12"), "")
        self.assertEqual(normalize_cdt("8888"), "")
        self.assertEqual(normalize_cdt("11.93"), "")

    def test_same_spine_feeds_dollar_and_pct(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "analytics.db"
            _seed(db)
            conn = sqlite3.connect(str(db))
            try:
                samples = collect_spine_samples(conn, years=5)
                self.assertTrue(samples.get("ok"))
                self.assertGreaterEqual(int(samples.get("episodeCount") or 0), 10)
                dollar = build_insco_ada_probabilistic_estimates(conn, years=5)
                pct = build_insco_ada_pct_variance(conn, years=5)
                self.assertTrue(dollar.get("ok"))
                self.assertTrue(pct.get("ok"))
                self.assertEqual(dollar.get("spineEpisodes"), pct.get("spineEpisodes"))
                self.assertEqual(dollar.get("periodStart"), pct.get("periodStart"))
            finally:
                conn.close()

            est = lookup_treatment_estimate(
                payer="DELTA DENTAL OF KS", ada_code="D1110", db_path=db
            )
            self.assertTrue(est.get("ok"))
            self.assertTrue(est.get("found"))
            self.assertEqual(est.get("source"), "ledger_episode_5yr")
            self.assertTrue(est.get("sufficient"))
            payload = est.get("estimate") or {}
            self.assertAlmostEqual(float(payload.get("paidAmountAvg") or 0), 84.0, delta=0.5)
            self.assertAlmostEqual(float(payload.get("writeOffAvg") or 0), 28.0, delta=0.5)
            self.assertAlmostEqual(float(payload.get("paidPctMedian") or 0), 60.0, delta=0.5)
            reply = format_treatment_estimate_reply(est)
            self.assertIn("ledger_episode_5yr", reply)
            self.assertNotIn("$0.00", reply.split("pays")[0] if False else reply)


if __name__ == "__main__":
    unittest.main()
