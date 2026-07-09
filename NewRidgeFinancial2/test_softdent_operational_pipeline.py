"""Daysheet-derived claims and clinical notes beat stale sample cache exports."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from import_direct_pipeline import pick_freshest_dataset
from softdent_operational_pipeline import (
    build_claims_rows,
    build_clinical_notes_rows,
    build_daysheet_claims_dataset,
    build_daysheet_clinical_dataset,
    _iter_daysheet_transactions,
)


class SoftDentOperationalPipelineTests(unittest.TestCase):
    def test_iter_daysheet_transactions_parses_production_rows(self) -> None:
        formatted = [
            ["May 28, 2026"],
            ["", "ID", "Name", "D$", "Dr", "Code", "Description", "Prod", "Charges", "Prod Adj", "Cash", "Check", "Credit", "Pay. Adj", "Transaction Notes"],
            [" ", "1080404", "Bernett, Jeffery Adam", "1", "1", "1110", "Prophylaxis - Adult", "$137.00", "", "", "", "", "", "", ""],
            [" ", "1424602", "Ayer, Robert", "1", "1", "51", "Insurance Co Write-Off", "", "", "($237.00)", "", "", "", "", ""],
        ]
        rows = _iter_daysheet_transactions(formatted)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["patientName"], "Bernett, Jeffery Adam")
        self.assertEqual(rows[0]["production"], 137.0)

    def test_build_clinical_notes_skips_sample_patients(self) -> None:
        rows = build_clinical_notes_rows(
            [
                {"patientId": "1", "patientName": "John Doe", "code": "1110", "description": "Prophy", "reportDate": "2026-06-12"},
                {"patientId": "2", "patientName": "Bernett, Jeffery Adam", "code": "1110", "description": "Prophylaxis - Adult", "reportDate": "2026-05-28"},
            ]
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["PatientName"], "Bernett, Jeffery Adam")

    def test_build_claims_marks_paid_when_insurance_payment_present(self) -> None:
        transactions = [
            {"patientId": "9", "patientName": "Kelley, Reese", "code": "1110", "description": "Prophylaxis - Adult", "production": 137.0, "reportDate": "2026-05-28"},
            {"patientId": "9", "patientName": "Kelley, Reese", "code": "2", "description": "Insurance Check Payment", "production": None, "reportDate": "2026-05-28"},
        ]
        claims = build_claims_rows(transactions)
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0]["ClaimStatus"], "Paid")

    def test_build_claims_prefers_sd_claims_payer_when_available(self) -> None:
        from softdent_operational_pipeline import _sd_claims_payer_index

        _sd_claims_payer_index.cache_clear()
        transactions = [
            {
                "patientId": "9",
                "patientName": "Kelley, Reese",
                "code": "1110",
                "description": "Prophylaxis - Adult",
                "production": 137.0,
                "reportDate": "2026-05-28",
            },
        ]
        with patch(
            "softdent_operational_pipeline._sd_claims_payer_index",
            return_value={"name_date|kelley, reese|2026-05-28": "METLIFE DENTAL"},
        ):
            claims = build_claims_rows(transactions)
        self.assertEqual(claims[0]["Payer"], "METLIFE DENTAL")
        _sd_claims_payer_index.cache_clear()
        with patch("softdent_operational_pipeline._sd_claims_payer_index", return_value={}):
            claims2 = build_claims_rows(transactions)
        self.assertEqual(claims2[0]["Payer"], "Insurance")

    def test_daysheet_pipeline_beats_sample_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            daysheet = Path(tmp) / "daysheet.jsonl"
            formatted = [
                ["May 28, 2026"],
                ["", "ID", "Name", "D$", "Dr", "Code", "Description", "Prod", "Charges", "Prod Adj", "Cash", "Check", "Credit", "Pay. Adj", "Transaction Notes"],
                [" ", "1080404", "Bernett, Jeffery Adam", "1", "1", "1110", "Prophylaxis - Adult", "$137.00", "", "", "", "", "", "", "Routine prophy completed."],
            ]
            payload = {
                "normalized": {"report_date": "2026-05-28"},
                "raw_row": {"formatted_report_rows": formatted},
            }
            daysheet.write_text(json.dumps(payload) + "\n", encoding="utf-8")
            os.utime(daysheet, (1750000000, 1750000000))

            pipeline = build_daysheet_clinical_dataset(daysheet)
            sample_cache = {
                "sourcePath": str(Path(tmp) / "softdent_clinical_notes_data.json"),
                "modifiedAt": datetime.fromtimestamp(1760000000, tz=timezone.utc).isoformat(),
                "rows": [{"PatientName": "John Doe", "ClinicalNote": "Sample", "Procedure": "Crown"}],
                "readSource": "cache",
            }
            picked = pick_freshest_dataset(sample_cache, pipeline)
            self.assertIs(picked, pipeline)
            self.assertEqual(picked.get("sourceKind"), "pipeline-daysheet")


if __name__ == "__main__":
    unittest.main()
