"""HAL board-actions → optical page navigate (consent) — never invent routes/dollars."""

from __future__ import annotations

import unittest

from apex_backend import resolve_hal_board_actions
from nr2_optical_routes import enrich_navigate_actions, resolve_optical_href


class OpticalBoardNavigateTests(unittest.TestCase):
    def test_resolve_softdent_and_qb_hrefs(self) -> None:
        self.assertEqual(resolve_optical_href("softdent"), "/nr2-optical-page-softdent.html")
        self.assertEqual(resolve_optical_href("quickbooks"), "/nr2-optical-page-quickbooks.html")
        self.assertEqual(resolve_optical_href("qb"), "/nr2-optical-page-quickbooks.html")
        self.assertEqual(resolve_optical_href("ar"), "/nr2-optical-page-ar.html")
        self.assertEqual(resolve_optical_href("unknown-xyz"), "")

    def test_enrich_adds_href(self) -> None:
        acts = enrich_navigate_actions([{"type": "navigate", "page": "softdent"}])
        self.assertEqual(acts[0].get("href"), "/nr2-optical-page-softdent.html")
        self.assertTrue(acts[0].get("clientMustNavigate"))

    def test_board_actions_open_softdent_has_href(self) -> None:
        out = resolve_hal_board_actions({"query": "open SoftDent page", "page": "hal"})
        navs = [a for a in (out.get("actions") or []) if a.get("type") == "navigate"]
        self.assertTrue(navs, out)
        self.assertTrue(any(a.get("href") == "/nr2-optical-page-softdent.html" for a in navs), navs)

    def test_execute_navigate_resolves_page_key(self) -> None:
        from hal_brain_tools import execute_action, propose_action

        proposed = propose_action(
            kind="navigate",
            label="Open SoftDent",
            payload={"page": "softdent"},
        )
        self.assertFalse(proposed.get("consentRequired"))
        out = execute_action(action_id=proposed["action"]["actionId"], consent=False)
        self.assertTrue(out.get("ok"))
        result = out.get("result") or {}
        self.assertTrue(result.get("clientMustNavigate"))
        self.assertEqual(result.get("navigate"), "/nr2-optical-page-softdent.html")


if __name__ == "__main__":
    unittest.main()
