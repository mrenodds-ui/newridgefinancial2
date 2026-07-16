"""Patient dossier — empty≠$0 + HAL summarize intent parsing."""

from __future__ import annotations

import unittest

from patient_dossier import (
    _safe_money,
    extract_patient_ref_from_query,
    query_touches_patient_summary,
)


class PatientDossierTests(unittest.TestCase):
    def test_safe_money_empty_not_zero(self) -> None:
        self.assertEqual(_safe_money(None), "unknown")
        self.assertEqual(_safe_money(""), "unknown")
        self.assertEqual(_safe_money(0), "unknown")
        self.assertEqual(_safe_money(0.0), "unknown")
        self.assertEqual(_safe_money(12.5), "$12.50")

    def test_touches_patient_summary(self) -> None:
        self.assertTrue(query_touches_patient_summary("Summarize patient 12345"))
        self.assertTrue(query_touches_patient_summary("Patient summary for Nickel, Donna"))
        self.assertTrue(query_touches_patient_summary("Can HAL summarize patients?"))
        self.assertFalse(query_touches_patient_summary("Summarize what HAL does in this program"))
        self.assertFalse(query_touches_patient_summary("What is insurance lag?"))

    def test_extract_patient_ref(self) -> None:
        self.assertEqual(extract_patient_ref_from_query("Summarize patient 12345"), "12345")
        self.assertEqual(
            extract_patient_ref_from_query("Patient summary for Nickel, Donna"),
            "Nickel, Donna",
        )
        self.assertIsNone(extract_patient_ref_from_query("Can you summarize patients?"))
        self.assertIsNone(extract_patient_ref_from_query("Summarize patients"))


if __name__ == "__main__":
    unittest.main()
