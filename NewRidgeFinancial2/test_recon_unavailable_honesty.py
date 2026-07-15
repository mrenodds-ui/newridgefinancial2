"""SoftDent×QB reconciliation honesty — UNAVAILABLE, never fake COHERENT (empty ≠ $0)."""

from __future__ import annotations

import unittest


class ReconUnavailableHonestyTests(unittest.TestCase):
    def test_clean_slate_payload_never_coherent(self) -> None:
        from apex_backend import _clean_slate_unavailable

        out = _clean_slate_unavailable("hal_reconciliation")
        self.assertFalse(out.get("ok"))
        self.assertFalse(out.get("available"))
        self.assertFalse(out.get("coherent"))
        self.assertEqual(out.get("status"), "UNAVAILABLE")
        self.assertTrue(out.get("emptyNotZero"))
        self.assertIn("never invent coherent", (out.get("detail") or "").lower())

    def test_unavailable_widget(self) -> None:
        from apex_backend import _reconciliation_unavailable_widget

        w = _reconciliation_unavailable_widget()
        self.assertEqual(w.get("status"), "unavailable")
        self.assertFalse(w.get("coherent"))
        self.assertIn("UNAVAILABLE", w.get("message") or "")
        self.assertNotIn("COHERENT", (w.get("message") or "").upper().replace("NEVER COHERENT", ""))


if __name__ == "__main__":
    unittest.main()
