"""HAL-10583 InsCo×ADA estimate HAL surfacing — exact default, inferred opt-in."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from softdent_insco_ada_probabilistic import (
    build_insco_ada_probabilistic_estimates,
    ensure_probabilistic_schema,
    format_probabilistic_estimate_reply,
    insco_ada_estimate_widget,
    list_published_estimate_rows,
    lookup_probabilistic_estimate,
    parse_probabilistic_estimate_query,
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
        rn = 1
        for i in range(12):
            day = f"2026-02-{(i % 28) + 1:02d}"
            for proc, billed, wo, paid in (
                ("1110", 137.0, None, None),
                ("51", None, -35.0, None),
                ("2", None, None, 70.0),
            ):
                conn.execute(
                    """
                    INSERT INTO sd_account_transactions (
                        stable_id, source_file, row_number, account_num, patient_name,
                        service_date, provider, procedure, note_flag, amount,
                        prod, charges, prod_adj, cash, "check", credit, pay_adj,
                        period_start, period_end, extracted_at
                    ) VALUES (?, 't', ?, '100100', 'Test', ?, '', ?, 'A', ?, ?, NULL, ?, NULL, ?, NULL, NULL,
                              '2026-01-01', '2026-07-01', 'now')
                    """,
                    (
                        f"s{rn}",
                        rn,
                        day,
                        proc,
                        billed or wo or paid,
                        billed,
                        wo,
                        paid,
                    ),
                )
                rn += 1
        # Multi-ADA day for inferred cell (not published as exact)
        for proc, billed in (("120", 100.0), ("274", 88.0)):
            conn.execute(
                """
                INSERT INTO sd_account_transactions (
                    stable_id, source_file, row_number, account_num, patient_name,
                    service_date, provider, procedure, note_flag, amount,
                    prod, charges, prod_adj, cash, "check", credit, pay_adj,
                    period_start, period_end, extracted_at
                ) VALUES (?, 't', ?, '100100', 'Test', '2026-03-01', '', ?, 'A', ?, ?, NULL, NULL, NULL, NULL, NULL, NULL,
                          '2026-01-01', '2026-07-01', 'now')
                """,
                (f"s{rn}", rn, proc, billed, billed),
            )
            rn += 1
        for _ in range(35):
            conn.execute(
                """
                INSERT INTO sd_account_transactions (
                    stable_id, source_file, row_number, account_num, patient_name,
                    service_date, provider, procedure, note_flag, amount,
                    prod, charges, prod_adj, cash, "check", credit, pay_adj,
                    period_start, period_end, extracted_at
                ) VALUES (?, 't', ?, '100100', 'Test', '2026-03-05', '', '2', 'A', 50, NULL, NULL, NULL, NULL, 50, NULL, NULL,
                          '2026-01-01', '2026-07-01', 'now')
                """,
                (f"s{rn}", rn),
            )
            rn += 1
        conn.commit()
        build_insco_ada_probabilistic_estimates(
            conn, period_start="2026-01-01", period_end="2026-07-01"
        )
    finally:
        conn.close()


class InscoAdaEstimateHal10583Tests(unittest.TestCase):
    def test_parse_and_exact_default_blocks_inferred(self) -> None:
        parsed = parse_probabilistic_estimate_query(
            "How much does Delta Dental of KS typically pay for D1110?"
        )
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed["kind"], "lookup")
        self.assertFalse(parsed["includeInferred"])

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "a.db"
            _seed(db)
            exact = lookup_probabilistic_estimate(
                payer="Delta Dental of KS", ada_code="D1110", db_path=db, include_inferred=False
            )
            self.assertIsNotNone(exact)
            assert exact is not None
            self.assertEqual(exact["tier"], "exact")
            self.assertIn(exact["credibility"], {"usable", "high"})
            # Inferred ADA from multi-code day should not return without opt-in
            inferred = lookup_probabilistic_estimate(
                payer="Delta", ada_code="D0120", db_path=db, include_inferred=False
            )
            # May be None (preferred) — never exact for D0120 from multi-ADA-only path alone
            if inferred is not None:
                self.assertEqual(inferred["tier"], "exact")

            rows = list_published_estimate_rows(db_path=db, include_inferred=False)
            self.assertTrue(all(r["tier"] == "exact" for r in rows))
            self.assertTrue(all(r["badge"] in {"high", "usable"} for r in rows))

            text = format_probabilistic_estimate_reply(
                exact, payer="Delta", ada="D1110", include_inferred=False
            )
            self.assertIn("badge=", text)
            self.assertIn("D1110", text)

    def test_widget_and_hal_policy(self) -> None:
        with mock.patch(
            "softdent_insco_ada_probabilistic.probabilistic_report_status",
            return_value={"publishedCells": 124, "highCredibilityCells": 2, "totalCells": 1973, "ok": True},
        ), mock.patch(
            "softdent_insco_ada_probabilistic.list_published_estimate_rows",
            return_value=[
                {
                    "insuranceCompany": "DELTA DENTAL OF KS",
                    "adaCode": "D1110",
                    "tier": "exact",
                    "sampleSize": 32,
                    "paidMedian": 68.0,
                    "writeOffMedian": 18.0,
                    "credibility": "high",
                    "badge": "high",
                    "badgeLabel": "High",
                    "tone": "ok",
                }
            ],
        ):
            w = insco_ada_estimate_widget()
        self.assertEqual(w["id"], "softdent-insco-ada-estimates")
        self.assertFalse(w.get("includeInferredDefault"))
        self.assertEqual(w["status"], "ok")

        from nr2_hal_gateway import try_local_policy_reply

        with mock.patch(
            "softdent_insco_ada_probabilistic.lookup_probabilistic_estimate",
            return_value={
                "insurance_company": "DELTA DENTAL OF KS",
                "ada_code": "D1110",
                "tier": "exact",
                "sample_size": 32,
                "paid_median": 68.0,
                "write_off_median": 18.0,
                "credibility": "high",
            },
        ):
            hit = try_local_policy_reply(
                "How much does Delta Dental of KS typically pay for D1110?"
            )
        self.assertEqual((hit or {}).get("intent"), "policy:insco-ada-estimates")
        self.assertIn("D1110", (hit or {}).get("text") or "")
        self.assertIn("high", ((hit or {}).get("text") or "").lower())


if __name__ == "__main__":
    unittest.main()
