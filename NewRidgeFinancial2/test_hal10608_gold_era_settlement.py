"""HAL-10608 — Gold ∪ ERA settlement hydration readiness (STOP OCR)."""

from __future__ import annotations

import unittest

from apex_backend import BUILD_ID
from softdent_gold_era_settlement_hal10608 import (
    HONESTY_BANNER,
    PACKAGE_BUILD_ID,
    STOP_OCR_POLICY,
    format_hal10608_reply,
    gold_era_settlement_status,
    gold_era_settlement_widget,
    run_ops_10608_gold_era_settlement,
    settlement_hydration_readiness_gate,
    staff_briefing_10608,
)


class Hal10608GoldEraSettlementTests(unittest.TestCase):
    def test_build_id(self) -> None:
        self.assertEqual(PACKAGE_BUILD_ID, "hal-10608")
        self.assertEqual(BUILD_ID, "hal-10608")

    def test_stop_ocr_policy(self) -> None:
        self.assertTrue(STOP_OCR_POLICY.get("ocrExpansionStopped"))
        self.assertFalse(STOP_OCR_POLICY.get("writesFromOcr"))
        self.assertTrue(STOP_OCR_POLICY.get("patientJpgOcrBlocked"))
        self.assertIn("DO NOT POST", STOP_OCR_POLICY.get("banner") or "")

    def test_staff_briefing_blocks_ocr(self) -> None:
        b = staff_briefing_10608()
        joined = " ".join(b.get("doNot") or []).lower()
        self.assertIn("ocr", joined)
        self.assertTrue((b.get("stopOcr") or {}).get("ocrExpansionStopped"))

    def test_readiness_gate_empty_not_ready(self) -> None:
        gate = settlement_hydration_readiness_gate(
            gold={"gapCode": "GOLD_CSV_MISSING", "paymentLines": 0},
            era={"gapCode": "ERA835_PENDING", "fileCount": 0, "pending": True, "ingestedRowSample": 0},
        )
        self.assertFalse(gate.get("ready"))
        self.assertEqual(gate.get("lanes"), [])

    def test_readiness_via_era_inbox(self) -> None:
        gate = settlement_hydration_readiness_gate(
            gold={"gapCode": "GOLD_CSV_MISSING", "paymentLines": 0},
            era={
                "gapCode": "ERA835_PENDING",
                "fileCount": 3,
                "pending": True,
                "ingestedRowSample": 0,
                "latestTotalPaid": None,
            },
        )
        self.assertTrue(gate.get("ready"))
        self.assertIn("era", gate.get("lanes") or [])
        self.assertFalse(gate.get("settlementMatrixReady"))

    def test_stale_era_fixture_not_ghost_ready(self) -> None:
        gate = settlement_hydration_readiness_gate(
            gold={"gapCode": "GOLD_CSV_MISSING", "paymentLines": 0},
            era={
                "gapCode": None,
                "fileCount": 0,
                "pending": False,
                "ingestedRowSample": 2,
                "latestTotalPaid": None,  # t.835 fixture
            },
        )
        self.assertFalse(gate.get("ready"))
        self.assertFalse(gate.get("eraReady"))
        self.assertFalse(gate.get("settlementMatrixReady"))

    def test_readiness_via_gold(self) -> None:
        gate = settlement_hydration_readiness_gate(
            gold={"gapCode": "GOLD_OK", "paymentLines": 1200},
            era={"gapCode": "ERA835_PENDING", "fileCount": 0, "pending": True, "ingestedRowSample": 0},
        )
        self.assertTrue(gate.get("ready"))
        self.assertIn("gold", gate.get("lanes") or [])
        self.assertTrue(gate.get("settlementMatrixReady"))

    def test_status_honesty(self) -> None:
        st = gold_era_settlement_status()
        self.assertTrue(st.get("ok"))
        self.assertTrue(st.get("ocrExpansionStopped"))
        self.assertFalse(st.get("writesFromOcr"))
        self.assertFalse(st.get("inventedGold"))
        self.assertTrue(st.get("emptyIsNotZero"))
        self.assertFalse(st.get("softDentWriteBack"))
        self.assertIn("DO NOT POST", st.get("honestyBanner") or HONESTY_BANNER)

    def test_run_no_invented_gold(self) -> None:
        result = run_ops_10608_gold_era_settlement(
            attempt_era_ingest=False, attempt_gold_repair=False
        )
        self.assertTrue(result.get("ok"))
        self.assertFalse(result.get("inventedGold"))
        self.assertTrue(result.get("ocrExpansionStopped"))
        self.assertFalse(result.get("writesFromOcr"))
        text = format_hal10608_reply(result)
        self.assertIn("HAL-10608", text)
        self.assertIn("STOPPED", text.upper())

    def test_widget(self) -> None:
        w = gold_era_settlement_widget()
        self.assertEqual(w.get("def"), "HAL-10608")
        self.assertIn("gold-era-settlement", w.get("apiStatus") or "")
        self.assertIn("STOP", (w.get("honesty") or "").upper())


if __name__ == "__main__":
    unittest.main()
