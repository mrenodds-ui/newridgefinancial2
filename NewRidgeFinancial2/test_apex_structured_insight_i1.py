"""Phase I1 validation — structured insight schemas (no Ollama required)."""

from __future__ import annotations

import unittest

from apex_backend import build_apex_widgets, resolve_hal_board_actions
from apex_orchestrator_pack import orchestrator_status
from apex_structured_insight_pack import (
    attach_insight_to_orchestrator_result,
    parse_and_validate_insight_text,
    validate_insight,
    wants_structured_insight,
)


GOOD_KPI = {
    "widget_type": "kpi-card",
    "title": "Production snapshot",
    "data": {"value": 12000.5, "unit": "dollars", "trend_direction": "up", "trend_percent": 3.2},
    "source_refs": ["softdent:register:2026-07-11"],
    "confidence": "high",
    "explanation": "From SoftDent register import.",
    "action_cta": {"label": "Open SoftDent", "route": "softdent"},
}

GOOD_ALERT = {
    "widget_type": "alert-banner",
    "title": "Collections pending",
    "data": {"severity": "warn", "message": "Collections daysheet not in latest import.", "value": None, "unit": "text"},
    "source_refs": ["import:health:2026-07-11"],
    "confidence": "medium",
    "explanation": "Honest empty — do not invent collections.",
}


class StructuredInsightPhaseI1Tests(unittest.TestCase):
    def test_orchestrator_phase_i1(self):
        st = orchestrator_status()
        self.assertEqual(st.get("phase"), "I4")
        self.assertTrue(st.get("structuredInsights"))
        self.assertTrue(st.get("unifiedDb"))

    def test_valid_kpi(self):
        r = validate_insight(GOOD_KPI)
        self.assertTrue(r.get("ok"), r)
        self.assertTrue(r.get("structured"))
        self.assertEqual(r["insight"]["widget_type"], "kpi-card")

    def test_valid_alert(self):
        r = validate_insight(GOOD_ALERT)
        self.assertTrue(r.get("ok"), r)

    def test_rejects_phi(self):
        bad = dict(GOOD_KPI)
        bad["explanation"] = "Patient SSN 123-45-6789"
        r = validate_insight(bad)
        self.assertFalse(r.get("ok"))

    def test_rejects_numeric_without_source(self):
        bad = dict(GOOD_KPI)
        bad["source_refs"] = []
        r = validate_insight(bad)
        self.assertFalse(r.get("ok"))

    def test_rejects_bad_schema(self):
        r = validate_insight({"widget_type": "kpi-card", "title": "x"})
        self.assertFalse(r.get("ok"))

    def test_parse_from_fenced_markdown(self):
        text = "Here you go:\n```json\n" + __import__("json").dumps(GOOD_KPI) + "\n```\n"
        r = parse_and_validate_insight_text(text)
        self.assertTrue(r.get("ok"), r)

    def test_parse_fallback_on_prose(self):
        r = parse_and_validate_insight_text("Production looks fine this week.")
        self.assertFalse(r.get("ok"))
        self.assertEqual(r.get("fallback"), "markdown")

    def test_attach_insight_to_result(self):
        fake = {"ok": True, "text": __import__("json").dumps(GOOD_ALERT)}
        out = attach_insight_to_orchestrator_result(
            fake, query="monthly practice health audit", require_structured=True
        )
        self.assertTrue(out.get("structured"))
        self.assertIn("insight", out)
        self.assertTrue(out.get("insightWidget", {}).get("status") == "ok")

    def test_wants_structured(self):
        self.assertTrue(wants_structured_insight("give me a structured insight as json"))
        self.assertTrue(wants_structured_insight("monthly practice health audit"))
        self.assertFalse(wants_structured_insight("hello"))

    def test_hal_page_has_insight_widget(self):
        out = build_apex_widgets("hal")
        ids = {w.get("id") for w in (out.get("widgets") or []) if isinstance(w, dict)}
        self.assertIn("hal-ai-insight", ids)

    def test_hal_focus_ai_insight(self):
        r = resolve_hal_board_actions({"query": "show ai insight widget", "page": "financial"})
        actions = r.get("actions") or []
        self.assertTrue(any(a.get("widgetId") == "hal-ai-insight" for a in actions))


if __name__ == "__main__":
    unittest.main()
