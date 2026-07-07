"""Pilot phase gate tests — Moonshot shadow/cutover operational criteria."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class PilotPhaseGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)
        import nr2_pilot as mod

        self.mod = mod
        self._orig_state = mod.PILOT_STATE_PATH
        self._orig_cutover = mod.CUTOVER_ATTESTATION_PATH
        mod.PILOT_STATE_PATH = self.tmp / "pilot_phase.json"
        mod.CUTOVER_ATTESTATION_PATH = self.tmp / "pilot_cutover.json"

    def tearDown(self) -> None:
        self.mod.PILOT_STATE_PATH = self._orig_state
        self.mod.CUTOVER_ATTESTATION_PATH = self._orig_cutover
        self._tmpdir.cleanup()

    def test_default_shadow_blocks_export(self) -> None:
        denied = self.mod.check_posting_gate("posting_queue_export_approved")
        self.assertIsNotNone(denied)
        self.assertEqual(denied.get("pilotPhase"), "shadow")

    def test_shadow_blocks_bulk_review(self) -> None:
        denied = self.mod.check_posting_gate("posting_queue_bulk_review")
        self.assertIsNotNone(denied)

    def test_supervised_allows_bulk_but_not_export(self) -> None:
        with mock.patch.dict(os.environ, {"NR2_PILOT_PHASE": "supervised"}, clear=False):
            self.assertIsNone(self.mod.check_posting_gate("posting_queue_bulk_review"))
            denied = self.mod.check_posting_gate("posting_queue_export_approved")
            self.assertIsNotNone(denied)

    def test_cutover_allows_export(self) -> None:
        with mock.patch.dict(os.environ, {"NR2_PILOT_PHASE": "cutover"}, clear=False):
            self.assertIsNone(self.mod.check_posting_gate("posting_queue_export_approved"))

    def test_cutover_validator_requires_attestation(self) -> None:
        self.mod.save_pilot_state(
            {
                "phase": "cutover",
                "shadow_started_at": "2020-01-01T00:00:00+00:00",
                "supervised_started_at": "2020-01-01T00:00:00+00:00",
            }
        )
        with mock.patch.dict(
            os.environ,
            {"NR2_PILOT_PHASE": "cutover", "NR2_PILOT_SKIP_DAY_CHECKS": "1"},
            clear=False,
        ):
            report = self.mod.cutover_readiness_checks()
        self.assertFalse(report.get("ok"))
        names = {c["name"] for c in report.get("checks") or [] if not c.get("ok")}
        self.assertIn("cutover_attestation", names)

    def test_ensure_phase_started_writes_state(self) -> None:
        state = self.mod.ensure_phase_started("shadow")
        self.assertEqual(state.get("phase"), "shadow")
        self.assertTrue(self.mod.PILOT_STATE_PATH.is_file())
        loaded = json.loads(self.mod.PILOT_STATE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(loaded.get("phase"), "shadow")


if __name__ == "__main__":
    unittest.main()
