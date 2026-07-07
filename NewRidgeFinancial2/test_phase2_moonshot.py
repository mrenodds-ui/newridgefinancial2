"""Moonshot Phase 2 coding guidance tests — Sprints 8-12."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class _FakeStore:
    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self.db_path = Path(tempfile.gettempdir()) / f"nr2-phase2-test-{id(self)}.db"

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


class FinancialLaneOverrideTests(unittest.TestCase):
    def test_financial_query_routes_reason21b(self) -> None:
        from nr2_hal_gateway import route_by_complexity

        store = _FakeStore()
        lane = route_by_complexity("$500 adjustment for patient", shift_context={"tier": 1}, store=store)
        self.assertEqual(lane, "reason21b")

    def test_reject_financial_downgrade(self) -> None:
        from nr2_hal_gateway import reject_financial_lane_downgrade

        self.assertTrue(reject_financial_lane_downgrade("posting $100", "chat8b"))
        self.assertFalse(reject_financial_lane_downgrade("hello", "chat8b"))


class SseStreamingTests(unittest.TestCase):
    def test_sse_frame_format(self) -> None:
        from nr2_hal_gateway import iter_ollama_sse_tokens

        with mock.patch("nr2_hal_gateway.urllib.request.urlopen") as mock_open:
            mock_resp = mock.MagicMock()
            mock_resp.__enter__.return_value = mock_resp
            mock_resp.__iter__.return_value = [
                b'{"message":{"content":"Hi"},"done":false}\n',
                b'{"message":{"content":" there"},"done":true}\n',
            ]
            mock_open.return_value = mock_resp
            frames = list(iter_ollama_sse_tokens(model="hal-chat:8b", messages=[], lane="chat8b"))
        self.assertTrue(any("event: meta" in f for f in frames))
        self.assertTrue(any('"token": "Hi"' in f or '"token":"Hi"' in f.replace(" ", "") for f in frames))


class EraFeedbackTests(unittest.TestCase):
    def test_record_feedback_and_train_stub(self) -> None:
        from era_ml_trainer import record_match_feedback, train_era_model

        store = _FakeStore()
        conn = store._connect()
        for i in range(5):
            record_match_feedback(
                conn,
                era_line_id=f"line-{i}",
                predicted_claim_id=f"C{i}",
                approved=i % 2 == 0,
                confidence_at_prediction=0.8,
            )
        result = train_era_model(conn)
        self.assertTrue(result.get("ok"))


class ShiftHandoffTests(unittest.TestCase):
    def test_clock_out_generates_handoff(self) -> None:
        from employee_actions import clock_in_shift, clock_out_shift
        from hal_employee_workflows import generate_collections_queue

        store = _FakeStore()
        clock_in_shift(store, tier=3)
        generate_collections_queue(store, limit=5)
        out = clock_out_shift(store)
        self.assertTrue(out["ok"])
        self.assertIn("handoffId", out)
        self.assertIn("Shift Handoff", out.get("reportMarkdown") or "")


class DocumentClassifierTests(unittest.TestCase):
    def test_classify_eob_era(self) -> None:
        from document_classifier import classify_document_text, route_for_category

        result = classify_document_text("835 remittance payment for claim 12345")
        self.assertEqual(result["category"], "EOB_ERA")
        self.assertGreater(result["confidence"], 0.8)
        self.assertEqual(route_for_category("EOB_ERA"), "parse_era_835")


class VoipSmsTests(unittest.TestCase):
    def test_voice_script_load(self) -> None:
        from voip_actions import get_voice_script

        script = get_voice_script("collections", patient_name="Jane", balance="$120")
        self.assertTrue(script["ok"])
        self.assertIn("$120", script["script"])

    def test_sms_consent_stop(self) -> None:
        from sms_actions import handle_inbound_sms, send_billing_sms, sms_consent_allowed

        store = _FakeStore()
        conn = store._connect()
        send_billing_sms(conn, patient_id="P1", phone_number="+15551234567", body="Test")
        handle_inbound_sms(conn, phone_number="+15551234567", body="STOP", patient_id="P1")
        self.assertFalse(sms_consent_allowed(conn, "P1"))


class SchedulerTests(unittest.TestCase):
    def test_morning_routine_tick(self) -> None:
        from nr2_scheduler import morning_routine_tick, scheduler_status

        store = _FakeStore()
        result = morning_routine_tick(store, force=True)
        self.assertTrue(result.get("ok"))
        status = scheduler_status(store)
        self.assertIn("ticksToday", status)


class QbConnectorTests(unittest.TestCase):
    def test_variance_detection(self) -> None:
        from qb_connector import detect_variance

        v = detect_variance(1000.0, 999.0)
        self.assertTrue(v["requiresReview"])

    def test_pull_payments_fallback(self) -> None:
        from qb_connector import pull_payments_read_only

        store = _FakeStore()
        result = pull_payments_read_only(store)
        self.assertTrue(result.get("ok"))


class Moonshot2ABCStubsTests(unittest.TestCase):
    def test_denial_predict_high_risk_without_narrative(self) -> None:
        from era_denial_trainer import predict_denial_risk

        result = predict_denial_risk(cdt_codes=["D2740"], payer_id="delta", has_narrative=False)
        self.assertTrue(result.get("ok"))
        self.assertGreaterEqual(result.get("riskScore", 0), 0.5)

    def test_scheduler_undo_within_window(self) -> None:
        from nr2_scheduler import morning_routine_tick, undo_autonomous_run

        store = _FakeStore()
        tick = morning_routine_tick(store, force=True)
        run_id = str(tick.get("runId") or "")
        self.assertTrue(run_id)
        undone = undo_autonomous_run(store, run_id=run_id)
        self.assertTrue(undone.get("undone"))

    def test_voip_twilio_twiml_stub(self) -> None:
        from voip_actions import create_twilio_stream_twiml

        twiml = create_twilio_stream_twiml(call_sid="CA123")
        self.assertIn("Stream", twiml)
        self.assertIn("CA123", twiml)

    def test_finetune_local_hal_dry_run(self) -> None:
        import subprocess
        import sys

        script = Path(__file__).resolve().parent / "scripts" / "finetune_local_hal.py"
        proc = subprocess.run(
            [sys.executable, str(script), "--dry-run"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("2C_stub", proc.stdout)


if __name__ == "__main__":
    unittest.main()
