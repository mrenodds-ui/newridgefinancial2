"""Patient dossier — empty≠$0 + HAL summarize intent parsing."""

from __future__ import annotations

import unittest

from patient_dossier import (
    _safe_money,
    extract_patient_ref_from_query,
    format_hal_patient_summary_reply,
    query_refers_to_bound_patient,
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
        self.assertTrue(query_touches_patient_summary("What's the copay for this patient?"))
        self.assertTrue(query_touches_patient_summary("about this patient"))
        self.assertTrue(query_refers_to_bound_patient("Tell me about this patient"))
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
        self.assertIsNone(extract_patient_ref_from_query("What's the copay for this patient?"))

    def test_this_patient_unbound_asks_for_id(self) -> None:
        import sys
        import types

        fake = types.ModuleType("nr2_rbac")
        fake.has_capability = lambda *_a, **_k: True  # type: ignore[attr-defined]
        fake.current_role = lambda: "office_manager"  # type: ignore[attr-defined]
        prev = sys.modules.get("nr2_rbac")
        sys.modules["nr2_rbac"] = fake
        try:
            out = format_hal_patient_summary_reply(
                "What's the copay for this patient?",
                session_id="missing-session",
            )
        finally:
            if prev is None:
                sys.modules.pop("nr2_rbac", None)
            else:
                sys.modules["nr2_rbac"] = prev
        self.assertEqual(out.get("intent"), "policy:patient-summary-unbound")
        self.assertIn("No SoftDent patient is bound", out.get("text") or "")

    def test_this_patient_expired_context_hints_rebind(self) -> None:
        import sys
        import types
        from datetime import datetime, timedelta, timezone
        from pathlib import Path
        import tempfile

        fake = types.ModuleType("nr2_rbac")
        fake.has_capability = lambda *_a, **_k: True  # type: ignore[attr-defined]
        fake.current_role = lambda: "office_manager"  # type: ignore[attr-defined]
        prev = sys.modules.get("nr2_rbac")
        sys.modules["nr2_rbac"] = fake
        try:
            import hal_session_store as store

            with tempfile.TemporaryDirectory() as tmp:
                store.SESSIONS_DIR = Path(tmp)
                sid = "expired-bound-session"
                path = store._session_path(sid)
                expired = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
                header = {
                    "type": "session",
                    "sessionId": sid,
                    "createdAt": datetime.now(timezone.utc).isoformat(),
                    "meta": {
                        "patientContext": {
                            "patientId": "999",
                            "patientHash": "ABCD",
                            "initials": "ZZ",
                            "expiresAt": expired,
                        }
                    },
                }
                path.write_text(
                    __import__("json").dumps(header) + "\n",
                    encoding="utf-8",
                )
                out = format_hal_patient_summary_reply(
                    "What's the copay for this patient?",
                    session_id=sid,
                )
        finally:
            if prev is None:
                sys.modules.pop("nr2_rbac", None)
            else:
                sys.modules["nr2_rbac"] = prev
        self.assertEqual(out.get("intent"), "policy:patient-summary-unbound")
        self.assertIn("expired", (out.get("text") or "").lower())


if __name__ == "__main__":
    unittest.main()
