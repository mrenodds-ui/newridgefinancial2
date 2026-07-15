"""HAL-10603 — Honesty CI gate: fail if TP/widgets regress null → $0.00.

Moonshot consult: MOONSHOT_CONFIRM_HAL10601_2026-07-13.md
Does not change treatment-planning lookup logic — tests/CI only (plus BUILD_ID).
empty != $0. No SoftDent write-back. No invented gold.
"""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from apex_backend import BUILD_ID, _money_kpi
from softdent_carrier_alias import ensure_carrier_alias_schema, reconcile_carrier_aliases
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
from softdent_print_preview_audit import print_preview_audit_widget
from softdent_treatment_planning import (
    build_tp_estimate_chip,
    lookup_treatment_estimate,
    treatment_planning_status,
)
from ui_honesty_policy import (
    SOURCE_GOLD_PAYMENT_LINES,
    audit_ui_honesty_surfaces,
    enforce_empty_not_zero,
    format_display_money,
    ui_honesty_widget,
)

DEF_ID = "HAL-10603"
PACKAGE_BUILD_ID = "hal-10603"


def assert_no_fake_zero_dollars(chip_or_result: dict, *, ctx: str = "") -> None:
    """CI gate helper — fail hard on null→$0 honesty regressions."""
    chip = chip_or_result.get("chip") if "chip" in chip_or_result else chip_or_result
    if not isinstance(chip, dict):
        raise AssertionError(f"{ctx}: expected chip/result dict")
    if chip.get("emptyIsNotZero") is False:
        raise AssertionError(f"{ctx}: emptyIsNotZero flipped to false")
    display = str(chip.get("display") or "")
    if chip.get("showDollars") is False and "$0.00" in display:
        raise AssertionError(f"{ctx}: showDollars=false but display has $0.00: {display!r}")
    paid = chip.get("paidMedian")
    if chip.get("showDollars") is False and paid == 0.0:
        raise AssertionError(f"{ctx}: showDollars=false but paidMedian is numeric 0.0")


def _seed_tp_alias_db(db: Path) -> None:
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
                        f"h{rn}",
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


class HonestyCiGateHal10603Tests(unittest.TestCase):
    """Honesty CI gate — null must never become $0.00 for empty/pending paths."""

    def test_build_id_coupled(self) -> None:
        self.assertEqual(PACKAGE_BUILD_ID, "hal-10603")
        self.assertEqual(BUILD_ID, "hal-10631")

    def test_empty_is_not_zero_policy_surfaces(self) -> None:
        for value in (None, "", "null", "n/a"):
            out = enforce_empty_not_zero(value, source_tag=SOURCE_GOLD_PAYMENT_LINES)
            self.assertTrue(out.get("emptyIsNotZero"))
            self.assertFalse(out.get("showDollars"))
            self.assertNotEqual(out.get("display"), "$0.00")
            self.assertIn(out.get("display"), {"—", "No data", "unknown"})

    def test_explicit_zero_still_allowed(self) -> None:
        out = enforce_empty_not_zero(0.0, source_tag="kpi")
        self.assertEqual(out.get("display"), "$0.00")
        self.assertTrue(out.get("showDollars"))

    def test_format_display_money_null_not_zero(self) -> None:
        self.assertEqual(format_display_money(None, source_tag=SOURCE_GOLD_PAYMENT_LINES), "—")
        self.assertNotEqual(format_display_money(None, source_tag="kpi"), "$0.00")

    def test_tp_chip_pending_alias_never_shows_zero_dollars(self) -> None:
        chip = build_tp_estimate_chip(
            {
                "ok": True,
                "found": True,
                "sufficient": False,
                "credibility": "insufficient",
                "sampleSize": 0,
                "source": "carrier_alias_pending",
                "payer": "ANTHEM - 188",
                "adaCode": "D1110",
                "estimate": {
                    "insuranceCompany": "ANTHEM - 188",
                    "adaCode": "D1110",
                    "paidAmountAvg": None,
                    "sampleSize": 0,
                    "credibility": "insufficient",
                    "source": "carrier_alias_pending",
                },
                "blockedPending": True,
            }
        )
        assert_no_fake_zero_dollars(chip, ctx="pending_alias_chip")
        self.assertFalse(chip.get("showDollars"))
        self.assertNotIn("$0.00", str(chip.get("display") or ""))

    def test_tp_chip_via_alias_null_paid_never_zero(self) -> None:
        chip = build_tp_estimate_chip(
            {
                "ok": True,
                "found": True,
                "sufficient": False,
                "credibility": "insufficient",
                "sampleSize": 3,
                "source": "ledger_episode_5yr_via_alias",
                "viaAlias": True,
                "payer": "Aetna Healthcare",
                "adaCode": "D1110",
                "estimate": {
                    "insuranceCompany": "Aetna Healthcare",
                    "adaCode": "D1110",
                    "paidAmountAvg": None,
                    "sampleSize": 3,
                    "credibility": "insufficient",
                    "source": "ledger_episode_5yr_via_alias",
                    "spineCarrierName": "AETNA",
                },
            }
        )
        assert_no_fake_zero_dollars(chip, ctx="via_alias_null_paid")
        self.assertIsNone(chip.get("paidMedian"))

    def test_tp_lookup_fixture_probes_honesty(self) -> None:
        """Fixture equivalents of live aetnaHealthcare / anthem188 probes."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "honesty.db"
            _seed_tp_alias_db(db)
            csv_path = root / "companies.csv"
            csv_path.write_text(
                "company_name,status,record_number\n"
                '"AETNA","likely_active","1"\n'
                '"Aetna Healthcare","likely_active","302"\n'
                '"ANTHEM - 188","likely_active","604"\n',
                encoding="utf-8",
            )
            ingest_insurance_companies_csv(
                csv_path=csv_path, db_path=db, copy_to_exports=False
            )
            reconcile_carrier_aliases(db_path=db, dest=root)
            # Force pending for Anthem-188 (manual band)
            conn = sqlite3.connect(str(db))
            conn.execute(
                """
                INSERT OR REPLACE INTO carrier_alias (
                    spine_carrier_name, master_company_id, master_company_name,
                    match_score, confidence, review_status, match_method, created_at_utc
                ) VALUES ('ANTHEM - 1115', '604', 'ANTHEM - 188', 84.5, 'manual', 'pending',
                          'fuzzy_blocked_jw', 'now')
                """
            )
            conn.commit()
            conn.close()

            aetna = lookup_treatment_estimate(
                payer="Aetna Healthcare", ada_code="D2391", db_path=db
            )
            self.assertTrue(aetna.get("found"))
            self.assertTrue(aetna.get("viaAlias"))
            self.assertEqual(aetna.get("source"), "ledger_episode_5yr_via_alias")
            est = aetna.get("estimate") or {}
            self.assertIsNotNone(est.get("paidAmountAvg"))
            self.assertNotEqual(est.get("paidAmountAvg"), 0)
            assert_no_fake_zero_dollars(aetna, ctx="aetnaHealthcare_D2391")
            self.assertTrue((aetna.get("chip") or {}).get("showDollars"))

            pending = lookup_treatment_estimate(
                payer="ANTHEM - 188", ada_code="D1110", db_path=db
            )
            self.assertTrue(pending.get("blockedPending"))
            self.assertEqual(pending.get("source"), "carrier_alias_pending")
            pend_est = pending.get("estimate") or {}
            self.assertIsNone(pend_est.get("paidAmountAvg"))
            self.assertNotEqual(pend_est.get("paidAmountAvg"), 0.0)
            assert_no_fake_zero_dollars(pending, ctx="anthem188_pending_D1110")
            self.assertFalse((pending.get("chip") or {}).get("showDollars"))
            self.assertNotIn("$0.00", str((pending.get("chip") or {}).get("display") or ""))

    def test_money_kpi_null_not_zero(self) -> None:
        kpi = _money_kpi("x", "Test", None, hint="hint")
        self.assertNotEqual(kpi.get("value"), "$0.00")
        self.assertTrue(kpi.get("emptyIsNotZero"))

    def test_widgets_honesty_markers(self) -> None:
        for w in (ui_honesty_widget(), print_preview_audit_widget()):
            self.assertTrue(w.get("emptyIsNotZero"), msg=str(w.get("id")))
        st = treatment_planning_status()
        if st.get("ok"):
            self.assertTrue(st.get("emptyIsNotZero") or st.get("tpCodeUsesCarrierAlias"))

    def test_audit_ui_honesty_surfaces_pass(self) -> None:
        result = audit_ui_honesty_surfaces()
        self.assertTrue(result.get("ok"))
        self.assertEqual(int(result.get("failCount") or 0), 0)


if __name__ == "__main__":
    unittest.main()
