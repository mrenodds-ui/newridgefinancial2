"""HAL-10587 treatment-plan estimate UX chips (catalog-enriched)."""

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
from softdent_odbc_extract import ensure_sd_schema
from softdent_treatment_planning import (
    build_tp_estimate_chip,
    ensure_treatment_planning_schema,
    format_treatment_estimate_reply,
    lookup_treatment_estimate,
    treatment_plan_estimate_widget,
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
            ) VALUES ('', '500500', 1, 'DELTA DENTAL OF KS', 'now')
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
                        f"t{rn}",
                        rn,
                        "500500",
                        day,
                        proc,
                        billed or prod_adj or paid,
                        billed,
                        prod_adj,
                        paid,
                    ),
                )
                rn += 1
        # Thin sample → insufficient catalog cell
        for i in range(2):
            day = f"2024-08-{i + 1:02d}"
            for proc, billed, prod_adj, paid in (
                ("2740", 1100.0, None, None),
                ("51", None, -100.0, None),
                ("2", None, None, 700.0),
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
                        f"t{rn}",
                        rn,
                        "500500",
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


class TreatmentPlanningHal10587Tests(unittest.TestCase):
    def test_chip_exact_and_insufficient(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "analytics.db"
            _seed(db)
            conn = sqlite3.connect(str(db))
            try:
                build_insco_ada_probabilistic_estimates(conn, years=5)
                build_insco_ada_pct_variance(conn, years=5)
            finally:
                conn.close()

            est = lookup_treatment_estimate(
                payer="DELTA DENTAL OF KS", ada_code="D1110", db_path=db
            )
            self.assertTrue(est.get("sufficient"))
            chip = est.get("chip") or build_tp_estimate_chip(est)
            self.assertTrue(chip.get("showDollars"))
            self.assertIn(chip.get("badge"), {"high", "usable"})
            self.assertNotIn("$0.00", str(chip.get("display")))
            reply = format_treatment_estimate_reply(est)
            self.assertIn("Treatment plan estimate", reply)

            thin = lookup_treatment_estimate(
                payer="DELTA DENTAL OF KS", ada_code="D2740", db_path=db
            )
            thin_chip = thin.get("chip") or build_tp_estimate_chip(thin)
            self.assertFalse(thin_chip.get("showDollars"))
            self.assertEqual(thin_chip.get("badge"), "insufficient")
            self.assertIsNone(thin_chip.get("paidMedian"))
            thin_reply = format_treatment_estimate_reply(thin)
            self.assertIn("empty != $0", thin_reply)
            self.assertNotRegex(thin_reply, r"pays \$0\.00")

    def test_widget_shape(self) -> None:
        w = treatment_plan_estimate_widget()
        self.assertEqual(w.get("id"), "softdent-tp-estimate-chips")
        self.assertEqual(w.get("def"), "HAL-10587")
        self.assertIn("halChips", w)


if __name__ == "__main__":
    unittest.main()
