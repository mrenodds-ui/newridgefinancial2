"""Tests for nr2_softdent_daily (hal-10071)."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from softdent_odbc_extract import ensure_sd_schema
from nr2_softdent_daily import (
    claims_outstanding,
    collections_daily,
    new_patients_mtd,
    provider_production,
)


def _seed_db(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    ensure_sd_schema(conn)
    conn.execute(
        "INSERT OR REPLACE INTO sd_payments (practice_id, patient_id, payment_date, amount, payer, method, extracted_at) VALUES ('', '1001', '2026-06-15', 85.0, '', 'Visa', 't')"
    )
    conn.execute(
        "INSERT OR REPLACE INTO sd_patients (patient_id, patient_name, first_visit_date, last_visit_date, practice_id, extracted_at) VALUES ('1001', 'Jane', '2026-06-01', '2026-06-15', '', 't')"
    )
    conn.execute(
        "INSERT OR REPLACE INTO sd_claims (claim_id, patient_name, payer, service_date, claim_amount, claim_status, practice_id, extracted_at) VALUES ('CLM-1', 'Jane', 'Delta', '2026-06-10', 420.0, 'Ready', '', 't')"
    )
    conn.execute(
        """
        INSERT OR REPLACE INTO sd_procedures
        (practice_id, patient_id, proc_date, ada_code, tooth, surface, provider_code, description, production, extracted_at)
        VALUES ('', '1001', '2026-06-15', '1110', '', '', 'DR1', 'Prophy', 120.0, 't')
        """
    )
    conn.commit()
    conn.close()


class Nr2SoftdentDailyTests(unittest.TestCase):
    def test_collections_daily(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "analytics.sqlite3"
            _seed_db(db_path)
            with patch("nr2_softdent_daily.resolve_sd_sqlite_db", return_value=db_path):
                result = collections_daily()
            self.assertTrue(result["hasData"])
            self.assertEqual(result["values"][-1], 85.0)

    def test_new_patients_mtd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "analytics.sqlite3"
            _seed_db(db_path)
            with patch("nr2_softdent_daily.resolve_sd_sqlite_db", return_value=db_path):
                result = new_patients_mtd(period="2026-06")
            self.assertTrue(result["hasData"])
            self.assertEqual(result["count"], 1)

    def test_claims_outstanding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "analytics.sqlite3"
            _seed_db(db_path)
            with patch("nr2_softdent_daily.resolve_sd_sqlite_db", return_value=db_path):
                result = claims_outstanding()
            self.assertTrue(result["hasData"])
            self.assertEqual(result["claims"][0]["claimId"], "CLM-1")

    def test_provider_production(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "analytics.sqlite3"
            _seed_db(db_path)
            with patch("nr2_softdent_daily.resolve_sd_sqlite_db", return_value=db_path):
                result = provider_production()
            self.assertTrue(result["hasData"])
            self.assertEqual(result["providers"][0]["providerCode"], "DR1")


if __name__ == "__main__":
    unittest.main()
