"""HAL-10580 Outstanding Claims by Carrier Bridge tests."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from softdent_outstanding_claims_bridge import (
    GAP_PAYER_ATTRIBUTION,
    aggregate_sd_claims_by_carrier,
    build_outstanding_claims_by_carrier_bridge,
    find_account_aging_export,
    format_outstanding_claims_hal_reply,
    parse_account_aging_export,
    reconcile_claims_to_aging,
)
from softdent_transaction_extract import resolve_account_transactions_db


def _write_aging_csv(path: Path, *, ar_total: float, ins_total: float) -> None:
    path.write_text(
        "\n".join(
            [
                "ACCOUNT AGING REPORT,,,,,,,,,,,,",
                "Acct ID,Account Name,Balance,Ins Amt,Amt Due,Prepay,Current,30 Day,60 Day,90 Day,Date LP,Amnt LP,CC Plan",
                f'100,"Test, A","${ar_total:,.2f}","${ins_total:,.2f}","${ar_total:,.2f}",$0.00,"${ar_total:,.2f}",$0.00,$0.00,$0.00,1/1/2026,$10.00,$0.00',
                ",Total (Net 30)," + f'"${ar_total:,.2f}"' + ",100%,,Receivables for all amounts NOT on budget plans.,,,,,,,",
                ',, "' + f"${ar_total:,.2f}" + '",100%,**       ,TRUE receivables.,,,,,,,',
                "Outstanding Insurance Breakdown,,,,,,,,,,,,",
                f",Total," + f'"${ins_total:,.2f}"' + ",100%,**       ,,,,,,,,",
                f",Total outstanding income," + f'"${ar_total:,.2f}"' + ",,,,,,,,,,",
            ]
        ),
        encoding="utf-8",
    )


def _seed_claims_db(path: Path, rows: list[tuple]) -> None:
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE sd_claims (
            claim_id TEXT NOT NULL,
            patient_name TEXT,
            payer TEXT,
            service_date TEXT,
            claim_amount REAL,
            claim_status TEXT,
            practice_id TEXT NOT NULL DEFAULT '',
            extracted_at TEXT,
            total_fee REAL,
            balance REAL,
            PRIMARY KEY (practice_id, claim_id)
        )
        """
    )
    for claim_id, payer, amount, status in rows:
        conn.execute(
            """
            INSERT INTO sd_claims
            (claim_id, patient_name, payer, service_date, claim_amount, claim_status,
             practice_id, extracted_at, total_fee, balance)
            VALUES (?, 'Pat', ?, '2026-05-01', ?, ?, '', 'now', ?, NULL)
            """,
            (claim_id, payer, amount, status, amount),
        )
    conn.commit()
    conn.close()


class OutstandingClaimsBridgeHal10580Tests(unittest.TestCase):
    def test_find_aging_skips_derived_ar_buckets_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            derived = root / "softdent_ar_aging.csv"
            derived.write_text("Bucket,Balance\nCurrent,100\n", encoding="utf-8")
            real = root / "account_aging.csv"
            _write_aging_csv(real, ar_total=100.0, ins_total=0.0)
            # Make derived newer so a naive mtime pick would choose it.
            derived.touch()
            hit = find_account_aging_export(roots=[root])
            self.assertEqual(hit, real)

    def test_resolve_account_transactions_db_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "softdent_financial_analytics.db"
            sqlite3.connect(str(db)).close()
            hit = resolve_account_transactions_db(db)
            self.assertEqual(hit, db)
            self.assertIsNone(resolve_account_transactions_db(Path(tmp) / "missing.db"))

    def test_parse_aging_and_reconcile_unnamed_payers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            aging = root / "account_aging.csv"
            _write_aging_csv(aging, ar_total=49111.03, ins_total=0.0)
            parsed = parse_account_aging_export(aging)
            self.assertTrue(parsed.get("ok"))
            self.assertAlmostEqual(float(parsed.get("trueReceivablesTotal") or 0), 49111.03, places=2)
            self.assertIsNotNone(parsed.get("outstandingInsuranceTotal"))
            self.assertEqual(float(parsed["outstandingInsuranceTotal"]), 0.0)

            db = root / "analytics.db"
            _seed_claims_db(
                db,
                [
                    ("C1", "Insurance", 100.0, "Pending Review"),
                    ("C2", "Insurance", 200.0, "Pending Review"),
                    ("C3", "Delta Dental", 50.0, "Ready"),
                ],
            )
            claims = aggregate_sd_claims_by_carrier(db_path=db)
            self.assertEqual(claims.get("claimCount"), 3)
            self.assertEqual(claims.get("unnamedPayerClaimCount"), 2)
            self.assertEqual(claims.get("namedPayerClaimCount"), 1)
            recon = reconcile_claims_to_aging(claims, parsed)
            self.assertEqual(recon.get("gapCode"), GAP_PAYER_ATTRIBUTION)
            self.assertFalse(recon.get("ok"))

            with mock.patch(
                "softdent_outstanding_claims_bridge.find_account_aging_export",
                return_value=aging,
            ):
                with mock.patch(
                    "softdent_outstanding_claims_bridge.resolve_account_transactions_db",
                    return_value=db,
                ):
                    with mock.patch(
                        "import_loader.softdent_import_dir",
                        return_value=root / "inbox",
                    ):
                        bridge = build_outstanding_claims_by_carrier_bridge(write_inbox=True)
            self.assertEqual(bridge.get("gapCode"), GAP_PAYER_ATTRIBUTION)
            text = format_outstanding_claims_hal_reply(bridge)
            self.assertIn("Outstanding Claims by Carrier", text)
            self.assertIn("unnamed", text.lower())
            self.assertIn("Do not invent carrier", text)
            self.assertNotRegex(
                text,
                r"(?i)(?<!do not )(?<!don't )invent(ed)?\s+carrier",
            )
            inbox = root / "inbox" / "softdent_outstanding_claims_by_carrier.json"
            self.assertTrue(inbox.is_file())
            payload = json.loads(inbox.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("def"), "HAL-10580")

    def test_hal_policy_outstanding_claims(self) -> None:
        from nr2_hal_gateway import try_local_policy_reply

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            aging = root / "account_aging.csv"
            _write_aging_csv(aging, ar_total=100.0, ins_total=0.0)
            db = root / "analytics.db"
            _seed_claims_db(db, [("C1", "Insurance", 40.0, "Pending Review")])
            with mock.patch(
                "softdent_outstanding_claims_bridge.find_account_aging_export",
                return_value=aging,
            ):
                with mock.patch(
                    "softdent_outstanding_claims_bridge.resolve_account_transactions_db",
                    return_value=db,
                ):
                    with mock.patch(
                        "import_loader.softdent_import_dir",
                        return_value=root / "inbox",
                    ):
                        hit = try_local_policy_reply("Show outstanding claims by carrier")
        self.assertIsNotNone(hit)
        self.assertEqual((hit or {}).get("intent"), "policy:outstanding-claims-by-carrier")
        self.assertIn("HAL-10580", (hit or {}).get("text") or "")


if __name__ == "__main__":
    unittest.main()
