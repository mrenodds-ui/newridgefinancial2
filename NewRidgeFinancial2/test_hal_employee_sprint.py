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
        fd, name = tempfile.mkstemp(prefix="nr2-hal-employee-", suffix=".db")
        os.close(fd)
        self.db_path = Path(name)

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
        self.assertEqual(classify_query_intent("What is MetLife eligibility phone?"), "insurance_ops")
        self.assertEqual(classify_query_intent("allowed for D2740 on Delta Dental"), "insurance_ops")
        self.assertEqual(classify_query_intent("Delta denial code 16 narrative tips"), "insurance_ops")

    def test_resolve_lane_mapping(self) -> None:
        from nr2_hal_gateway import resolve_lane, route_by_complexity

        self.assertEqual(resolve_lane("chat8b")["model"], "hal-local:30b-a3b")
        self.assertEqual(resolve_lane("reason21b")["lane"], "reason21b")
        self.assertEqual(resolve_lane("reason21b")["model"], "hal-local:30b-a3b")
        self.assertEqual(resolve_lane("escalate30b")["model"], "hal-local:30b-a3b")
        self.assertEqual(resolve_lane("coder32b")["model"], "hal-local:30b-a3b")
        lane = route_by_complexity("simple hello", shift_context={"tier": 1})
        self.assertEqual(lane, "chat8b")
        lane_esc = route_by_complexity("deep root cause investigation", shift_context={"tier": 5})
        self.assertEqual(lane_esc, "escalate30b")
        # Insurance ops must not auto-escalate to 30B
        self.assertEqual(
            route_by_complexity("MetLife eligibility phone", shift_context={"tier": 1}),
            "chat8b",
        )
        self.assertEqual(
            route_by_complexity("allowed for D2740 on Delta Dental", shift_context={"tier": 1}),
            "chat8b",
        )
        self.assertNotEqual(
            route_by_complexity("Draft clinical narrative for crown on tooth 14", shift_context={"tier": 1}),
            "chat8b",
        )

    def test_stale_financial_blocked(self) -> None:
        from nr2_hal_gateway import evaluate_query

        readiness = {"level": "stale", "ok": False, "loadedAt": "2020-01-01T00:00:00Z", "ageHours": 72}
        result = evaluate_query(query="What is our revenue?", readiness=readiness)
        self.assertFalse(result.get("ok"))
        self.assertEqual(result.get("error"), "HAL_UNAVAILABLE_STALE_DATA")

    def test_import_gap_reply_names_optional_qb_datasets(self) -> None:
        from nr2_hal_gateway import evaluate_query, try_import_gap_reply

        readiness = {
            "level": "fresh",
            "ok": True,
            "summary": {"connected": 17, "missing": 2, "stale": 0, "missingOptional": 2},
            "completeness": {"ok": True, "scorePct": 100.0, "required": 4, "connected": 4},
            "datasetGaps": [
                {
                    "datasetKey": "quickbooks.ap",
                    "severity": "optional",
                    "status": "missing",
                    "detail": "Dataset file not found in import cache.",
                },
                {
                    "datasetKey": "quickbooks.payroll",
                    "severity": "optional",
                    "status": "missing",
                    "detail": "Dataset file not found in import cache.",
                },
            ],
            "blocking": [],
        }
        local = try_import_gap_reply(
            "To address the issue of missing import datasets and ensure KPIs are reliable",
            readiness,
        )
        self.assertIsNotNone(local)
        assert local is not None
        self.assertIn("quickbooks.payroll", local["text"])
        self.assertIn("quickbooks.ap", local["text"])
        self.assertIn("optional", local["text"].lower())
        self.assertNotIn("firewall", local["text"].lower())

        result = evaluate_query(
            query="Which import datasets are missing?",
            readiness=readiness,
            store=_FakeStore(),
        )
        self.assertTrue(result.get("ok"))
        self.assertEqual(result.get("model"), "local-import-gaps")
        self.assertIn("quickbooks.payroll", result.get("text") or "")

    def test_import_readiness_context_lists_named_gaps(self) -> None:
        from nr2_hal_gateway import build_import_readiness_context

        ctx = build_import_readiness_context(
            {
                "level": "fresh",
                "ok": True,
                "summary": {"connected": 17, "missing": 2, "stale": 0, "missingOptional": 2},
                "completeness": {"ok": True, "scorePct": 100.0, "required": 4, "connected": 4},
                "datasetGaps": [
                    {"datasetKey": "quickbooks.payroll", "severity": "optional", "status": "missing"},
                ],
            }
        )
        self.assertIn("quickbooks.payroll", ctx)
        self.assertIn("Named gaps", ctx)

    @mock.patch("nr2_hal_gateway.call_ollama_chat")
    def test_soft_stale_analytical_watermark(self, mock_chat: mock.MagicMock) -> None:
        from nr2_hal_gateway import evaluate_query

        mock_chat.return_value = {"ok": True, "body": {"message": {"content": "Trend summary text."}}}
        readiness = {"level": "stale", "ok": False, "loadedAt": "2020-01-01T00:00:00Z", "ageHours": 12}
        result = evaluate_query(query="Why did A/R increase?", readiness=readiness, store=_FakeStore())
        self.assertTrue(result.get("ok"))
        self.assertIn("SOFT-STALE", result.get("text") or "")

    def test_build_chat_messages_injects_memoai_guidance(self) -> None:
        from nr2_hal_gateway import build_chat_messages

        messages, _, _, _ = build_chat_messages(
            query="Can HAL email the payer narrative without consent?",
            readiness={"level": "fresh"},
        )
        guidance = [m for m in messages if m.get("role") == "system" and "Governed memory matches:" in str(m.get("content") or "")]
        self.assertTrue(guidance, "expected MemoAI memory guidance system message")

    def test_build_chat_messages_skips_duplicate_memory_guidance(self) -> None:
        from nr2_hal_gateway import build_chat_messages

        existing = "Durable HAL knowledge (guidance only; does not override runtime checks or guardrails):\n- Existing memory"
        messages, _, _, _ = build_chat_messages(
            query="Can HAL email the payer narrative without consent?",
            readiness={"level": "fresh"},
            system_prompt=existing,
        )
        governed = [m for m in messages if "Governed memory matches:" in str(m.get("content") or "")]
        self.assertEqual(governed, [])
        self.assertEqual(messages[0]["content"], existing)

    def test_build_chat_messages_injects_payer_reference(self) -> None:
        from nr2_hal_gateway import build_chat_messages

        messages, _, _, _ = build_chat_messages(
            query="MetLife denied crown D2740 code 16 narrative appeal",
            readiness={"level": "fresh"},
        )
        payer_msgs = [m for m in messages if "Payer reference matches (" in str(m.get("content") or "")]
        self.assertTrue(payer_msgs, "expected payer reference guidance system message")

    def test_build_chat_messages_injects_eligibility_cache(self) -> None:
        from eligibility_cache_store import upsert_eligibility_entry
        from nr2_hal_gateway import build_chat_messages

        upsert_eligibility_entry(
            {
                "payerName": "Gateway Test Payer",
                "payerId": "GWTEST",
                "source": "unit_test",
                "annualMaxRemaining": 800,
                "ttlHours": 72,
            }
        )
        messages, _, _, _ = build_chat_messages(
            query="Gateway Test Payer deductible remaining annual max",
            readiness={"level": "fresh"},
        )
        elig_msgs = [m for m in messages if "Cached eligibility context (" in str(m.get("content") or "")]
        self.assertTrue(elig_msgs, "expected eligibility cache guidance system message")

    def test_compile_claim_payer_guidance_generic_honesty(self) -> None:
        from nr2_hal_gateway import compile_claim_payer_guidance, query_wants_claim_payer_join

        self.assertTrue(query_wants_claim_payer_join("Which payer is on the denied claim?"))
        self.assertFalse(query_wants_claim_payer_join("What is our revenue this month?"))
        # With inbox claims (often generic Insurance), guidance should still surface honesty text.
        text = compile_claim_payer_guidance("Which payer is on the denied claim?")
        if text:
            self.assertIn("Claim ↔ payer reference joins", text)


class EmployeeWorkflowTests(unittest.TestCase):
    def test_deposit_reconciliation_draft(self) -> None:
        from hal_employee_workflows import draft_deposit_reconciliation

        store = _FakeStore()
        result = draft_deposit_reconciliation(store, {"bankAmount": 1000, "ledgerAmount": 950})
        self.assertTrue(result["ok"])
        self.assertEqual(result["variance"], 50.0)
        self.assertFalse(result.get("seededFromAnalytics"))

    def test_deposit_reconciliation_seeds_from_analytics(self) -> None:
        from unittest.mock import patch

        from hal_employee_workflows import draft_deposit_reconciliation

        store = _FakeStore()
        fake = {
            "hasData": True,
            "period": "2026-06",
            "softdentCollections": 100000.0,
            "quickbooksDeposits": 94000.0,
            "variancePct": -6.0,
            "summary": "2026-06: QuickBooks deposits are -6.0% vs SoftDent collections.",
        }
        with patch("nr2_analytics.collection_deposit_variance", return_value=fake):
            result = draft_deposit_reconciliation(store, {})
        self.assertTrue(result["ok"])
        self.assertTrue(result.get("seededFromAnalytics"))
        self.assertEqual(result["draft"]["bankAmount"], 94000.0)
        self.assertEqual(result["draft"]["ledgerAmount"], 100000.0)
        self.assertEqual(result["variance"], -6000.0)
        self.assertEqual(result["draft"]["depositDate"], "2026-06")

    def test_claim_preflight(self) -> None:
        from hal_employee_workflows import stage_claim_preflight

        store = _FakeStore()
        result = stage_claim_preflight(
            store,
            {
                "claimId": "C1",
                "payer": "Delta Dental",
                "narrativePresent": True,
                "attachmentsReady": True,
                "feeScheduleVerified": True,
                "insuranceVerified": True,
                "clinicalSummaryLinked": True,
            },
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "ready")

    def test_appeal_packet_local_only(self) -> None:
        from hal_employee_workflows import build_appeal_packet

        store = _FakeStore()
        result = build_appeal_packet(
            store,
            {
                "claimId": "DS-20260709-1",
                "payer": "Insurance",
                "procedure": "D2740 Crown",
                "status": "Denied",
                "denialReason": "missing narrative",
                "narrative": "",
            },
        )
        self.assertTrue(result["ok"])
        self.assertTrue(result.get("localOnly"))
        self.assertTrue(result.get("notSubmitted"))
        self.assertTrue(result.get("consentRequiredForZip"))
        self.assertIn("preflight", result)
        self.assertIn("denialRisk", result)
        self.assertTrue(result.get("narrative"))
        self.assertTrue(result.get("finishLine", {}).get("narrativeReady"))
        self.assertTrue(result["preflight"].get("genericPayer") or result["denialRisk"].get("genericPayer"))

    def test_appeal_packet_attaches_clinical_notes(self) -> None:
        from unittest.mock import patch

        from hal_employee_workflows import build_appeal_packet

        notes = [
            {
                "PatientName": "Jane Doe",
                "MRN": "P100",
                "NoteDate": "2026-06-01",
                "Provider": "Dr. Test",
                "Procedure": "D2740 Crown",
                "ClinicalNote": "Tooth #14 fractured; crown indicated after endo.",
            }
        ]
        store = _FakeStore()
        with patch("hal_employee_workflows._load_clinical_note_rows", return_value=notes):
            result = build_appeal_packet(
                store,
                {
                    "claimId": "CLM-NOTE-1",
                    "payer": "Delta Dental",
                    "procedure": "D2740 Crown",
                    "status": "Denied",
                    "patient": "Jane Doe",
                    "patientId": "P100",
                    "narrative": "",
                },
            )
        self.assertTrue(result["ok"])
        self.assertTrue(result.get("clinicalNotesAttached"))
        self.assertEqual(len(result.get("clinicalNotes") or []), 1)
        self.assertIn("fractured", result.get("narrative") or "")
        self.assertTrue(result.get("finishLine", {}).get("clinicalNotesAttached"))
        self.assertTrue((result.get("preflight") or {}).get("checklist", {}).get("clinicalSummaryLinked"))

    def test_confirm_era_match_flips_status(self) -> None:
        from hal_employee_workflows import confirm_era_match, list_pending_era_matches, process_eob_match

        store = _FakeStore()
        staged = process_eob_match(
            store,
            {"referenceId": "ERA-99", "claimId": "", "paidAmount": 150, "sourceType": "era"},
        )
        # Force review status with empty claim to simulate pending
        with store._connect() as conn:
            conn.execute(
                "UPDATE nr2_eob_match SET status = 'review', matched_claim_id = '' WHERE id = ?",
                (staged["id"],),
            )
        pending = list_pending_era_matches(store, limit=10)
        self.assertGreaterEqual(pending["count"], 1)
        confirmed = confirm_era_match(
            store,
            {"matchId": staged["id"], "claimId": "CLM-100", "paidAmount": 150, "cdt": "D1110", "payer": "Delta"},
        )
        self.assertTrue(confirmed["ok"])
        self.assertEqual(confirmed["status"], "matched")
        self.assertEqual(confirmed["claimId"], "CLM-100")
        after = list_pending_era_matches(store, limit=50)
        self.assertFalse(any(i["id"] == staged["id"] for i in after.get("items") or []))

    def test_shift_handoff_includes_era_and_claims(self) -> None:
        from unittest.mock import patch

        from hal_employee_workflows import compile_shift_handoff, process_eob_match

        store = _FakeStore()
        process_eob_match(store, {"referenceId": "ERA-H1", "claimId": "C1", "paidAmount": 10})
        with store._connect() as conn:
            conn.execute("UPDATE nr2_eob_match SET status = 'review' WHERE reference_id = 'ERA-H1'")
        with patch(
            "hal_employee_workflows._claims_ops_snapshot",
            return_value={
                "total": 2,
                "denied": 1,
                "genericPayer": 1,
                "namedPayer": 1,
                "agingOver60": 1,
                "agingOver90": 0,
                "topAging": [{"claimId": "C9", "ageDays": 70, "status": "denied"}],
            },
        ), patch(
            "hal_employee_workflows._softdent_named_payer_brief",
            return_value={"summary": "Named payers on 1/2 claim(s); 1 still generic \"Insurance\".", "namedPayer": 1, "genericPayer": 1},
        ), patch("hal_employee_workflows.generate_month_end_tasks", return_value={"tasks": [], "ok": True}):
            handoff = compile_shift_handoff(store, employee_id="HAL")
        self.assertTrue(handoff["ok"])
        self.assertIn("ERA/EOB Pending Review", handoff["reportMarkdown"])
        self.assertIn("Claims Ops", handoff["reportMarkdown"])
        self.assertIn("Posting Queue", handoff["reportMarkdown"])
        self.assertIn("SoftDent claims/ODBC", handoff["reportMarkdown"])
        self.assertGreaterEqual(handoff.get("pendingEraMatches") or 0, 1)

    def test_claim_preflight_flags_generic_payer(self) -> None:
        from hal_employee_workflows import stage_claim_preflight

        store = _FakeStore()
        result = stage_claim_preflight(
            store,
            {
                "claimId": "DS-20260709-1",
                "payer": "Insurance",
                "procedure": "D2740 Crown",
                "narrativePresent": True,
                "attachmentsReady": True,
                "feeScheduleVerified": True,
                "insuranceVerified": True,
                "clinicalSummaryLinked": True,
            },
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "staged")
        self.assertTrue(result.get("genericPayer"))
        self.assertFalse(result["checklist"].get("namedPayerPresent"))
        self.assertTrue(any("Named payer" in g for g in result.get("gaps") or []))

    def test_preflight_joins_eligibility_cache(self) -> None:
        from unittest.mock import patch

        from hal_employee_workflows import stage_claim_preflight

        store = _FakeStore()
        elig = {
            "payerName": "Delta Dental",
            "deductibleRemaining": 50,
            "annualMaxRemaining": 1200,
            "cachedAt": "2026-07-09T12:00:00+00:00",
        }
        with patch("hal_employee_workflows._match_eligibility_for_claim", return_value=elig):
            result = stage_claim_preflight(
                store,
                {
                    "claimId": "CLM-ELIG-1",
                    "payer": "Delta Dental",
                    "procedure": "D2740 Crown",
                    "narrativePresent": True,
                    "attachmentsReady": True,
                    "feeScheduleVerified": True,
                    "clinicalSummaryLinked": True,
                    # omit insuranceVerified — must come from eligibility join
                },
            )
        self.assertTrue(result["ok"])
        self.assertTrue(result["checklist"].get("insuranceVerified"))
        self.assertEqual((result.get("eligibilityHit") or {}).get("payerName"), "Delta Dental")
        self.assertEqual(result["status"], "ready")

    def test_preflight_named_payer_without_eligibility(self) -> None:
        from unittest.mock import patch

        from hal_employee_workflows import stage_claim_preflight

        store = _FakeStore()
        with patch("hal_employee_workflows._match_eligibility_for_claim", return_value=None):
            result = stage_claim_preflight(
                store,
                {
                    "claimId": "CLM-NOELIG",
                    "payer": "Delta Dental",
                    "procedure": "D2740",
                    "narrativePresent": True,
                    "attachmentsReady": True,
                    "feeScheduleVerified": True,
                    "clinicalSummaryLinked": True,
                },
            )
        self.assertTrue(result["ok"])
        self.assertFalse(result["checklist"].get("insuranceVerified"))
        self.assertEqual(result["status"], "staged")
        self.assertTrue(any("Eligibility" in g for g in result.get("gaps") or []))

    def test_underpay_seed_includes_call_script(self) -> None:
        from hal_employee_workflows import seed_underpay_to_collections

        store = _FakeStore()
        result = seed_underpay_to_collections(
            store,
            {
                "shortfall": 200,
                "patientName": "Script Patient",
                "claimId": "CLM-SCR-1",
                "cdt": "D2740",
                "payer": "Delta",
            },
        )
        self.assertTrue(result["ok"])
        self.assertTrue(result.get("seeded"))
        self.assertTrue(result.get("callScript"))
        self.assertIn("Script Patient", result["callScript"])

    def test_call_outcome_updates_collections_queue(self) -> None:
        from hal_employee_workflows import schedule_call_task, update_collections_queue_status
        from voip_actions import initiate_call, log_call_outcome

        store = _FakeStore()
        scheduled = schedule_call_task(
            store,
            {
                "patientName": "Queue Patient",
                "patientId": "P-Q1",
                "balance": 150,
                "phone": "555-0100",
                "scenario": "collections",
            },
        )
        self.assertTrue(scheduled["ok"])
        with store._connect() as conn:
            dial = initiate_call(
                conn,
                phone_number="555-0100",
                patient_id="P-Q1",
                reason="collections",
                queue_id=scheduled["id"],
            )
            self.assertTrue(dial["ok"])
            logged = log_call_outcome(
                conn,
                call_id=dial["callId"],
                outcome="promised",
                notes="Will pay Friday",
                store=store,
            )
        self.assertTrue(logged["ok"])
        self.assertEqual(logged.get("queueStatus"), "promised")
        updated = update_collections_queue_status(
            store, {"queueId": scheduled["id"], "status": "closed", "outcome": "paid"}
        )
        self.assertTrue(updated["ok"])
        self.assertEqual(updated["status"], "closed")

    def test_schedule_call_claims_aging_scenario(self) -> None:
        from hal_employee_workflows import schedule_call_task

        store = _FakeStore()
        result = schedule_call_task(
            store,
            {
                "patientName": "Aging Patient",
                "claimId": "CLM-OLD-1",
                "payer": "Delta Dental",
                "scenario": "claims_aging",
                "phone": "555-0199",
            },
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result.get("scenario"), "claims_aging")
        self.assertIn("outstanding insurance claim", (result.get("callScript") or "").lower())

    def test_appeal_includes_payer_narrative_themes(self) -> None:
        from unittest.mock import patch

        from hal_employee_workflows import build_appeal_packet

        store = _FakeStore()
        fake_join = {
            "claimPayer": "Delta Dental",
            "matchedName": "Delta Dental",
            "eligibilityNotes": "800-555-0100",
            "narrativeNotes": "Code 16 often needs narrative.",
            "commonDenialCodes": ["16", "97"],
        }
        with patch("payer_reference_store.enrich_claim_payer", return_value=fake_join), patch(
            "hal_employee_workflows._load_clinical_note_rows", return_value=[]
        ):
            result = build_appeal_packet(
                store,
                {
                    "claimId": "CLM-THEME-1",
                    "payer": "Delta Dental",
                    "procedure": "D2740 Crown",
                    "status": "Denied",
                    "narrative": "",
                },
            )
        self.assertTrue(result["ok"])
        self.assertIn("Code 16", result.get("narrative") or "")
        self.assertIn("16", " ".join(str(c) for c in ((result.get("payerJoin") or {}).get("commonDenialCodes") or [])))

    def test_stage_pending_appeal_packets_caps_and_skips_generic(self) -> None:
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        from hal_employee_workflows import stage_pending_appeal_packets

        store = _FakeStore()
        rows = [
            {
                "ClaimId": "CLM-DENY-1",
                "Payer": "Delta Dental",
                "ClaimStatus": "Denied",
                "Procedure": "D2740",
                "Days": 70,
            },
            {
                "ClaimId": "DS-GENERIC",
                "Payer": "Insurance",
                "ClaimStatus": "Denied",
                "Procedure": "D1110",
                "Days": 90,
            },
            {
                "ClaimId": "CLM-AGE-2",
                "Payer": "MetLife",
                "ClaimStatus": "Submitted",
                "Procedure": "D4341",
                "Days": 65,
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            with patch("hal_employee_workflows._load_claim_rows_for_autonomy", return_value=rows), patch(
                "outbound_actions._exports_subdir", return_value=out
            ), patch(
                "hal_employee_workflows.build_appeal_packet",
                side_effect=lambda _s, p: {
                    "ok": True,
                    "claimId": p.get("claimId"),
                    "claim": {"id": p.get("claimId"), "payer": p.get("payer")},
                    "narrative": "draft",
                    "gaps": [],
                    "preflight": {},
                    "denialRisk": {},
                    "payerJoin": None,
                    "clinicalNotesAttached": False,
                    "finishLine": {"zipNeedsConsent": True},
                    "summary": "ok",
                },
            ):
                result = stage_pending_appeal_packets(store, limit=5)
        self.assertTrue(result["ok"])
        ids = {i["claimId"] for i in result.get("items") or []}
        self.assertIn("CLM-DENY-1", ids)
        self.assertIn("CLM-AGE-2", ids)
        self.assertNotIn("DS-GENERIC", ids)
        self.assertLessEqual(result.get("count") or 0, 5)
        self.assertTrue(result.get("localOnly"))
        self.assertTrue(result.get("notSubmitted"))

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
        self.assertTrue(result.get("summary"))

    def test_month_end_tasks_analytics_deposit_signal(self) -> None:
        from unittest.mock import patch

        from hal_employee_workflows import generate_month_end_tasks

        store = _FakeStore()
        fake_snap = {
            "collectionDepositVariance": {
                "hasData": True,
                "period": "2026-06",
                "variancePct": -12.0,
                "thresholdPct": 8,
                "summary": "2026-06: deposits -12% vs collections",
            },
            "collectionLag": {"hasData": True, "avgLagDays": 52, "summary": "Lag 52 days"},
            "alertTicker": {"items": []},
        }
        with patch("nr2_analytics.analytics_snapshot", return_value=fake_snap), patch(
            "daily_closeout.build_daily_closeout", return_value={"overall": "green"}
        ):
            result = generate_month_end_tasks(store, period="2026-06")
        self.assertTrue(result["ok"])
        self.assertTrue(result.get("analyticsGrounded"))
        self.assertIn("deposit_variance", result.get("signals") or [])
        deposit = next(t for t in result["tasks"] if t["id"] == "deposit-recon")
        self.assertEqual(deposit["priority"], "high")

    def test_scrub_fee_vs_paid_underpay(self) -> None:
        from unittest.mock import patch

        from hal_employee_workflows import list_collections_queue, scrub_fee_vs_paid

        fake_fee = {
            "ok": True,
            "code": "D2740",
            "sourceSheet": "test",
            "amounts": [{"scheduleId": "delta", "scheduleName": "Delta PPO", "amount": 900.0}],
        }
        store = _FakeStore()
        with patch("fee_schedule_store.lookup_cdt", return_value=fake_fee):
            result = scrub_fee_vs_paid(
                {
                    "cdt": "D2740",
                    "payer": "Delta",
                    "paidAmount": 700,
                    "billedAmount": 1200,
                    "claimId": "CLM-UP-1",
                    "patientName": "Underpay Patient",
                },
                store=store,
            )
        self.assertTrue(result["ok"])
        self.assertTrue(result.get("underpaid"))
        self.assertEqual(result.get("classification"), "underpaid")
        self.assertTrue((result.get("collectionsSeed") or {}).get("seeded"))
        queued = list_collections_queue(store, limit=20)
        self.assertTrue(any("underpay" in str(i.get("notes") or "").lower() for i in queued.get("items") or []))

    def test_softdent_named_payer_brief(self) -> None:
        from unittest.mock import patch

        from hal_employee_workflows import _softdent_named_payer_brief

        with patch(
            "hal_employee_workflows._claims_ops_snapshot",
            return_value={
                "total": 3,
                "denied": 0,
                "genericPayer": 2,
                "namedPayer": 1,
                "agingOver60": 0,
                "agingOver90": 0,
                "topAging": [],
            },
        ), patch(
            "softdent_odbc_extract.read_extract_status",
            return_value={
                "ok": True,
                "odbcConfigured": True,
                "stale": False,
                "queriesConfigured": 1,
                "configuredQueryTables": ["sd_patients"],
                "tableCounts": {"sd_claims": 0},
                "nextSteps": ["SOFTDENT_ODBC_CLAIMS_QUERY is not configured"],
            },
        ):
            brief = _softdent_named_payer_brief()
        self.assertTrue(brief.get("ok"))
        self.assertEqual(brief.get("namedPayer"), 1)
        self.assertEqual(brief.get("genericPayer"), 2)
        self.assertFalse(brief.get("hasClaimsQuery"))
        self.assertIn("generic", (brief.get("summary") or "").lower())

    def test_scrub_fee_vs_paid_contractual(self) -> None:
        from unittest.mock import patch

        from hal_employee_workflows import scrub_fee_vs_paid

        fake_fee = {
            "ok": True,
            "code": "D2740",
            "amounts": [{"scheduleId": "delta", "scheduleName": "Delta PPO", "amount": 900.0}],
        }
        with patch("fee_schedule_store.lookup_cdt", return_value=fake_fee):
            result = scrub_fee_vs_paid(
                {"cdt": "D2740", "payer": "Delta", "paidAmount": 900, "remark": "CO-45"}
            )
        self.assertTrue(result["ok"])
        self.assertTrue(result.get("contractualOk"))
        self.assertEqual(result.get("classification"), "contractual_ok")

    def test_collections_queue_ranks_90_first(self) -> None:
        from unittest.mock import patch

        from hal_employee_workflows import generate_collections_queue

        store = _FakeStore()
        rows = [
            {"Patient": "Low", "Balance": 50, "Aging": "0-30"},
            {"Patient": "High", "Balance": 400, "Aging": "90+"},
            {"Patient": "Mid", "Balance": 200, "Aging": "31-60"},
        ]
        with patch("hal_employee_workflows._load_ar_rows", return_value=rows):
            result = generate_collections_queue(store, limit=10)
        self.assertTrue(result["ok"])
        self.assertEqual(result["items"][0]["patientName"], "High")
        self.assertEqual(result["items"][0]["priority"], "high")


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


class UsDentalCarrierCatalogTests(unittest.TestCase):
    def test_catalog_summary_and_search(self) -> None:
        from us_dental_carrier_catalog import catalog_summary, format_carrier_hits, search_carriers

        summary = catalog_summary()
        self.assertTrue(summary["ok"])
        self.assertGreaterEqual(summary["carrierCount"], 30)
        self.assertGreaterEqual(summary["planFamilyCount"], 80)

        hits = search_carriers("Guardian Advantage Premier", limit=3)
        self.assertTrue(hits)
        self.assertTrue(any("guardian" in str(h.get("id") or "").lower() for h in hits))
        text = format_carrier_hits(hits)
        self.assertIn("plan families", text.lower())

        ks = search_carriers("Kansas Delta Dental", limit=3)
        self.assertTrue(ks)
        self.assertTrue(any(h.get("id") == "delta-dental" for h in ks))


if __name__ == "__main__":
    unittest.main()
