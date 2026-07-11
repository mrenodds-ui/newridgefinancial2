"""Prefer SoftDent named-payer claims CSV over daysheet overwrite."""

from __future__ import annotations

import unittest

from import_sync import (
    _claims_have_named_payers,
    _claims_look_daysheet_derived,
    _is_generic_payer,
    _is_sample_claims,
)


class ClaimsPreserveHelpersTests(unittest.TestCase):
    def test_generic_payer_labels(self) -> None:
        self.assertTrue(_is_generic_payer("Insurance"))
        self.assertTrue(_is_generic_payer(""))
        self.assertFalse(_is_generic_payer("Delta Dental"))

    def test_named_payers_detected(self) -> None:
        rows = [
            {"ClaimId": "C1", "Payer": "Insurance"},
            {"ClaimId": "C2", "Payer": "MetLife"},
        ]
        self.assertTrue(_claims_have_named_payers(rows))
        self.assertFalse(_claims_have_named_payers([{"Payer": "Insurance"}]))

    def test_daysheet_derived_shape(self) -> None:
        daysheet = [
            {"ClaimId": "DS-20260709-1", "Payer": "Insurance"},
            {"ClaimId": "DS-20260709-2", "Payer": "Insurance"},
        ]
        softdent = [
            {"ClaimId": "88421", "Payer": "Delta Dental"},
            {"ClaimId": "88422", "Payer": "Guardian"},
        ]
        self.assertTrue(_claims_look_daysheet_derived(daysheet))
        self.assertFalse(_claims_look_daysheet_derived(softdent))

    def test_jane_doe_stub_is_sample(self) -> None:
        stub = [
            {
                "ClaimId": "CLM-001",
                "PatientName": "Jane Doe",
                "Payer": "Delta Dental",
                "ClaimAmount": "420.0",
            }
        ]
        self.assertTrue(_is_sample_claims(stub))

    def test_real_claims_not_sample(self) -> None:
        rows = [
            {
                "ClaimId": "DS-20260528-1080404-1110-3",
                "PatientName": "Bernett, Jeffery Adam",
                "Payer": "Insurance",
            }
        ]
        self.assertFalse(_is_sample_claims(rows))


if __name__ == "__main__":
    unittest.main()
