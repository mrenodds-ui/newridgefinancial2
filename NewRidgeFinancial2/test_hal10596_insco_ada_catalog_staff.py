"""HAL-10596 — InsCo×ADA staff catalog CSV + cents + rebuild coupling."""

from __future__ import annotations

import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path

from apex_backend import BUILD_ID
from softdent_insco_ada_catalog_matrix import (
    PACKAGE_BUILD_ID,
    export_catalog_matrix_report,
    insco_ada_catalog_widget,
    list_catalog_matrix_rows,
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
        conn.commit()
        build_insco_ada_probabilistic_estimates(conn)
        build_insco_ada_pct_variance(conn, years=5)
        conn.commit()
    finally:
        conn.close()


class InscoAdaCatalogHal10596Tests(unittest.TestCase):
    def test_build_id_coupled(self) -> None:
        self.assertEqual(PACKAGE_BUILD_ID, "hal-10599")
        self.assertEqual(BUILD_ID, "hal-10608")

    def test_csv_row_count_matches_cells_and_cents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            db = dest / "analytics.db"
            _seed(db)
            export = export_catalog_matrix_report(db_path=db, dest=dest)
            self.assertTrue(export.get("ok"))
            csv_path = Path(export["csvPath"])
            self.assertTrue(csv_path.is_file())
            with csv_path.open(encoding="utf-8", newline="") as fh:
                rows = list(csv.DictReader(fh))
            cells = list_catalog_matrix_rows(
                db_path=db, include_insufficient=True, include_inferred=True, limit=100000
            )
            # Staff CSV is spine rows expanded with company-master pad (≥ spine).
            self.assertGreaterEqual(len(rows), len(cells))
            self.assertEqual(len(rows), export.get("cellCount"))
            self.assertIn("paidMedianCents", rows[0])
            self.assertIn("source", rows[0])
            # insufficient with samples keep real amounts; never invent $0 for empty
            insuff = [r for r in cells if r.get("credibility") == "insufficient"]
            for r in insuff:
                if int(r.get("sampleSize") or 0) <= 0:
                    self.assertIsNone(r.get("paidMedian"))
                    self.assertIsNone(r.get("paidMedianCents"))
            for r in rows:
                if r.get("credibility") == "no_settlement":
                    self.assertEqual(r.get("paidMedian") or "", "")
                    self.assertEqual(r.get("paidMedianCents") or "", "")

    def test_widget_exposes_csv_and_uncovered(self) -> None:
        w = insco_ada_catalog_widget()
        self.assertEqual(w.get("packageBuildId"), "hal-10599")
        self.assertIn("uncoveredCount", w)
        self.assertIn("csvPath", w)
        self.assertTrue(w.get("emptyIsNotZero"))
        self.assertIn("HAL-10599", str(w.get("label") or ""))


if __name__ == "__main__":
    unittest.main()
