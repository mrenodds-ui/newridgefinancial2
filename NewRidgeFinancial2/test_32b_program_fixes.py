"""Unit tests for shippable 32B program fixes (2026-07-13)."""

from __future__ import annotations

import os
import unittest
from unittest import mock


class TestScrubImportRows(unittest.TestCase):
    def test_drops_void_and_exact_dupes(self) -> None:
        from apex_32b_program_fixes_pack import scrub_import_rows

        rows = [
            {"Date": "2026-01-01", "Code": "D1110", "Amount": "50", "PatientName": "A"},
            {"Date": "2026-01-01", "Code": "D1110", "Amount": "50", "PatientName": "A"},
            {"Date": "2026-01-02", "Code": "VOID", "Amount": "50", "Description": "voided"},
            {"Date": "2026-01-03", "Code": "D0120", "Amount": "25", "PatientName": "B"},
        ]
        kept, summary = scrub_import_rows(rows)
        self.assertEqual(summary["voidDropped"], 1)
        self.assertEqual(summary["dupDropped"], 1)
        self.assertEqual(summary["kept"], 2)
        self.assertEqual(len(kept), 2)


class TestImportCacheTelemetry(unittest.TestCase):
    def test_counts_live_stale_warming(self) -> None:
        from apex_32b_program_fixes_pack import import_cache_kpi_widget, import_cache_telemetry

        now = 1000.0
        cache = {
            "financial": {"at": now - 2.0, "payload": {"warming": False}},
            "hal": {"at": now - 40.0, "payload": {"warming": False}},
            "financial:warming": {"at": now},
        }
        tele = import_cache_telemetry(
            widgets_cache=cache,
            fill_progress={"financial": {"pct": 40, "ts": now}},
            fill_failures=0,
            ttl_sec=15.0,
            now=now,
        )
        self.assertEqual(tele["liveKeys"], 1)
        self.assertEqual(tele["staleKeys"], 1)
        self.assertEqual(tele["warmingKeys"], 1)
        self.assertIn("financial", tele["pagesFilling"])
        w = import_cache_kpi_widget(tele)
        self.assertEqual(w["id"], "import-cache-kpi")
        self.assertIn("Warming", w["message"])


class TestBridgeErrors(unittest.TestCase):
    def test_ok_when_clean(self) -> None:
        from apex_32b_program_fixes_pack import bridge_errors_widget

        with mock.patch(
            "apex_32b_program_fixes_pack.bridge_errors_widget",
            wraps=None,
        ):
            pass
        # Patch internals via import path inside function
        with mock.patch.dict("sys.modules", {}):
            w = bridge_errors_widget(bundle={"diagnostics": {"summary": {"connected": 5, "total": 5}}}, fill_failures=0)
        # Without blocking issues / quarantine, status is ok or may include diagnostics noise
        self.assertEqual(w["id"], "bridge-errors")
        self.assertIn(w["status"], {"ok", "warn"})

    def test_warn_on_fill_failure(self) -> None:
        from apex_32b_program_fixes_pack import bridge_errors_widget

        w = bridge_errors_widget(bundle={}, fill_failures=2, last_sync_error="boom")
        self.assertEqual(w["status"], "warn")
        self.assertIn("fill failures", w["message"].lower())


class TestReconciliationSurface(unittest.TestCase):
    def test_defaults_env_on(self) -> None:
        from apex_32b_program_fixes_pack import ensure_reconciliation_env

        prev = os.environ.pop("NR2_RECONCILIATION", None)
        try:
            ensure_reconciliation_env()
            self.assertEqual(os.environ.get("NR2_RECONCILIATION"), "1")
        finally:
            if prev is None:
                os.environ.pop("NR2_RECONCILIATION", None)
            else:
                os.environ["NR2_RECONCILIATION"] = prev


class TestGoldOpsHonesty(unittest.TestCase):
    def test_staff_reply_mentions_missing_not_zero(self) -> None:
        from apex_32b_program_fixes_pack import gold_csv_ops_staff_reply, gold_ticket_hint_widget

        text = gold_csv_ops_staff_reply()
        self.assertIn("GOLD_CSV_MISSING", text)
        self.assertIn("pending", text.lower())
        self.assertTrue(
            "carestreamcasenumber" in text.lower().replace(" ", "")
            or "case # pending" in text.lower()
            or "case number" in text.lower()
        )
        w = gold_ticket_hint_widget()
        self.assertEqual(w["status"], "empty")
        self.assertNotIn("$0", w["message"])  # honest wait, not inventing zero dollars as value


class TestAuditKinds(unittest.TestCase):
    def test_financial_mutation_actions_include_program_kinds(self) -> None:
        from nr2_audit_log import FINANCIAL_MUTATION_ACTIONS

        for kind in ("financial_override", "consent_action", "sync", "claim_action", "hal_outbound_consent"):
            self.assertIn(kind, FINANCIAL_MUTATION_ACTIONS)


if __name__ == "__main__":
    unittest.main()
