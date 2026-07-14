"""Tests for Moonshot compact + zero-scroll professional pages pack."""

from __future__ import annotations

import unittest

from apex_compact_pages_pack import (
    KPI_BUDGET_ABOVE_FOLD,
    MAX_MICRO_PX,
    MAX_PRIMARY_PX,
    MAX_SECONDARY_PX,
    TABLE_ROW_CAP,
    apply_collapse_empty_all,
    apply_kpi_density_contract,
    apply_zero_scroll_contract,
    build_kpi_micro_strip,
    claims_pipeline_summary_widget,
    claims_top_critical_widget,
    collapse_empty_large,
    is_empty_kpi,
    normalize_first_viewport,
)


class CollapseEmptyTests(unittest.TestCase):
    def test_empty_large_collapses(self) -> None:
        w = {"id": "x", "size": "xl", "status": "empty", "label": "X"}
        out = collapse_empty_large(w)
        self.assertEqual(out["size"], "strip")
        self.assertTrue(out["compact"])

    def test_loading_not_collapsed(self) -> None:
        w = {"id": "x", "size": "xl", "status": "loading"}
        self.assertEqual(collapse_empty_large(w)["size"], "xl")

    def test_skeleton_flag_not_collapsed(self) -> None:
        w = {"id": "x", "size": "full", "status": "empty", "isSkeleton": True}
        self.assertEqual(collapse_empty_large(w)["size"], "full")

    def test_populated_unchanged(self) -> None:
        w = {"id": "x", "size": "l", "status": "ok"}
        self.assertEqual(collapse_empty_large(w)["size"], "l")

    def test_opt_out(self) -> None:
        w = {"id": "x", "size": "l", "status": "empty", "collapseWhenEmpty": False}
        self.assertEqual(collapse_empty_large(w)["size"], "l")

    def test_apply_all(self) -> None:
        widgets = [
            {"id": "a", "size": "xl", "status": "empty"},
            {"id": "b", "size": "m", "status": "ok"},
            {"id": "c", "type": "status", "size": "l", "status": "empty"},
        ]
        out = apply_collapse_empty_all(widgets)
        # Non-exempt empties are omitted (hal-10615); status empties still collapse→strip.
        ids = [w.get("id") for w in out if isinstance(w, dict)]
        self.assertNotIn("a", ids)
        self.assertIn("b", ids)
        self.assertIn("c", ids)
        by_id = {w["id"]: w for w in out if isinstance(w, dict)}
        self.assertEqual(by_id["b"]["size"], "m")
        self.assertEqual(by_id["c"]["size"], "strip")


class FirstViewportTests(unittest.TestCase):
    def test_hal_chat_no_longer_sole_l(self) -> None:
        """Zero-scroll: HAL sole-l exemption removed."""
        widgets = [
            {"id": "h", "type": "kpi", "size": "s", "status": "ok"},
            {"id": "hal-ask", "type": "hal-chat", "size": "l", "status": "ok"},
            {"id": "x", "type": "chart", "size": "xl", "status": "ok"},
        ]
        out = normalize_first_viewport(widgets, page="hal")
        # Chat follows normal first-viewport rules (may stay l as first large)
        self.assertIn(out[1]["size"], {"l", "m"})
        zs = apply_zero_scroll_contract(out, page="hal")
        chat = next(w for w in zs if w.get("id") == "hal-ask")
        self.assertEqual(chat["size"], "m")
        self.assertEqual(chat["maxHeight"], MAX_PRIMARY_PX)
        self.assertTrue(any(w.get("id") == "hal-full-log" for w in zs))

    def test_xl_demoted_above_fold(self) -> None:
        widgets = [{"id": f"w{i}", "type": "chart", "size": "xl", "status": "ok"} for i in range(3)]
        out = normalize_first_viewport(widgets, page="financial")
        self.assertEqual(out[0]["size"], "l")
        self.assertEqual(out[1]["size"], "m")


class ZeroScrollContractTests(unittest.TestCase):
    def test_height_caps_and_row_cap(self) -> None:
        widgets = [
            {"id": "a", "type": "chart", "size": "xl", "status": "ok"},
            {"id": "b", "type": "claims-workbench", "size": "full", "status": "ok", "rowCap": 50},
            {"id": "c", "type": "kpi", "size": "s", "status": "ok"},
        ]
        out = apply_zero_scroll_contract(widgets, page="claims")
        self.assertTrue(all(w.get("zeroScroll") for w in out if isinstance(w, dict)))
        wb = next(w for w in out if w["id"] == "b")
        self.assertEqual(wb["rowCap"], TABLE_ROW_CAP)
        self.assertLessEqual(wb["maxHeight"], MAX_PRIMARY_PX)
        kpi = next(w for w in out if w["id"] == "c")
        self.assertEqual(kpi["maxHeight"], MAX_MICRO_PX)

    def test_kanban_subpage_keeps_internal_scroll(self) -> None:
        widgets = [
            {"id": "claims-kanban-board", "type": "claims-workbench", "size": "full", "status": "ok"},
        ]
        out = apply_zero_scroll_contract(widgets, page="claims", sub="kanban")
        self.assertTrue(out[0].get("internalScroll"))
        self.assertEqual(out[0].get("rowCap"), 50)

    def test_widget_max_height_unit(self) -> None:
        """Unit gate: widget renders ≤ cap after contract."""
        w = apply_zero_scroll_contract(
            [{"id": "x", "type": "waterfall", "size": "xl", "status": "ok"}],
            page="taxes",
        )[0]
        self.assertLessEqual(int(w["maxHeight"]), MAX_PRIMARY_PX)
        self.assertIn(w["size"], {"l", "m"})


class ClaimsPipelineTests(unittest.TestCase):
    def test_summary_pills(self) -> None:
        w = claims_pipeline_summary_widget(
            {"submitted": 2, "pendingReview": 1, "eraMatched": 0, "denied": 3, "paid": 4},
            available=True,
        )
        self.assertEqual(w["id"], "claims-pipeline-summary")
        self.assertEqual(w["size"], "s")
        self.assertEqual(w["navHash"], "claims/kanban")
        self.assertEqual(len(w["pills"]), 4)

    def test_top_critical_five(self) -> None:
        rows = [{"claimId": f"c{i}", "ageDays": i} for i in range(12)]
        w = claims_top_critical_widget(rows, available=True)
        self.assertEqual(w["id"], "claims-top-critical")
        self.assertEqual(len(w["rows"]), TABLE_ROW_CAP)
        self.assertEqual(w["maxHeight"], MAX_PRIMARY_PX)
        self.assertEqual(w["rowCap"], TABLE_ROW_CAP)


class KpiDensityTests(unittest.TestCase):
    def test_empty_kpi_detection(self) -> None:
        self.assertTrue(is_empty_kpi({"type": "kpi", "status": "empty", "value": None}))
        self.assertTrue(is_empty_kpi({"type": "kpi", "value": None}))
        self.assertFalse(is_empty_kpi({"type": "kpi", "value": 12, "status": "ok"}))
        self.assertFalse(is_empty_kpi({"type": "chart", "status": "empty"}))

    def test_omit_empty_kpis_and_pending_chip(self) -> None:
        widgets = [
            {"id": "cmd", "type": "financial-command-strip", "status": "ok"},
            {"id": "a", "type": "kpi", "label": "A", "status": "empty", "value": None, "omitWhenEmpty": True},
            {"id": "b", "type": "kpi", "label": "B", "status": "empty", "value": None, "collapseWhenEmpty": True},
            {"id": "c", "type": "kpi", "label": "C", "value": 10, "status": "ok"},
        ]
        out = apply_kpi_density_contract(widgets, page="taxes")
        ids = [w.get("id") for w in out if isinstance(w, dict)]
        self.assertNotIn("a", ids)
        self.assertNotIn("b", ids)
        self.assertIn("c", ids)
        self.assertIn("kpi-data-pending", ids)

    def test_budget_caps_standalone_kpis(self) -> None:
        widgets = [
            {"id": f"k{i}", "type": "kpi", "label": f"K{i}", "value": i + 1, "status": "ok"}
            for i in range(6)
        ]
        out = apply_kpi_density_contract(widgets, page="softdent", budget=KPI_BUDGET_ABOVE_FOLD)
        full = [w for w in out if w.get("type") == "kpi" and not w.get("kpiOverBudget")]
        over = [w for w in out if w.get("kpiOverBudget")]
        self.assertEqual(len(full), KPI_BUDGET_ABOVE_FOLD)
        self.assertEqual(len(over), 2)
        self.assertEqual(over[0]["size"], "xs")

    def test_subpage_keeps_empty_when_keep_empty(self) -> None:
        widgets = [
            {
                "id": "tax-book-net",
                "type": "kpi",
                "label": "Book",
                "value": None,
                "status": "empty",
                "keepEmpty": True,
                "omitWhenEmpty": False,
            }
        ]
        out = apply_kpi_density_contract(widgets, page="taxes", sub="planning")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["id"], "tax-book-net")

    def test_micro_strip_packs_four(self) -> None:
        w = build_kpi_micro_strip(
            "x-strip",
            "Vitals",
            [
                {"id": "a", "label": "A", "value": 1},
                {"id": "b", "label": "B", "value": None},
                {"id": "c", "label": "C", "value": 3},
                {"id": "d", "label": "D", "value": 4},
                {"id": "e", "label": "E", "value": 5},
            ],
        )
        self.assertEqual(w["type"], "executive-strip")
        self.assertEqual(len(w["pills"]), 4)
        self.assertTrue(w.get("kpiBudgetExempt"))


if __name__ == "__main__":
    unittest.main()
