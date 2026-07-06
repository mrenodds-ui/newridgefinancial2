"""Moonshot HAL employee sprint tests — Sprints 1-7."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class _FakeStore:
    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self.db_path = Path(tempfile.gettempdir()) / "nr2-hal-employee-test.db"

    def get(self, key: str):
        return self._data.get(key)

    def set(self, key: str, value: str) -> None:
        self._data[key] = value

    def _connect(self):
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        from hal_employee_workflows import init_employee_workflow_schemas

        init_employee_workflow_schemas(conn)
        return conn


class ShiftContextTests(unittest.TestCase):
    def test_clock_in_and_shift_context(self) -> None:
        from employee_actions import clock_in_shift, get_current_shift_context

        store = _FakeStore()
        clocked = clock_in_shift(store, employee_id="HAL", tier=5)
        self.assertTrue(clocked["ok"])
        ctx = get_current_shift_context(store)
        self.assertTrue(ctx["active"])
        self.assertEqual(ctx["tier"], 5)

    def test_check_action_consent_qbo_post_cap(self) -> None:
        from employee_actions import check_action_consent, clock_in_shift

        store = _FakeStore()
        clock_in_shift(store, tier=2)
        ok = check_action_consent("HAL", "qbo-post", 1000, store=store)
        self.assertTrue(ok["allowed"])
        blocked = check_action_consent("HAL", "qbo-post", 9000, store=store)
        self.assertFalse(blocked["allowed"])


class HalGatewayTests(unittest.TestCase):
    def test_classify_query_intent(self) -> None:
        from nr2_hal_gateway import classify_query_intent

        self.assertEqual(classify_query_intent("What is our revenue this month?"), "transactional")
        self.assertEqual(classify_query_intent("Why did collections drop last quarter?"), "analytical")
        self.assertEqual(classify_query_intent("CDT code for crown on tooth 14"), "clinical")

    def test_resolve_lane_mapping(self) -> None:
        from nr2_hal_gateway import resolve_lane, route_by_complexity

        self.assertEqual(resolve_lane("chat8b")["model"], "hal-chat:8b")
        self.assertEqual(resolve_lane("reason21b")["lane"], "reason21b")
        lane = route_by_complexity("simple hello", shift_context={"tier": 1})
        self.assertEqual(lane, "chat8b")
        lane_esc = route_by_complexity("deep root cause investigation", shift_context={"tier": 5})
        self.assertEqual(lane_esc, "escalate30b")

    def test_stale_financial_blocked(self) -> None:
        from nr2_hal_gateway import evaluate_query

        readiness = {"level": "stale", "ok": False, "loadedAt": "2020-01-01T00:00:00Z", "ageHours": 72}
        result = evaluate_query(query="What is our revenue?", readiness=readiness)
        self.assertFalse(result.get("ok"))
        self.assertEqual(result.get("error"), "HAL_UNAVAILABLE_STALE_DATA")

    @mock.patch("nr2_hal_gateway.call_ollama_chat")
    def test_soft_stale_analytical_watermark(self, mock_chat: mock.MagicMock) -> None:
        from nr2_hal_gateway import evaluate_query

        mock_chat.return_value = {"ok": True, "body": {"message": {"content": "Trend summary text."}}}
        readiness = {"level": "stale", "ok": False, "loadedAt": "2020-01-01T00:00:00Z", "ageHours": 12}
        result = evaluate_query(query="Why did A/R increase?", readiness=readiness, store=_FakeStore())
        self.assertTrue(result.get("ok"))
        self.assertIn("SOFT-STALE", result.get("text") or "")


class EmployeeWorkflowTests(unittest.TestCase):
    def test_deposit_reconciliation_draft(self) -> None:
        from hal_employee_workflows import draft_deposit_reconciliation

        store = _FakeStore()
        result = draft_deposit_reconciliation(store, {"bankAmount": 1000, "ledgerAmount": 950})
        self.assertTrue(result["ok"])
        self.assertEqual(result["variance"], 50.0)

    def test_claim_preflight(self) -> None:
        from hal_employee_workflows import stage_claim_preflight

        store = _FakeStore()
        result = stage_claim_preflight(
            store,
            {"claimId": "C1", "narrativePresent": True, "attachmentsReady": True, "feeScheduleVerified": True, "insuranceVerified": True, "clinicalSummaryLinked": True},
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "ready")

    def test_eob_match(self) -> None:
        from hal_employee_workflows import process_eob_match

        store = _FakeStore()
        result = process_eob_match(store, {"referenceId": "EOB1", "claimId": "C1", "paidAmount": 120})
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "matched")

    def test_month_end_tasks(self) -> None:
        from hal_employee_workflows import generate_month_end_tasks

        store = _FakeStore()
        result = generate_month_end_tasks(store)
        self.assertTrue(result["ok"])
        self.assertGreaterEqual(result["count"], 3)


class AuditSessionTests(unittest.TestCase):
    def test_hal_session_record_and_fetch(self) -> None:
        from nr2_audit_log import explain_hal_block, get_hal_session, record_hal_session

        store = _FakeStore()
        record_hal_session(store, "sess-1", {"type": "evaluate_query", "lane": "chat8b"})
        fetched = get_hal_session(store, "sess-1")
        self.assertTrue(fetched["ok"])
        self.assertEqual(len(fetched["session"]["events"]), 1)
        explained = explain_hal_block(store, {"error": "HAL_UNAVAILABLE_STALE_DATA", "sessionId": "sess-1"})
        self.assertTrue(explained["ok"])
        self.assertIn("stale", explained["explanation"].lower())


class SoftStaleEnvTests(unittest.TestCase):
    def test_soft_stale_ttl_default(self) -> None:
        from nr2_hal_gateway import SOFT_STALE_TTL_HOURS

        self.assertEqual(SOFT_STALE_TTL_HOURS, float(os.environ.get("NR2_SOFT_STALE_TTL_HOURS", "24")))


class Era835Tests(unittest.TestCase):
    def test_parse_835_segments(self) -> None:
        from era835_parser import parse_835_text

        text = "Claim CLM-99 paid: $120.00 patient: Jane Doe 2026-06-01"
        parsed = parse_835_text(text)
        self.assertTrue(parsed["ok"])
        self.assertGreaterEqual(parsed["count"], 1)

    def test_fuzzy_match_by_claim_id(self) -> None:
        from era835_parser import fuzzy_match_claims, parse_835_text

        parsed = parse_835_text("Claim CLM-1 paid: $50")
        rows = [{"Claim": "CLM-1", "Patient": "Jane", "Amount": 50}]
        matches = fuzzy_match_claims(parsed["segments"], rows)
        self.assertTrue(matches[0].get("claimId"))


class ImportHealTests(unittest.TestCase):
    def test_heal_returns_structure(self) -> None:
        from import_healing import heal_import_pipeline

        result = heal_import_pipeline(force=False)
        self.assertIn("ok", result)
        self.assertIn("steps", result)


class CollectionLetterTests(unittest.TestCase):
    def test_collection_letter_draft(self) -> None:
        from hal_employee_workflows import generate_collection_letter

        store = _FakeStore()
        from employee_actions import clock_in_shift

        clock_in_shift(store, tier=3)
        result = generate_collection_letter(store, {"patientName": "Jane Doe", "balance": 250})
        self.assertTrue(result["ok"])
        self.assertIn("Dear Jane Doe", result["letter"])


if __name__ == "__main__":
    unittest.main()
