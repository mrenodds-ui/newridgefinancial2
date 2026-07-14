# Moonshot AI — KPI Density Fix & Re-Report (CONSULT ONLY)

**Date:** 2026-07-12  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10561 + hal-local:32b  
**Prior:** zero-scroll + compact (hal-10561); still too many KPI tiles  
**Script:** `scripts/run_moonshot_kpi_density_fix_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> alot of kpis appear ask moonshot ai how to fix and rereport

---

# Verdict  
Height caps in hal-10561 stopped vertical scroll but failed to constrain KPI cardinality, leaving Taxes and SoftDent emitting 7–13 tiles that still consume first-viewport mosaic slots; fix requires a hard “≤4 visible KPIs above fold” budget with automatic collapse of empty planning placeholders into status strips or subpages.

## 0. Operator Intent (quote verbatim; confirm consult-only)

> "alot of kpis appear"

**Confirmed CONSULT-ONLY.** No code will be generated, committed, or applied to `hal-10561` until you explicitly respond with “approve,” “proceed,” or “do it.” This is a systems-design prescription only.

## 1. Why So Many KPIs Appear (post-hal-10561 diagnosis)

**Blunt diagnosis:** Zero-scroll capped *pixel height* but not *KPI count*, so empty and planning tiles still render as mosaic slots (crowded voids).

| Builder | Emits | Problem |
|---------|-------|---------|
| `_taxes_widgets` | ~13 | **Worst offender.** Dumps individual planning placeholders (Book Net Income, Est. Owner Tax, Est. K-1 Ordinary, Modeled Officer W-2, Quarterly Estimates, etc.) as separate `l`/`m` tiles even when theoretical or empty. Empty KPIs still occupy grid slots. |
| `_softdent_widgets` | ~7 | Production, utilization, timeline, and treatment-plan counts emitted as separate secondary KPIs instead of packed into a single vital-signs strip. |
| `_quickbooks_widgets` | ~6 | Expense and categorization KPIs compete with the chart for first-viewport dominance. |
| `_financial_widgets_from_reports` | 4+ secondary + vitals | Secondary row (Claims, Denied, Treatment Plans) duplicates metrics that should be absorbed into the vital-signs strip (4 pills). |
| `_ar_widgets`, `_office_manager_widgets`, etc. | ~5 each | Uncollated operational counts render as individual chips rather than a unified status row. |

**Empty vs. Populated:**  
`_empty_kpi` and `_money_kpi` with `null` values still emit JSON widgets; the frontend renders them as blank chips or “—” tiles, creating visual noise without information.  
**Vitals vs. Secondary vs. Tax Planning:**  
The Financial Executive Console established a “Strip 2 = 3–4 KPI micro-cards ONLY” standard (Prior Moonshot contract). Taxes ignored this standard, treating planning scenarios as primary KPIs rather than collapsible notes.

## 2. KPI Density Contract (hard rules)

**First-Viewport KPI Budget (1920×1080 compact):**  
- **Hard ceiling:** ≤4 visible KPI tiles (size `s` or `m`) above the fold **OR** 1 vital-signs strip (4 pills) + 1 secondary micro-row (max 4 chips).  
- **Row Cap enforcement:** `rowCap 5` applies to total tiles; KPI-specific sub-cap of 4 enforced at builder level.

**Empty KPI Rule:**  
Any KPI with `null`, `None`, or `empty` status auto-collapses to a single “Data Pending” status chip (size `xs`, ≤40 px) or is **omitted entirely**; never render empty mosaic slots.  
*Honesty:* Empty ≠ $0; do not pad.

**Planning vs. Actual:**  
Tax planning scenarios (modeled W-2, quarterly estimates, hypothetical K-1s) do **not** qualify as primary KPIs. They must collapse into a single “Tax Planning (expandable)” strip or move to `#taxes/planning` subpage. Only *book-actual* metrics (e.g., “Book Net Income” when QuickBooks is linked) may appear as a single primary tile.

**Vital Absorption:**  
Primary money metrics (Revenue, Collections, AR, EBITDA) must live in the vital-signs strip (4 pills) or one primary trend tile. No duplicate secondary KPIs for the same metric.

**Pack Related Empties:**  
If multiple KPIs are empty (e.g., SoftDent treatment plans + case acceptance unavailable), render **one** composite status chip: “Practice data pending (3 modules)” rather than three empty boxes.

## 3. Fix Package (THE recommended work package)

**Name:** KPI Cap & Collapse Contract (hal-10562)  
**Why now:** Height-only zero-scroll leaves the mosaic overcrowded; Taxes dumps 13 tiles, making it impossible to scan vitals.  
**Effort:** 1–2 dev days (backend builder edits + CSS collapse rules).

**REAL files:**
- `NewRidgeFinancial2/apex_backend.py` (`_taxes_widgets`, `_softdent_widgets`, `_money_kpi`, `_count_kpi`, `_empty_kpi` collapse logic)
- `NewRidgeFinancial2/apex_compact_pages_pack.py` (`normalize_first_viewport` KPI budget enforcement, `collapse_empty_large` extension)
- `NewRidgeFinancial2/apex_financial_console_pack.py` (secondary KPI row cap enforcement)
- `NewRidgeFinancial2/site/apex-bridge.css` (`.kpi-empty { display: none }` or height-collapse rules)

**Phases:**
1. **Audit & Flag** – Mark empty-vs-populated emit sites in `_taxes_widgets` and `_softdent_widgets`; add `collapseWhenEmpty: true` to KPI schema.
2. **Collapse Logic** – Modify `_empty_kpi` to return `None` (omitted) or a single collapsed status chip; modify `_money_kpi`/`_count_kpi` to skip rendering when value is `None` and `collapseWhenEmpty` is set.
3. **Tax Planning Isolation** – Route all planning KPIs (Est. Owner Tax, K-1 Ordinary, Modeled W-2, Quarterly Estimates) to `#taxes/planning` subpage; main Taxes page shows single “Tax Status” chip (book connected / not connected).
4. **Pack Secondary** – Convert SoftDent, QuickBooks, AR, and Office Manager secondary KPIs into single vital-style strips (4 micro-pills) using `_micro_strip_pack` helper.
5. **Validation Gate** – Browser hook `__nr2AssertKpiBudget(page, max=4)` validates ≤4 KPI tiles visible above fold at 1920×1080 compact.

**Validation Gate:**  
1920×1080, 100% zoom, compact density:  
- No page shows >4 KPI tiles (excluding chart canvases) before first scroll action.  
- Taxes page shows ≤1 status chip + 1 bridge chart in first viewport.

## 4. Page-by-Page KPI Map

| Page | Current KPI problem | Keep (≤4) | Collapse/hide/subpage | Target first viewport |
|------|---------------------|-----------|----------------------|---------------------|
| **Financial** | Vital strip (4) + secondary row (4) + EBITDA tile = 9+ slots | Vital-signs strip (4 pills: Revenue, Collections, AR, EBITDA) only | Secondary claims/treatment KPIs → pack into 1 micro-strip OR move to `#financial/operations` subpage | Vital strip + 1 primary trend chart |
| **Taxes** | ~13 planning KPIs (Book Net, Est Tax, K-1, W-2, Quarterly, etc.) | 1 “Tax Year Status” chip (book connected / planning available) | All planning estimates → `#taxes/planning` subpage; empty placeholders hidden entirely | Single status chip + 1 book-to-tax bridge chart |
| **SoftDent** | ~7 production/util/timeline KPIs | Vital-style strip: Production, Collections, Utilization, Adjustments (4 pills) | Treatment plan counts → collapse if empty or move to `#softdent/plans` | 4-pill strip + production trend chart |
| **QuickBooks** | ~6 expense/category KPIs | Strip: Expense YTD, Uncategorized, Bank Sync, Net Income (4) | Detail categorization KPIs → `#quickbooks/detail` subpage | 4-pill strip + expense breakdown chart |
| **AR** | ~5 aging/outlook KPIs | Strip: Total AR, 90+, Collections Today, Risk Score (4) | Aging heatmap/waterfall → secondary tile (max 240px) | 4-pill strip + aging chart |
| **Claims** | Already compliant per hal-10561 | Pipeline summary + Top 5 critical count (1 tile) | Denied claims detail → kanban subpage (already shipped) | Pipeline strip + Top 5 list |
| **HAL** | ~6 status KPIs | 1 “System Health” status chip + Chat tile | Log counts → Full Log strip (already shipped) | Health chip + Chat (capped 320px) |
| **Narratives** | ~4 KPIs | Composer status + Library count (2) | Unused templates → hidden if empty | Composer preview + slim library strip |
| **Documents** | ~5 upload/processing KPIs | Pending uploads + Processed today (2) | Storage quotas → settings page | Upload status + thumb grid (≤200px) |
| **Library** | ~4 KPIs | Items count (1) | Category breakdown → filter dropdown | Search bar + count chip |
| **Office Manager** | ~5 KPIs | Strip: Tasks, Alerts, Sync status, Users (4) | Detailed task list → `#office-manager/tasks` subpage | 4-pill strip |

## 5. Report Summary (executive bullets for operator)

- **Root cause identified:** hal-10561 fixed vertical scroll via `maxHeight` tiers but did not enforce a cardinality cap; Taxes emits 13 tiles, SoftDent 7, creating “KPI warehouse” despite compact density.
- **Fix direction:** Hard “≤4 visible KPIs above fold” budget per page; empty placeholders collapse to a single status chip or are omitted (never $0 padded).
- **Tax planning quarantine:** Move ~9 planning-scenario KPIs from main Taxes page to `#taxes/planning` subpage; surface only one “Tax Status” chip on the cockpit.
- **Secondary row consolidation:** Convert SoftDent, QuickBooks, AR, and Office Manager operational counts into vital-signs-style 4-pill strips, eliminating duplicate secondary tiles.
- **Validation standard:** 1920×1080 compact, zero external scroll, ≤4 KPI slots per first viewport, verified via `__nr2AssertKpiBudget`.

## 6. Approval checklist

- [ ] **Confirm consult-only** — No code applied until you approve.
- [ ] **Approve KPI budget** — ≤4 visible KPI tiles above fold per page (excluding chart canvases).
- [ ] **Approve tax planning isolation** — Move ~9 planning KPIs to `#taxes/planning` subpage; main page shows single status chip.
- [ ] **Approve empty KPI collapse** — Hide empty slots entirely; no “$0” padding, no blank chip placeholders.
- [ ] **Approve vital-signs absorption** — Primary money metrics live in 4-pill strip only; secondary row capped at 4 micro-cards or removed.