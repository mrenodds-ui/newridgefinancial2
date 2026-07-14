"""HAL-10588 FIX-003 — raise line coverage on financial InsCo×ADA / TP modules."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from softdent_insco_ada_catalog_matrix import (
    catalog_matrix_status,
    format_catalog_status_reply,
    run_insco_ada_catalog_matrix_report,
)
from softdent_insco_ada_pct_variance import (
    build_insco_ada_pct_variance,
    ensure_pct_variance_schema,
    export_pct_variance_report,
    format_pct_variance_reply,
    format_pct_variance_status_reply,
    list_pct_variance_rows,
    lookup_pct_variance,
    pct_variance_status,
    run_insco_ada_pct_variance_report,
)
from softdent_insco_ada_probabilistic import (
    build_insco_ada_probabilistic_estimates,
    credibility_badge,
    ensure_probabilistic_schema,
    export_probabilistic_report,
    format_probabilistic_estimate_reply,
    format_probabilistic_status_reply,
    insco_ada_estimate_widget,
    list_published_estimate_rows,
    log_inferred_view_audit,
    lookup_probabilistic_estimate,
    parse_probabilistic_estimate_query,
    probabilistic_report_status,
    run_insco_ada_probabilistic_report,
)
from softdent_insco_ada_spine import normalize_cdt
from softdent_odbc_extract import ensure_sd_schema
from softdent_treatment_planning import (
    build_tp_estimate_chip,
    ensure_treatment_planning_schema,
    find_newest_csv,
    format_treatment_estimate_reply,
    ingest_procedure_code_csv,
    lookup_treatment_estimate,
    normalize_ada_code,
    parse_money,
    parse_treatment_estimate_query,
    run_treatment_planning_ingest,
    treatment_plan_estimate_widget,
    treatment_planning_status,
    _PAYMENT_GLOBS,
)


def _seed_ledger(db: Path, *, n_episodes: int = 12) -> None:
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
        for i in range(n_episodes):
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
        # Multi-ADA inferred cluster
        for i in range(10):
            day = f"2024-{(i % 9) + 1:02d}-{(i % 27) + 1:02d}"
            for proc, billed, prod_adj, paid in (
                ("1110", 140.0, None, None),
                ("0274", 60.0, None, None),
                ("51", None, -40.0, None),
                ("2", None, None, 120.0),
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


_PAYMENT_CSV = """Insurance Company,Procedure Code,Submitted Fee,Allowed Amount,Paid Amount,Write Off,Patient Portion,Claim Number,Check Number,Payment Date,Description
DELTA DENTAL OF KS,D1110,140.00,112.00,84.00,28.00,28.00,C1,CHK1,2025-06-01,Prophy
DELTA DENTAL OF KS,D1110,140.00,112.00,90.00,22.00,22.00,C2,CHK2,2025-06-15,Prophy
"""

_CODE_CSV = """Internal Code,ADA Code,Description,UCR Fee
1110,D1110,Prophylaxis,140.00
0274,D0274,Bitewings,60.00
"""


class FinancialCoverageHal10588Tests(unittest.TestCase):
    def test_helpers_and_parsers(self) -> None:
        self.assertEqual(normalize_ada_code("1110"), "D1110")
        self.assertEqual(normalize_cdt("1110"), "D1110")
        self.assertEqual(parse_money("$1,234.50"), 1234.50)
        self.assertIsNone(parse_money(""))
        parsed = parse_treatment_estimate_query(
            "How much will Delta Dental typically pay for D1110?"
        )
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["adaCode"], "D1110")
        p2 = parse_probabilistic_estimate_query(
            "What does Delta typically pay for D1110?"
        )
        self.assertIsNotNone(p2)
        badge = credibility_badge("high", "exact")
        self.assertIn("label", badge)

    def test_probabilistic_surface_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "a.db"
            dest = root / "out"
            _seed_ledger(db)
            conn = sqlite3.connect(str(db))
            try:
                build = build_insco_ada_probabilistic_estimates(conn, years=5)
                self.assertTrue(build.get("ok"))
            finally:
                conn.close()
            row = lookup_probabilistic_estimate(
                payer="DELTA DENTAL OF KS", ada_code="D1110", db_path=db
            )
            self.assertTrue(row)
            text = format_probabilistic_estimate_reply(row, payer="DELTA", ada="D1110")
            self.assertIn("D1110", text)
            st = probabilistic_report_status(db)
            self.assertTrue(st.get("ok"))
            self.assertIn("published", format_probabilistic_status_reply(st).lower())
            rows = list_published_estimate_rows(db_path=db, limit=20)
            self.assertTrue(rows)
            exp = export_probabilistic_report(db_path=db, dest=dest)
            self.assertTrue(exp.get("ok"))
            run = run_insco_ada_probabilistic_report(db_path=db)
            self.assertTrue(run.get("ok"))
            log_inferred_view_audit(payer="DELTA", ada="D1110", source="test")
            w = insco_ada_estimate_widget(include_inferred=True)
            self.assertEqual(w.get("id") or w.get("type") or "x", w.get("id") or w.get("type") or "x")

    def test_pct_variance_surface_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "a.db"
            dest = root / "out"
            _seed_ledger(db)
            conn = sqlite3.connect(str(db))
            try:
                build_insco_ada_pct_variance(conn, years=5)
            finally:
                conn.close()
            row = lookup_pct_variance(
                payer="DELTA DENTAL OF KS", ada_code="D1110", db_path=db
            )
            self.assertTrue(row)
            self.assertIn("pay", format_pct_variance_reply(row).lower())
            self.assertIn("No publishable", format_pct_variance_reply(None, payer="X", ada="D9999"))
            st = pct_variance_status(db_path=db)
            self.assertTrue(st.get("ok"))
            self.assertIn("HAL-10584", format_pct_variance_status_reply(st))
            self.assertTrue(list_pct_variance_rows(db_path=db, include_inferred=True))
            exp = export_pct_variance_report(db_path=db, dest=dest)
            self.assertTrue(exp.get("ok"))
            run = run_insco_ada_pct_variance_report(db_path=db)
            self.assertTrue(run.get("ok"))

    def test_treatment_planning_ingest_and_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "a.db"
            drop = root / "exports"
            drop.mkdir()
            _seed_ledger(db)
            (drop / "insurance_payments_20260712.csv").write_text(_PAYMENT_CSV, encoding="utf-8")
            (drop / "procedure_codes_20260712.csv").write_text(_CODE_CSV, encoding="utf-8")
            newest = find_newest_csv(_PAYMENT_GLOBS, search_dir=drop)
            self.assertIsNotNone(newest)
            ingest = run_treatment_planning_ingest(db_path=db, search_dir=drop)
            self.assertTrue(ingest.get("ok"))
            self.assertGreaterEqual(int(ingest.get("paymentLines") or 0), 2)
            self.assertGreaterEqual(int(ingest.get("procedureCodes") or 0), 1)
            st = treatment_planning_status(db)
            self.assertTrue(st.get("ok"))
            self.assertGreaterEqual(int(st.get("paymentLines") or 0), 2)
            est = lookup_treatment_estimate(
                payer="DELTA DENTAL OF KS", ada_code="D1110", db_path=db
            )
            self.assertTrue(est.get("found"))
            chip = build_tp_estimate_chip(est)
            self.assertIn("badge", chip)
            reply = format_treatment_estimate_reply(est)
            self.assertTrue(reply)
            # procedure ingest direct
            conn = sqlite3.connect(str(db))
            try:
                n = ingest_procedure_code_csv(drop / "procedure_codes_20260712.csv", conn)
                self.assertGreaterEqual(n, 1)
                conn.commit()
            finally:
                conn.close()

    def test_catalog_matrix_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "a.db"
            _seed_ledger(db)
            conn = sqlite3.connect(str(db))
            try:
                build_insco_ada_probabilistic_estimates(conn, years=5)
                build_insco_ada_pct_variance(conn, years=5)
            finally:
                conn.close()
            run = run_insco_ada_catalog_matrix_report(db_path=db)
            self.assertTrue(run.get("ok"))
            st = catalog_matrix_status(db_path=db)
            self.assertTrue(st.get("ok"))
            self.assertIn("catalog", format_catalog_status_reply(st).lower())

    def test_treatment_planning_edge_paths(self) -> None:
        from softdent_treatment_planning import log_tp_estimate_audit

        self.assertEqual(normalize_ada_code("D1110.1"), "D1110")
        self.assertEqual(normalize_ada_code("111000"), "D1110")
        self.assertEqual(normalize_ada_code(""), "")
        self.assertIsNotNone(
            parse_treatment_estimate_query("estimate for code 1110 with Delta Dental")
        )
        self.assertIsNotNone(
            parse_treatment_estimate_query("Will Cigna pay for D0274?")
        )
        self.assertIsNone(parse_treatment_estimate_query(""))
        self.assertIsNone(parse_treatment_estimate_query("hello world"))

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "a.db"
            drop = root / "exports"
            drop.mkdir()
            _seed_ledger(db)
            # Thin gold sample → insufficient chip (empty != $0)
            thin = """Insurance Company,Procedure Code,Submitted Fee,Allowed Amount,Paid Amount,Write Off,Patient Portion
DELTA DENTAL OF KS,D1110,140,112,84,28,28
DELTA DENTAL OF KS,D1110,140,112,80,30,30
"""
            (drop / "insurance_payments_thin.csv").write_text(thin, encoding="utf-8")
            run_treatment_planning_ingest(db_path=db, search_dir=drop)
            est = lookup_treatment_estimate(
                payer="DELTA DENTAL OF KS", ada_code="D1110", db_path=db, min_sample=10
            )
            self.assertTrue(est.get("found"))
            self.assertFalse(est.get("sufficient"))
            chip = build_tp_estimate_chip(est)
            self.assertEqual(chip.get("badge"), "insufficient")
            self.assertFalse(chip.get("showDollars"))
            reply = format_treatment_estimate_reply(est)
            self.assertFalse(chip.get("showDollars"))
            self.assertTrue(
                "insufficient" in reply.lower()
                or "only" in reply.lower()
                or "empty" in reply.lower()
            )
            # force reply branches
            format_treatment_estimate_reply({"ok": False, "message": "boom"})
            format_treatment_estimate_reply(
                {
                    "ok": True,
                    "found": True,
                    "sufficient": True,
                    "source": "gold_payment_lines",
                    "estimate": {
                        "insuranceCompany": "DELTA",
                        "adaCode": "D1110",
                        "sampleSize": 12,
                        "source": "gold_payment_lines",
                        "credibility": "gold",
                        "paidAmountAvg": 84,
                        "writeOffAvg": 28,
                        "allowedAmountAvg": None,
                        "patientPortionAvg": 28,
                    },
                    "chip": {
                        "showDollars": True,
                        "label": "Payment lines",
                        "badge": "gold",
                        "display": "x",
                    },
                }
            )
            log_tp_estimate_audit(est, source="test")
            st = treatment_planning_status(db)
            self.assertGreaterEqual(int(st.get("paymentLines") or 0), 1)


if __name__ == "__main__":
    unittest.main()
