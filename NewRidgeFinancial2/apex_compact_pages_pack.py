"""NR2 Apex compact + zero-scroll + KPI density — Moonshot helpers.

CONSULTS:
- MOONSHOT_COMPACT_PAGES_DETAILED_PLAN_2026-07-11.md
- MOONSHOT_ZERO_SCROLL_WIDGETS_CONSULT_2026-07-11.md (hal-10561)
- MOONSHOT_KPI_DENSITY_FIX_CONSULT_2026-07-12.md (hal-10562)

Claims: pipeline summary on main + kanban subpage (zero-scroll: no board on Overview).
HAL: no sole-l exemption — chat is a capped tile; full audit via Full Log strip.
KPI: ≤4 visible KPI tiles above fold; empty KPIs omit (never $0 pad).
"""

from __future__ import annotations

from typing import Any

# Moonshot Fibonacci zero-scroll height tiers (px)
MAX_PRIMARY_PX = 320
MAX_SECONDARY_PX = 240
MAX_MICRO_PX = 80
TABLE_ROW_CAP = 5
TABLE_ROW_CAP_HARD = 7
# Moonshot KPI density (hal-10562)
KPI_BUDGET_ABOVE_FOLD = 4
# First-viewport keep sets — tight zero-scroll (hal-10616). Target ≤5 tiles/page.
PAGE_FIRST_VIEW_KEEP: dict[str, frozenset[str]] = {
    "financial": frozenset(
        {
            "financial-command-strip",
            "financial-dual-trend",
            "provider-hbar",
            "ar-aging-chart",
            "bridge-errors",
        }
    ),
    "claims": frozenset(
        {
            "claims-executive-strip",
            "claims-aging-exposure",
            "claims-top-critical",
        }
    ),
    "hal": frozenset(
        {
            "hal-import-health",
            "hal-ask",
            "hal-recommended-actions",
            "hal-ai-insight",
            "hal-full-log",
        }
    ),
    "taxes": frozenset(
        {
            "tax-core-strip",
            "tax-year-status",
            "tax-bridge-waterfall",
            "tax-open-planning",
            "tax-disclaimer",
        }
    ),
    "softdent": frozenset(
        {
            "sd-vitals-strip",
            "collections-gauge",
            "sd-prod-trend",
            "softdent-collections-gap",
            "softdent-outstanding-claims-bridge",
        }
    ),
    "ar": frozenset(
        {
            "ar-vitals-strip",
            "ar-aging-chart",
            "ar-collection-task-list",
            "ar-follow-up",
            "ar-heatmap-grid",
        }
    ),
    "quickbooks": frozenset(
        {
            "qb-vitals-strip",
            "qb-net-profit-gap",
            "qb-payroll-gap",
            "qb-expense-hbar",
            "qb-ap-aging",
        }
    ),
    "office-manager": frozenset(
        {
            "om-vitals-strip",
            "om-daily-huddle",
            "operatory-util-trend",
            "om-priorities",
            "om-open-operatory",
        }
    ),
}

# Ops subpages: money/detail only — no scroll fluff (hal-10618 debris cleanup).
PAGE_OPS_KEEP: dict[str, frozenset[str]] = {
    "softdent": frozenset(
        {
            "softdent-aging-gap",
            "softdent-production-gap",
            "softdent-case-acceptance-gap",
            "softdent-scheduling-gap",
        }
    ),
    "claims": frozenset(
        {
            "claims-pipeline-summary",
            "claims-risk-analytics",
            "claim-status-lanes",
        }
    ),
    "financial": frozenset(
        {
            "reconciliation-status",
            "revenue-composition",
            "ebitda-station",
        }
    ),
    "hal": frozenset(
        {
            "hal-recommended-actions",
            "hal-ai-insight",
        }
    ),
    "ar": frozenset(
        {
            "collection-bullet",
            "ar-waterfall",
            "collectible-remainder",
        }
    ),
    "office-manager": frozenset(
        {
            "om-open-operatory",
            "operatory-util-trend",
            "patient-responsibility-calc",
        }
    ),
    "content": frozenset(
        {
            "narr-drafts",
            "narr-clinical-notes",
            "narr-template-library",
            "docs-queue",
            "docs-previews",
            "library-payers",
            "library-codes",
        }
    ),
    "documents": frozenset(
        {
            "docs-queue",
            "docs-previews",
        }
    ),
    "narratives": frozenset(
        {
            "narr-drafts",
            "narr-clinical-notes",
            "narr-template-library",
        }
    ),
    "library": frozenset(
        {
            "library-payers",
            "library-codes",
        }
    ),
}

# Hard-omit for zero-scroll (optional playbooks / dupes / overview kanban / HAL mosaics).
OMIT_OPTIONAL_ZERO_SCROLL_IDS = frozenset(
    {
        "softdent-gold-csv-drop-ops",
        "softdent-visual-ledger-recon",
        "softdent-tp-estimate-chips",
        "softdent-account-tx-coverage",
        "softdent-transaction-ledger",
        "softdent-gold-payment-pipeline",
        "softdent-patient-dossier",
        "softdent-print-preview-audit",
        "softdent-ui-honesty",
        "v-patient-aging",
        "v-case-acceptance",
        "v-scheduling-efficiency",
        "claims-open-kanban",
        "hal-mosaic-prod",
        "hal-mosaic-coll",
        "taxes-period-scrubber",
        "eob-posting-backlog",
        "clinical-signoff-queue",
        "expense-treemap",
        "deep-audit-status",
        "ar-aging-outlook",
        "ar-aging-pareto",
        "import-health-timeline",
        "era835-ingest-gap",
    }
)

# Chronic empty until SoftDent source lands — omit (do not scroll empty tiles).
# warming-bridge stays for cold stub only; final payloads omit it via omit_until_source.
OMIT_UNTIL_SOURCE_IDS = frozenset(
    {
        "claims-era-gauge",
        "denial-pareto",
        "verification-matrix",
        "gold-csv-ticket-ops",
        "import-cache-kpi",
        "import-health-monitor",
        "ins-patient-split",
        "preauth-aging-lanes",
        "payer-change-alerts",
        "warming-bridge",
        "kpi-data-pending",
    }
)

# Cap tiles per overview (incl. More Ops strip) for Fibonacci stage
MAX_FIRST_VIEWPORT_WIDGETS = 5
MAX_OPS_VIEWPORT_WIDGETS = 5

# Always keep on parent even if not in page keep set
_ALWAYS_KEEP_IDS = frozenset()


def collapse_empty_large(widget: dict[str, Any]) -> dict[str, Any]:
    """Empty l/xl/full → strip. Skip loading/skeleton (Moonshot R3)."""
    if not isinstance(widget, dict):
        return widget
    if widget.get("isSkeleton") is True:
        return widget
    status = str(widget.get("status") or "").lower()
    if status in {"loading", "skeleton", "warming"}:
        return widget
    if status != "empty":
        return widget
    size = str(widget.get("size") or "")
    if size not in {"l", "xl", "full", "large"}:
        return widget
    if widget.get("collapseWhenEmpty") is False:
        return widget
    out = dict(widget)
    out["collapseWhenEmpty"] = True
    out["size"] = "strip"
    out["compact"] = True
    return out


def omit_until_source_widgets(widgets: list[Any], *, page: str = "", sub: str = "") -> list[Any]:
    """Drop chronic empty + optional zero-scroll clutter (hal-10616)."""
    del sub  # reserved
    if not isinstance(widgets, list):
        return widgets
    page_key = str(page or "").strip().lower()
    out: list[Any] = []
    for w in widgets:
        if not isinstance(w, dict):
            out.append(w)
            continue
        wid = str(w.get("id") or "")
        status = str(w.get("status") or "").lower()
        if wid in OMIT_OPTIONAL_ZERO_SCROLL_IDS:
            continue
        if wid.endswith("-ops-more-omitted"):
            continue
        if wid == "collections-gauge" and page_key not in {"", "softdent"}:
            continue
        if wid in OMIT_UNTIL_SOURCE_IDS:
            # Omit while empty / warming. Show only when real status arrives (ok/warn with data).
            if status in {"empty", "awaiting-migration", "warming", ""}:
                continue
            if status == "warn" and wid in {
                "import-cache-kpi",
                "import-health-monitor",
                "gold-csv-ticket-ops",
            }:
                # Still no source file — keep ops quiet until CSV/ERA exists
                if not w.get("paymentLines") and not w.get("value") and not w.get("rows"):
                    continue
        out.append(w)
    return out


def omit_cross_page_duplicates(widgets: list[Any], *, page: str = "") -> list[Any]:
    """Keep collections-gauge on SoftDent only (hal-10616)."""
    if not isinstance(widgets, list):
        return widgets
    page_key = str(page or "").strip().lower()
    if page_key in {"", "softdent"}:
        return widgets
    return [
        w
        for w in widgets
        if not (isinstance(w, dict) and str(w.get("id") or "") == "collections-gauge")
    ]


# Preferred mosaic order within each page keep set (Fibonacci stage left→right / top→bottom)
PAGE_FIRST_VIEW_ORDER: dict[str, tuple[str, ...]] = {
    "softdent": (
        "sd-vitals-strip",
        "collections-gauge",
        "softdent-collections-gap",
        "softdent-outstanding-claims-bridge",
        "sd-prod-trend",
    ),
    "financial": (
        "financial-command-strip",
        "financial-dual-trend",
        "provider-hbar",
        "ar-aging-chart",
        "bridge-errors",
    ),
    "claims": (
        "claims-executive-strip",
        "claims-aging-exposure",
        "claims-top-critical",
    ),
    "hal": (
        "hal-import-health",
        "hal-ask",
        "hal-recommended-actions",
        "hal-ai-insight",
        "hal-full-log",
    ),
    "ar": (
        "ar-vitals-strip",
        "ar-aging-chart",
        "ar-collection-task-list",
        "ar-follow-up",
        "ar-heatmap-grid",
    ),
    "taxes": (
        "tax-core-strip",
        "tax-bridge-waterfall",
        "tax-open-planning",
        "tax-year-status",
        "tax-disclaimer",
    ),
    "quickbooks": (
        "qb-vitals-strip",
        "qb-net-profit-gap",
        "qb-payroll-gap",
        "qb-expense-hbar",
        "qb-ap-aging",
    ),
    "office-manager": (
        "om-vitals-strip",
        "om-daily-huddle",
        "operatory-util-trend",
        "om-priorities",
        "om-open-operatory",
    ),
    "content": (
        "content-hub-strip",
        "docs-queue",
        "narr-drafts",
        "narr-clinical-notes",
        "narr-template-library",
    ),
}

PAGE_FIRST_VIEW_KEEP["content"] = frozenset(PAGE_FIRST_VIEW_ORDER["content"])


def compact_widget_sizes(widgets: list[Any], *, page: str = "", sub: str = "") -> list[Any]:
    """Force denser sizes on remaining tiles (zero-scroll stage)."""
    if not isinstance(widgets, list):
        return widgets
    out: list[Any] = []
    for i, w in enumerate(widgets):
        if not isinstance(w, dict):
            out.append(w)
            continue
        item = dict(w)
        size = str(item.get("size") or "").lower()
        wtype = str(item.get("type") or "")
        item["compact"] = True
        if size in {"xl", "full", "large"}:
            item["size"] = "m" if i > 0 else "l"
        elif size == "l" and i > 0:
            item["size"] = "m"
        if wtype in {"executive-strip", "claims-executive-strip", "financial-command-strip"}:
            item["size"] = "strip" if size != "s" else size
            item.setdefault("maxHeight", MAX_MICRO_PX)
        elif wtype == "status":
            wid = str(item.get("id") or "")
            # Keep overview/ops chrome as micro strips (hal-10618)
            if wid.endswith(("-overview-open", "-ops-open", "-ops-empty", "-ops-pair")) and size in {
                "strip",
                "xs",
                "s",
                "",
            }:
                if wid.endswith("-ops-pair"):
                    item["size"] = "m"
                    item.setdefault("maxHeight", MAX_SECONDARY_PX)
                else:
                    item["size"] = "strip"
                    item.setdefault("maxHeight", MAX_MICRO_PX)
            else:
                # Pairable secondary tiles (hal-10617) — avoid stacking every status as micro strip
                if size in {"", "strip", "xs", "s"}:
                    item["size"] = "m"
                item.setdefault("maxHeight", MAX_SECONDARY_PX)
        elif wtype in {
            "chart",
            "dual-axis-trend",
            "line",
            "bar",
            "spark",
            "horizontal-bar",
            "radial-gauge",
        }:
            if size in {"", "strip", "xs", "s"}:
                item["size"] = "m"
            item.setdefault("maxHeight", MAX_SECONDARY_PX)
        elif str(item.get("size") or "") in {"s", "strip", "xs"}:
            item.setdefault("maxHeight", MAX_MICRO_PX)
        elif str(item.get("size") or "") == "m":
            item.setdefault("maxHeight", MAX_SECONDARY_PX)
        else:
            item.setdefault("maxHeight", MAX_PRIMARY_PX)
        out.append(item)
    return out


def apply_single_micro_band(widgets: list[Any], *, page: str = "", sub: str = "") -> list[Any]:
    """hal-10618: at most one micro (80px) band per page (HAL exempt for chat chrome)."""
    del sub
    if not isinstance(widgets, list):
        return widgets
    if str(page or "").strip().lower() == "hal":
        return widgets
    out: list[Any] = []
    micro_used = False
    for w in widgets:
        if not isinstance(w, dict):
            out.append(w)
            continue
        item = dict(w)
        if _is_hal_chat(item):
            out.append(item)
            continue
        size = _layout_size(item)
        wtype = str(item.get("type") or "")
        is_micro = size in {"strip", "xs", "s"} or wtype in {
            "executive-strip",
            "claims-executive-strip",
            "financial-command-strip",
        }
        if is_micro and size in {"strip", "xs", "s"}:
            if micro_used:
                item["size"] = "m"
                item["maxHeight"] = MAX_SECONDARY_PX
                item["tileClass"] = item.get("tileClass") or "tile-50"
            else:
                micro_used = True
                item["size"] = "strip" if size != "s" else size
                item.setdefault("maxHeight", MAX_MICRO_PX)
        out.append(item)
    return out


def omit_fresh_stale_alert(widgets: list[Any]) -> list[Any]:
    """Keep stale-import-alert only when it is actually alerting (hal-10619)."""
    if not isinstance(widgets, list):
        return widgets
    out: list[Any] = []
    for w in widgets:
        if isinstance(w, dict) and str(w.get("id") or "") == "stale-import-alert":
            if w.get("alert") is not True:
                continue
        out.append(w)
    return out


def _layout_size(widget: dict[str, Any]) -> str:
    return str(widget.get("size") or "s").lower()


def _is_hal_chat(widget: dict[str, Any]) -> bool:
    return str(widget.get("type") or "") == "hal-chat" or str(widget.get("id") or "") == "hal-ask"


def _is_band_hidden(widget: dict[str, Any]) -> bool:
    """Widgets CSS will hide — keep out of band width math (empty ≠ $0)."""
    if not isinstance(widget, dict):
        return True
    status = str(widget.get("status") or "").lower()
    wtype = str(widget.get("type") or "")
    if widget.get("keepEmpty") is True:
        return False
    if status in {"empty", "awaiting-migration"} and (
        widget.get("omitWhenEmpty") is True
        or widget.get("collapseWhenEmpty") is True
        or wtype == "kpi"
    ):
        return True
    return False


def _annotate_tile(widget: dict[str, Any], *, band: str, tile_class: str, height: int) -> dict[str, Any]:
    out = dict(widget)
    out["band"] = band
    out["tileClass"] = tile_class
    out["mosaicBand"] = band
    out.setdefault("maxHeight", height)
    out["zeroScroll"] = True
    return out


def pack_fibonacci_bands(
    widgets: list[Any], *, page: str = "", sub: str = ""
) -> tuple[list[Any], dict[str, Any]]:
    """Group widgets into Fibonacci bands (80 / 240 / 320) that tile edge-to-edge.

    Returns (annotated_widgets, mosaicLayout). Strips own micro bands; medium
    tiles pair as tile-50 in secondary; large/hal-chat own primary. Applies to
    every page/sub including ops — fills stage without auto-fill gaps.
    """
    del page, sub  # layout is size-driven for all pages
    if not isinstance(widgets, list):
        return widgets, {"mode": "fibonacci", "version": 1, "bands": []}

    annotated: list[Any] = []
    visible: list[dict[str, Any]] = []
    for w in widgets:
        if not isinstance(w, dict):
            annotated.append(w)
            continue
        item = dict(w)
        if _is_band_hidden(item):
            item.pop("band", None)
            item.pop("tileClass", None)
            item.pop("mosaicBand", None)
            annotated.append(item)
            continue
        visible.append(item)
    # Ops-open chips trail so money tiles pair first in the stage.
    visible.sort(key=lambda w: 1 if str(w.get("id") or "").endswith("-ops-open") else 0)

    bands: list[dict[str, Any]] = []
    placed: dict[str, dict[str, Any]] = {}
    i = 0
    while i < len(visible):
        w = visible[i]
        size = _layout_size(w)
        wid = str(w.get("id") or f"w{i}")

        if _is_hal_chat(w):
            tile = _annotate_tile(w, band="primary", tile_class="tile-100", height=MAX_PRIMARY_PX)
            placed[wid] = tile
            bands.append(
                {
                    "band": "primary",
                    "height": MAX_PRIMARY_PX,
                    "tiles": [{"id": wid, "tileClass": "tile-100"}],
                }
            )
            i += 1
            continue

        if size in {"strip", "xs"}:
            tile = _annotate_tile(w, band="micro", tile_class="tile-100", height=MAX_MICRO_PX)
            placed[wid] = tile
            bands.append(
                {
                    "band": "micro",
                    "height": MAX_MICRO_PX,
                    "tiles": [{"id": wid, "tileClass": "tile-100"}],
                }
            )
            i += 1
            continue

        if size == "s":
            group = [w]
            j = i + 1
            while j < len(visible) and len(group) < 3:
                nxt = visible[j]
                if _is_hal_chat(nxt) or _layout_size(nxt) != "s":
                    break
                group.append(nxt)
                j += 1
            tile_class = {1: "tile-100", 2: "tile-50", 3: "tile-33"}[len(group)]
            tiles_meta = []
            for g in group:
                gid = str(g.get("id") or "")
                placed[gid] = _annotate_tile(
                    g, band="micro", tile_class=tile_class, height=MAX_MICRO_PX
                )
                tiles_meta.append({"id": gid, "tileClass": tile_class})
            bands.append({"band": "micro", "height": MAX_MICRO_PX, "tiles": tiles_meta})
            i = j
            continue

        # Secondary / primary body tiles — prefer pairs (tile-50), else triple / solo.
        group = [w]
        j = i + 1
        alone_primary = size in {"l", "xl", "full"}
        while j < len(visible) and len(group) < 3 and not alone_primary:
            nxt = visible[j]
            ns = _layout_size(nxt)
            if _is_hal_chat(nxt) or ns in {"strip", "xs", "s"}:
                break
            group.append(nxt)
            j += 1
            if len(group) == 2:
                break

        if alone_primary and len(group) == 1:
            # Try to pair with next secondary-eligible sibling for a filled primary row.
            if j < len(visible):
                nxt = visible[j]
                ns = _layout_size(nxt)
                if not _is_hal_chat(nxt) and ns not in {"strip", "xs", "s"}:
                    group.append(nxt)
                    j += 1

        if len(group) == 1:
            alone = group[0]
            alone_size = _layout_size(alone)
            band = "primary" if alone_size in {"l", "xl", "full"} else "secondary"
            height = MAX_PRIMARY_PX if band == "primary" else MAX_SECONDARY_PX
            aid = str(alone.get("id") or "")
            placed[aid] = _annotate_tile(alone, band=band, tile_class="tile-100", height=height)
            bands.append(
                {
                    "band": band,
                    "height": height,
                    "tiles": [{"id": aid, "tileClass": "tile-100"}],
                }
            )
        elif len(group) == 2:
            band = (
                "primary"
                if any(_layout_size(g) in {"l", "xl", "full"} for g in group)
                else "secondary"
            )
            height = MAX_PRIMARY_PX if band == "primary" else MAX_SECONDARY_PX
            tiles_meta = []
            for g in group:
                gid = str(g.get("id") or "")
                placed[gid] = _annotate_tile(g, band=band, tile_class="tile-50", height=height)
                tiles_meta.append({"id": gid, "tileClass": "tile-50"})
            bands.append({"band": band, "height": height, "tiles": tiles_meta})
        else:
            height = MAX_SECONDARY_PX
            tiles_meta = []
            for g in group:
                gid = str(g.get("id") or "")
                placed[gid] = _annotate_tile(
                    g, band="secondary", tile_class="tile-33", height=height
                )
                tiles_meta.append({"id": gid, "tileClass": "tile-33"})
            bands.append({"band": "secondary", "height": height, "tiles": tiles_meta})
        i = j

    # Preserve original order in annotated list; overlay band fields.
    final: list[Any] = []
    for w in widgets:
        if not isinstance(w, dict):
            final.append(w)
            continue
        wid = str(w.get("id") or "")
        if wid in placed:
            final.append(placed[wid])
        else:
            item = dict(w)
            item.pop("band", None)
            item.pop("tileClass", None)
            item.pop("mosaicBand", None)
            final.append(item)

    layout = {
        "mode": "fibonacci",
        "version": 1,
        "bands": bands,
        "totalHeight": sum(int(b.get("height") or 0) for b in bands),
    }
    return final, layout


def is_empty_kpi(widget: dict[str, Any]) -> bool:
    """True when a KPI tile has no import-backed value (empty ≠ $0)."""
    if not isinstance(widget, dict):
        return False
    if str(widget.get("type") or "") != "kpi":
        return False
    if widget.get("keepEmpty") is True:
        return False
    status = str(widget.get("status") or "").lower()
    if status in {"empty", "awaiting-migration"}:
        return True
    return widget.get("value") is None or widget.get("value") == ""


def build_kpi_micro_strip(
    strip_id: str,
    label: str,
    pills: list[dict[str, Any]],
    *,
    hint: str = "",
    nav_hash: str | None = None,
    max_pills: int = KPI_BUDGET_ABOVE_FOLD,
) -> dict[str, Any]:
    """Pack up to 4 KPI pills into one executive-strip (counts as 1 mosaic slot)."""
    cleaned: list[dict[str, Any]] = []
    for p in pills[: max(1, int(max_pills))]:
        if not isinstance(p, dict):
            continue
        pill = dict(p)
        if "empty" not in pill:
            pill["empty"] = pill.get("value") is None or pill.get("value") == ""
        cleaned.append(pill)
    any_data = any(not p.get("empty") for p in cleaned)
    out: dict[str, Any] = {
        "id": strip_id,
        "type": "executive-strip",
        "label": label,
        "size": "strip",
        "compact": True,
        "maxHeight": MAX_MICRO_PX,
        "pills": cleaned,
        "status": "ok" if any_data else "empty",
        "emptyMessage": "Import data pending — empty stays empty (not $0).",
        "hint": hint or "KPI micro-strip · ≤4 pills · never invents dollars.",
        "collapseWhenEmpty": True,
        "kpiBudgetExempt": True,
        "aliasIds": [str(p.get("id") or "") for p in cleaned if p.get("id")],
    }
    if nav_hash:
        out["navHash"] = nav_hash
    return out


def pending_modules_chip(omitted_labels: list[str]) -> dict[str, Any] | None:
    """One composite status chip for multiple omitted empty KPIs."""
    labels = [str(x).strip() for x in omitted_labels if str(x).strip()]
    if not labels:
        return None
    n = len(labels)
    preview = ", ".join(labels[:3])
    if n > 3:
        preview += f" +{n - 3} more"
    return {
        "id": "kpi-data-pending",
        "type": "status",
        "label": "Data Pending",
        "size": "strip",
        "compact": True,
        "maxHeight": MAX_MICRO_PX,
        "status": "empty",
        "message": f"{n} module(s) pending",
        "hint": f"Omitted empty KPIs (not $0): {preview}",
        "collapseWhenEmpty": True,
        "kpiBudgetExempt": True,
    }


def apply_kpi_density_contract(
    widgets: list[Any],
    *,
    page: str = "",
    sub: str = "",
    budget: int = KPI_BUDGET_ABOVE_FOLD,
) -> list[Any]:
    """Omit empty KPIs; enforce ≤budget standalone KPI tiles on parent pages.

    Executive-strips / command strips are exempt (already packed). Subpages keep
    planning detail KPIs. Honesty: never pad empty with $0.
    """
    if not isinstance(widgets, list):
        return widgets
    is_subpage = bool(str(sub or "").strip())
    cap = max(0, int(budget))
    out: list[Any] = []
    omitted: list[str] = []
    kpi_kept = 0
    pending_inserted = False

    for w in widgets:
        if not isinstance(w, dict):
            out.append(w)
            continue
        item = dict(w)
        wtype = str(item.get("type") or "")
        if wtype == "kpi" and is_empty_kpi(item) and item.get("omitWhenEmpty") is not False:
            # Default: omit empty KPI mosaic slots
            if item.get("omitWhenEmpty") is True or item.get("collapseWhenEmpty") is not False:
                omitted.append(str(item.get("label") or item.get("id") or "KPI"))
                continue
        if wtype == "kpi" and not is_subpage and item.get("kpiBudgetExempt") is not True:
            if kpi_kept >= cap:
                if is_empty_kpi(item):
                    omitted.append(str(item.get("label") or item.get("id") or "KPI"))
                    continue
                # Excess populated KPIs → demote to micro strip chip (still visible, not tile flood)
                item["size"] = "xs"
                item["compact"] = True
                item["maxHeight"] = MAX_MICRO_PX
                item["kpiOverBudget"] = True
                item["hint"] = (
                    str(item.get("hint") or "")
                    + f" · Over KPI budget (>{cap}); demoted micro."
                ).strip(" ·")
            else:
                kpi_kept += 1
                item.setdefault("size", "s")
                item.setdefault("maxHeight", MAX_MICRO_PX)
        item["kpiDensity"] = True
        out.append(item)

    if omitted and not is_subpage and not pending_inserted:
        chip = pending_modules_chip(omitted)
        if chip:
            # Place after first strip/command if present, else at front
            insert_at = 0
            for i, x in enumerate(out):
                if isinstance(x, dict) and str(x.get("type") or "") in {
                    "financial-command-strip",
                    "executive-strip",
                    "claims-executive-strip",
                    "import-freshness",
                    "import-health",
                    "status",
                }:
                    insert_at = i + 1
            out.insert(insert_at, chip)

    return out


def apply_collapse_empty_all(widgets: list[Any], *, page: str = "") -> list[Any]:
    out: list[Any] = []
    # Exempt strips and analysis/gap surfaces from empty-omit (hal-10611)
    exempt_if_empty = {
        "financial-command-strip",
        "claims-executive-strip",
        "status",
        "import-freshness",
        "import-health",
        "analysis",
        "gap",
    }
    page_key = str(page or "").strip().lower()
    for w in widgets:
        if isinstance(w, dict):
            wid = str(w.get("id") or "")
            if wid in OMIT_UNTIL_SOURCE_IDS and str(w.get("status") or "").lower() in {
                "empty",
                "awaiting-migration",
                "warming",
                "",
            }:
                continue
            # Narratives/content: drop empty workflow placeholders (hal-10618)
            if wid in {"narr-workflow", "unknown-subpage"} and str(w.get("status") or "") == "empty":
                continue
            if page_key in {"narratives", "content"} and wid.startswith("narr-") and str(w.get("status") or "") == "empty":
                continue
            # Financial + claims + all pages: omit non-strip empty widgets (hal-10615)
            wtype = str(w.get("type") or "")
            if w.get("status") == "empty" and wtype not in exempt_if_empty:
                continue
            if page == "financial":
                if w.get("status") == "empty" and wtype not in exempt_if_empty:
                    continue
            out.append(collapse_empty_large(w))
        else:
            out.append(w)
    return out


def normalize_first_viewport(widgets: list[Any], *, page: str = "") -> list[Any]:
    """Cap first-viewport sizes: no xl above fold; at most one l in first six.

    Zero-scroll (hal-10561): HAL sole-l exemption REMOVED — chat follows same rules.
    """
    if not isinstance(widgets, list):
        return widgets
    large_seen = 0
    out: list[Any] = []
    for i, w in enumerate(widgets):
        if not isinstance(w, dict):
            out.append(w)
            continue
        item = dict(w)
        size = str(item.get("size") or "").lower()
        wtype = str(item.get("type") or "")
        wid = str(item.get("id") or "")

        if i < 6:
            if size == "xl":
                item["size"] = "l" if large_seen == 0 else "m"
                size = item["size"]
            if size in {"l", "large", "full"}:
                if size == "full" and wtype not in {"claims-workbench", "claims-kanban"}:
                    if wtype in {
                        "status",
                        "import-freshness",
                        "import-health",
                        "financial-command-strip",
                        "claims-executive-strip",
                        "executive-strip",
                    } or wid.endswith("-strip"):
                        item["size"] = "strip"
                    elif large_seen >= 1:
                        item["size"] = "m"
                    else:
                        item["size"] = "l"
                        large_seen += 1
                elif size in {"l", "large"}:
                    if large_seen >= 1:
                        item["size"] = "m"
                    else:
                        large_seen += 1
                elif size == "full" and wtype in {"claims-workbench", "claims-kanban"}:
                    # Main-page boards must not remain full; subpage may keep full.
                    item["size"] = "m"
        out.append(item)
    return out


def _tier_for_size(size: str, wtype: str) -> str:
    s = str(size or "").lower()
    t = str(wtype or "").lower()
    if s in {"strip", "xs"} or t in {
        "status",
        "kpi",
        "bullet",
        "credit-float",
        "financial-command-strip",
        "claims-executive-strip",
        "executive-strip",
    }:
        return "micro"
    if s in {"s"}:
        return "micro"
    if s in {"m"} or t in {"hal-chat", "ai-insight"}:
        return "secondary"
    if s in {"l", "large"}:
        return "primary"
    # xl/full → treat as primary then demote in apply_zero_scroll
    return "primary"


def apply_zero_scroll_contract(widgets: list[Any], *, page: str = "", sub: str = "") -> list[Any]:
    """Moonshot zero-scroll: hard height tiers, row caps, no HAL sole-l, no main kanban.

    Subpages (e.g. claims/kanban) may keep taller boards with internal scroll.
    """
    if not isinstance(widgets, list):
        return widgets
    page_key = str(page or "").strip().lower()
    sub_key = str(sub or "").strip().lower()
    is_subpage = bool(sub_key)
    out: list[Any] = []
    primary_seen = 0

    for w in widgets:
        if not isinstance(w, dict):
            out.append(w)
            continue
        item = dict(w)
        wtype = str(item.get("type") or "")
        wid = str(item.get("id") or "")
        size = str(item.get("size") or "").lower()

        # Claims Overview: never emit full workbench/kanban (subpage only)
        if (
            page_key == "claims"
            and not is_subpage
            and wtype in {"claims-workbench", "claims-kanban"}
        ):
            item["size"] = "s"
            item["compact"] = True
            item["rowCap"] = TABLE_ROW_CAP
            item["maxHeight"] = MAX_PRIMARY_PX
            item["hint"] = (
                str(item.get("hint") or "")
                + " · Open #claims/kanban for full board (zero-scroll)."
            ).strip(" ·")
            item["navHash"] = item.get("navHash") or "claims/kanban"

        # HAL: chat is a capped secondary tile — no sole-l / no 100vh fill
        if wtype == "hal-chat" or wid == "hal-ask":
            item["size"] = "m"
            item["compact"] = True
            item["maxHeight"] = MAX_PRIMARY_PX
            item["hint"] = "HAL command tile · capped for zero-scroll (no sole-l)."

        # Demote monuments on parent pages
        if not is_subpage:
            if size in {"xl", "full", "large"}:
                if primary_seen == 0 and wtype not in {
                    "claims-workbench",
                    "claims-kanban",
                    "hal-chat",
                }:
                    item["size"] = "l"
                    primary_seen += 1
                else:
                    item["size"] = "m"
            elif size == "l":
                if primary_seen >= 1:
                    item["size"] = "m"
                else:
                    primary_seen += 1

        size = str(item.get("size") or "").lower()
        tier = _tier_for_size(size, wtype)
        if "maxHeight" not in item or not isinstance(item.get("maxHeight"), int):
            if tier == "micro":
                item["maxHeight"] = MAX_MICRO_PX
            elif tier == "secondary":
                item["maxHeight"] = MAX_SECONDARY_PX
            else:
                item["maxHeight"] = MAX_PRIMARY_PX

        # Table / list row caps (main pages hard; subpages keep higher if already set)
        if not is_subpage:
            if wtype in {
                "claims-workbench",
                "claims-kanban",
                "claims-critical-actions",
                "data-table",
                "collection-task-list",
                "era-matching-table",
                "schedule-list",
            }:
                cap = item.get("rowCap")
                if not isinstance(cap, int) or cap > TABLE_ROW_CAP_HARD:
                    item["rowCap"] = TABLE_ROW_CAP
            # Critical claims list: Top 5
            if wid in {"claims-critical-actions", "claims-top-critical"} or wtype == "claims-critical-actions":
                item["rowCap"] = TABLE_ROW_CAP
                item["maxHeight"] = MAX_PRIMARY_PX
                item["size"] = item.get("size") if item.get("size") in {"s", "m", "l"} else "m"

        # Subpage boards: internal scroll allowed; still emit maxHeight for CSS clamp
        if is_subpage and wtype in {"claims-workbench", "claims-kanban"}:
            item.setdefault("maxHeight", 720)
            item.setdefault("rowCap", 50)
            item["internalScroll"] = True

        item["zeroScroll"] = True
        out.append(item)

    # HAL: ensure Full Log affordance after chat/posture
    if page_key == "hal" and not is_subpage:
        has_full_log = any(
            isinstance(x, dict) and str(x.get("id") or "") == "hal-full-log"
            for x in out
        )
        if not has_full_log:
            insert_at = 0
            for i, x in enumerate(out):
                if isinstance(x, dict) and str(x.get("type") or "") == "hal-chat":
                    insert_at = i + 1
                    break
            out.insert(
                insert_at,
                {
                    "id": "hal-full-log",
                    "type": "status",
                    "label": "Full Log",
                    "size": "strip",
                    "compact": True,
                    "status": "ok",
                    "message": "Open full HAL audit / message history",
                    "hint": "Zero-scroll: audit trail lives behind Full Log (not sole-l).",
                    "maxHeight": MAX_MICRO_PX,
                    "halAction": "open_hal_full_log",
                    "halActionLabel": "Full Log",
                    "zeroScroll": True,
                },
            )

    return out


def claims_pipeline_summary_widget(counts: dict[str, Any] | None, *, available: bool) -> dict[str, Any]:
    """Claims mode: summary strip + Open Kanban (not clipped board)."""
    c = counts if isinstance(counts, dict) else {}
    try:
        from apex_claims_narratives_pack import KANBAN_COLUMNS, KANBAN_LABELS

        keys = list(KANBAN_COLUMNS)
        labels = dict(KANBAN_LABELS)
    except Exception:
        keys = ["pending", "submitted", "denied", "paid"]
        labels = {k: k.title() for k in keys}

    pills: list[dict[str, Any]] = []
    for key in keys[:4]:
        pills.append(
            {
                "id": key,
                "label": str(labels.get(key) or key).title(),
                "value": int(c.get(key) or 0),
                "empty": not available,
            }
        )
    has = available and any(int(p.get("value") or 0) > 0 for p in pills)
    return {
        "id": "claims-pipeline-summary",
        "type": "claims-executive-strip",
        "label": "Claims Pipeline",
        "size": "s",
        "compact": True,
        "maxHeight": MAX_MICRO_PX,
        "zeroScroll": True,
        "pills": pills,
        "status": "ok" if has else "empty",
        "emptyMessage": "Import SoftDent claims — then open Kanban for the full board",
        "hint": "Zero-scroll pipeline · full workbench on #claims/kanban.",
        "navHash": "claims/kanban",
        "halAction": "open_claims_kanban",
        "halActionLabel": "Open Kanban",
        "aliasIds": ["claims-kanban-board"],
    }


def claims_top_critical_widget(rows: list[Any] | None, *, available: bool) -> dict[str, Any]:
    """Main Claims: Top 5 critical claims ≤320px (Moonshot page map)."""
    raw = [r for r in (rows or []) if isinstance(r, dict)]
    top = raw[:TABLE_ROW_CAP]
    has = available and len(top) > 0
    return {
        "id": "claims-top-critical",
        "type": "claims-critical-actions",
        "label": "Top 5 Critical Claims",
        "size": "m",
        "compact": True,
        "rowCap": TABLE_ROW_CAP,
        "maxHeight": MAX_PRIMARY_PX,
        "zeroScroll": True,
        "rows": top,
        "status": "ok" if has else "empty",
        "emptyMessage": "No critical claims in import — empty stays empty.",
        "hint": "Zero-scroll Top 5 · full board on #claims/kanban.",
        "navHash": "claims/kanban",
    }


def open_detail_strip(*, page: str, sub: str, label: str, message: str) -> dict[str, Any]:
    return {
        "id": f"{page}-{sub}-open",
        "type": "status",
        "label": label,
        "size": "strip",
        "compact": True,
        "maxHeight": MAX_MICRO_PX,
        "zeroScroll": True,
        "status": "ok",
        "message": message,
        "hint": f"Open #{page}/{sub}",
        "navHash": f"{page}/{sub}",
    }


def _is_always_keep(wid: str) -> bool:
    if wid in _ALWAYS_KEEP_IDS:
        return True
    if wid.endswith("-open"):
        return True
    return False


def partition_first_viewport(
    widgets: list[Any],
    *,
    page: str,
    sub: str = "",
) -> list[Any]:
    """Keep ≤MAX_FIRST_VIEWPORT_WIDGETS; demote the rest to #{page}/ops (hal-10616)."""
    if not isinstance(widgets, list):
        return widgets
    page_key = str(page or "").strip().lower()
    if str(sub or "").strip():
        return widgets
    keep_set = PAGE_FIRST_VIEW_KEEP.get(page_key)
    if not keep_set:
        return widgets

    kept: list[Any] = []
    demoted_labels: list[str] = []
    # Prefer keep-set order for stable Fibonacci mosaic
    by_id = {
        str(w.get("id") or ""): w
        for w in widgets
        if isinstance(w, dict) and str(w.get("id") or "")
    }
    order = PAGE_FIRST_VIEW_ORDER.get(page_key) or tuple(sorted(keep_set))
    for wid in order:
        if wid not in keep_set:
            continue
        w = by_id.get(wid)
        if w is None:
            continue
        if wid in OMIT_OPTIONAL_ZERO_SCROLL_IDS:
            continue
        kept.append(w)
        # SoftDent: use full five-tile money set (no reserved More Ops slot).
        soft_cap = (
            MAX_FIRST_VIEWPORT_WIDGETS
            if page_key == "softdent"
            else max(1, MAX_FIRST_VIEWPORT_WIDGETS - 1)
        )
        if len(kept) >= soft_cap:
            break
    # Any remaining keep-set members not in preferred order
    soft_cap = (
        MAX_FIRST_VIEWPORT_WIDGETS
        if page_key == "softdent"
        else max(1, MAX_FIRST_VIEWPORT_WIDGETS - 1)
    )
    if len(kept) < soft_cap:
        for wid in keep_set:
            if wid in by_id and all(str(x.get("id")) != wid for x in kept if isinstance(x, dict)):
                if wid in OMIT_OPTIONAL_ZERO_SCROLL_IDS:
                    continue
                kept.append(by_id[wid])
                if len(kept) >= soft_cap:
                    break
    for w in widgets:
        if not isinstance(w, dict):
            continue
        wid = str(w.get("id") or "")
        if wid in keep_set or _is_always_keep(wid):
            continue
        if wid in OMIT_OPTIONAL_ZERO_SCROLL_IDS or wid in OMIT_UNTIL_SOURCE_IDS:
            continue
        demoted_labels.append(str(w.get("label") or wid or "widget"))

    if page_key == "softdent":
        # Money truth on SoftDent overview; Ops is optional (#softdent/ops).
        return kept[:MAX_FIRST_VIEWPORT_WIDGETS]

    if not demoted_labels and len(kept) <= MAX_FIRST_VIEWPORT_WIDGETS:
        return kept[:MAX_FIRST_VIEWPORT_WIDGETS]

    n = len(demoted_labels)
    preview = ", ".join(demoted_labels[:3]) if demoted_labels else "ops"
    if n > 3:
        preview += f" +{n - 3} more"
    ops = open_detail_strip(
        page=page_key,
        sub="ops",
        label="More Ops",
        message=f"{n} widget(s) in Ops — {preview}" if n else "Open Ops",
    )
    # Prefer after command/executive strip if present
    insert_at = len(kept)
    for i, x in enumerate(kept):
        if isinstance(x, dict) and str(x.get("type") or "") in {
            "financial-command-strip",
            "claims-executive-strip",
            "executive-strip",
        }:
            insert_at = i + 1
            break
    kept.insert(insert_at, ops)
    return kept[:MAX_FIRST_VIEWPORT_WIDGETS]


def select_demoted_widgets(widgets: list[Any], *, page: str) -> list[Any]:
    """Build #{page}/ops payload: demoted keep-set capped for zero-scroll (hal-10616)."""
    if not isinstance(widgets, list):
        return []
    page_key = str(page or "").strip().lower()
    keep_set = PAGE_FIRST_VIEW_KEEP.get(page_key, frozenset())
    ops_keep = PAGE_OPS_KEEP.get(page_key)
    out: list[Any] = [
        {
            "id": f"{page_key}-overview-open",
            "type": "status",
            "label": "Back to Overview",
            "size": "strip",
            "compact": True,
            "maxHeight": MAX_MICRO_PX,
            "zeroScroll": True,
            "status": "ok",
            "message": f"Overview keeps the zero-scroll set · #{page_key}",
            "hint": f"Open #{page_key}",
            "navHash": page_key,
        }
    ]

    body: list[Any] = []
    for w in widgets:
        if not isinstance(w, dict):
            continue
        wid = str(w.get("id") or "")
        if wid in keep_set or _is_always_keep(wid):
            continue
        if wid in OMIT_OPTIONAL_ZERO_SCROLL_IDS:
            continue
        if wid in OMIT_UNTIL_SOURCE_IDS and str(w.get("status") or "").lower() in {
            "empty",
            "awaiting-migration",
            "warming",
            "",
        }:
            continue
        if ops_keep is not None and wid not in ops_keep:
            continue
        body.append(w)
        if len(body) >= max(1, MAX_OPS_VIEWPORT_WIDGETS - 1):
            break

    out.extend(body)
    if len(out) == 1:
        out.append(
            {
                "id": f"{page_key}-ops-empty",
                "type": "status",
                "label": "Ops",
                "size": "strip",
                "compact": True,
                "status": "empty",
                "message": "No demoted widgets for this page right now.",
                "emptyMessage": "Nothing to show in Ops — empty stays empty.",
                "maxHeight": MAX_MICRO_PX,
                "zeroScroll": True,
            }
        )
    # Pair thin OPS orphans (hal-10618): odd body after overview → pad so secondary tiles pair.
    body_n = max(0, len(out) - 1)
    if body_n % 2 == 1 and len(out) < MAX_OPS_VIEWPORT_WIDGETS:
        out.append(
            {
                "id": f"{page_key}-ops-pair",
                "type": "status",
                "label": "More detail",
                "size": "m",
                "compact": True,
                "maxHeight": MAX_SECONDARY_PX,
                "zeroScroll": True,
                "status": "ok",
                "message": f"Open #{page_key} subpages for deeper tools",
                "hint": "Paired filler so Ops bands stay edge-to-edge (no thin single).",
                "navHash": page_key,
            }
        )
    return out[:MAX_OPS_VIEWPORT_WIDGETS]
