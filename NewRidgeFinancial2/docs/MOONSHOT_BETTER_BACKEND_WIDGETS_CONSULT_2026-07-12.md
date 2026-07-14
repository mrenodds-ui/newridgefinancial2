# Moonshot AI — Better Backend Widgets (CONSULT ONLY)

**Date:** 2026-07-12  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Build reviewed:** hal-10566  
**Script:** `scripts/run_moonshot_better_backend_widgets_consult.py`  
**Apply:** DO NOT APPLY until operator validates.

## Operator request (verbatim)

> ask moonshot ai if there are better widgets that can be used from the backend then report

---

# Verdict
Yes — the backend can immediately emit denser, underused frontend types (data-table, radial-gauge, status-matrix, action-list) to replace KPI sprawl on Taxes, A/R, and SoftDent pages without new JS, while modest new builders (collection-task-list, ai-insight, pareto-chart) add high-ROI workflow and analytical depth.

## 0. Operator Intent (quote; confirm consult-only)
> "ask moonshot ai if there are better widgets that can be used FROM THE BACKEND (apex_backend.py / page packs emitting mosaic JSON) then report"
> "CONSULT ONLY — DO NOT APPLY / DO NOT CODE into the live repo until operator approves."

**Confirmed CONSULT-ONLY.** No code will be generated, committed, or applied to build `hal-10566` until explicit operator approval (proceed / validated / approve) is received. All JSON shapes below are speculative specifications for review.

## 1. Gap Analysis (backend emits vs frontend can render)

| Tier | Frontend Renderers (apex-core.js) | Backend Emitters (apex_backend.py) | Gap |
|------|-----------------------------------|------------------------------------|-----|
| **Dense Data** | `data-table`, `status-matrix`, `action-list`, `ai-insight` | Not emitted — backend prefers `kpi` clusters | High-density tables and matrices exist in JS but are unused; Taxes page emits 7–13 `kpi` tiles that could collapse to one `data-table`. |
| **Visual Gauges** | `radial-gauge` | Not emitted — backend uses `bullet` or bare `kpi` | `radial-gauge` renders single-metric status (utilization, collection %) with cyan/amber/magenta arcs; backend never emits it. |
| **Workflow** | `collection-task-list`, `patient-dossier-card`, `utilization-board` | Not emitted | A/R and SoftDent pages emit scattered `status`/`pulse` chips instead of structured task lists or patient cards. |
| **Analytical** | `pareto-chart`, `forecast-trend-line`, `tax-calendar` | Not emitted | Financial/A/R pages lack 80/20 aging analysis and forward-looking calendars; backend only emits historical `waterfall`/`scrubber`. |

**Honesty constraints preserved:** All proposed types support `emptyState` props, `null` value handling, and `collapseWhenEmpty` to honor the DEF-001 "empty ≠ $0" rule without fabricating amounts.

## 2. Better Backend Widgets — Ranked

| name | type id | page(s) | data source | vs current | MUST/SHOULD/NICE | effort |
|------|---------|---------|-------------|------------|------------------|--------|
| **Tax Planning Data-Table** | `data-table` | taxes | `tax_planning_items` (modeled K-1, estimates, officer W-2) | Replaces 6–7 separate `kpi` tiles (Book Net Income, Est. Tax, etc.) with one sortable table; respects empty states. | **MUST** | Low |
| **Collections Radial-Gauge** | `radial-gauge` | financial, ar | `financial_reports` (collections / net production) | Replaces bare `kpi` "Collection %" with visual arc showing progress to 98% target; amber/magenta zones for <95%. | **MUST** | Low |
| **System Health Status-Matrix** | `status-matrix` | office-manager, claims | `import_freshness`, `cache_status`, `claims_feed` | Replaces 4–5 scattered `status` chips (SoftDent, QB, Claims, HAL) with a 2×2 grid showing active/stale/error states. | **MUST** | Low |
| **HAL Action-List** | `action-list` | hal, office-manager | `hal_recommendations` (anomaly alerts, filing reminders) | Replaces `remainder` text blocks with checkable action items; integrates with `filing-workflow`. | **SHOULD** | Low |
| **A/R Collection Task-List** | `collection-task-list` | ar | `ar_aging` + `claims_denied` (90+ buckets, denied claims) | Replaces static `bullet` charts with actionable tasks ("Call Payer X on Claim Y"); priority flags. | **SHOULD** | Medium |
| **AI Insight Card** | `ai-insight` | narratives, hal | `narrative_structure` (auto-generated variance explanations) | Replaces static `kpi` "Variance $" with natural-language insight + confidence score; no LLM embed, rule-backed only. | **SHOULD** | Low |
| **Patient Dossier Card** | `patient-dossier-card` | softdent | `softdent/patient_summary` (demographics, insurances, last visit) | Replaces scattered `kpi` "Active Patients" with a search-linked card; empty placeholder when no patient selected. | **SHOULD** | Medium |
| **Aging Pareto Chart** | `pareto-chart` | ar, financial | `ar_aging_buckets` sorted by amount | Replaces `horizontal-bar` aging with 80/20 view showing which buckets drive total A/R; cumulative % line. | **NICE** | Medium |
| **Tax Calendar** | `tax-calendar` | taxes | `tax_deadlines` (941, 1040-ES, K-1 due dates) | Replaces `countdown` single-item with month-lane view of upcoming filings; cyan=confirmed, amber=estimated. | **NICE** | Medium |
| **Claim Timeline Lanes** | `timeline-lanes` | claims, documents | `claim_history` (submitted, acknowledged, paid, denied) | Replaces `status` text with horizontal swim-lane history; gaps shown for pending payer ack. | **NICE** | High |

## 3. Quick Wins (frontend ready — backend emit only)

These types are fully implemented in `apex-core.js` and only require new Python builders (no JS work).

1. **`data-table` on Taxes page** — Emit a single `size: "l"` table with columns: Item, Status, Estimated Impact, Due Date. Rows derive from existing `tax_planning_items` bundle. Empty table shows "Import QuickBooks and SoftDent to populate."
2. **`radial-gauge` on Financial page** — Emit `size: "m"` gauge for "Collection Efficiency" (value: `reports.get("collectionRatio")`, target: 0.98). Use `ranges` to color <0.85 magenta, 0.85–0.95 amber, >0.95 cyan.
3. **`status-matrix` on Office-Manager** — Emit 2×2 grid: SoftDent Import | QuickBooks Import; Claims Feed | HAL Status. Each cell uses `status: "active" | "stale" | "error" | "unknown"` based on `bundle["import_meta"]` timestamps.
4. **`action-list` on HAL page** — Emit top 3 HAL recommendations as actionable rows with `priority: "high" | "medium"` and `href` to relevant page (e.g., `/taxes?focus=estimated_payments`).

## 4. Better Choices (replace/upgrade weak existing widgets)

| Current Weak Widget | Replacement | Backend Change | Benefit |
|---------------------|-------------|----------------|---------|
| **Taxes page:** 7× `kpi` tiles (Book Net Income, Est. Owner Tax, Modeled Officer W-2, Q1–Q4 Estimates) | Single `data-table` | `_taxes_widgets` emits one `type: "data-table"` instead of list of `kpi` | Zero-scroll compliance; ≤4 visible items above fold; sortable; honest empty rows. |
| **A/R page:** `bullet` chart for collection target + `kpi` "90+ Days" | `radial-gauge` + `collection-task-list` | `build_collection_bullet` → `build_collections_gauge`; new `build_ar_task_list` | Visual target achievement + actionable workflow list; reduces tile count from 3 to 2. |
| **SoftDent page:** `kpi` "Active Patients" + `kpi` "Avg Production" | `patient-dossier-card` | New builder aggregating `patient_summary` | Clinical context in one card; eliminates orphaned metrics when no patient selected. |
| **Office-Manager:** Row of `status` chips | `status-matrix` | Emit 2D array instead of flat list | Compact grid layout; instant visual pattern recognition (e.g., both imports stale). |
| **Narratives:** Static `remainder` text blocks | `ai-insight` cards | Emit insight objects with `confidence: "high" | "medium"` and `explanation` | Structured variance narratives; hooks into existing `narrative_structure` without new NLP. |

## 5. Per-Page Backend Placement Map

**financial**
- Row 2 (Vitals): Replace secondary `kpi` row with `radial-gauge` (Collections) + `data-table` (Top 5 A/R accounts).
- Row 3 (Analytics): Keep `dual-axis-trend`; add `pareto-chart` (A/R concentration) alongside `waterfall`.

**taxes**
- Replace entire KPI cluster (currently 7–13 tiles) with single `data-table` (Tax Planning Items) `size: "l"`.
- Add `tax-calendar` widget below table for filing deadlines (replaces `countdown`).

**softdent**
- Add `patient-dossier-card` `size: "m"` linked to active patient selector.
- Add `utilization-board` `size: "l"` (if implemented) or `radial-gauge` for chair utilization %.

**quickbooks**
- Add `data-table` `size: "m"` for "Uncleared Transactions" (check register integrity).

**ar**
- Replace `bullet` + `kpi` cluster with `radial-gauge` (target) + `collection-task-list` (actions).
- Add `pareto-chart` `size: "m"` showing which aging buckets drive 80% of balance.

**claims**
- Add `status-matrix` `size: "s"` showing payer feed health (Electronic | Paper | Portal).
- Add `timeline-lanes` `size: "l"` for selected claim history (replaces static `status`).

**narratives**
- Insert `ai-insight` cards between `workpaper` widgets to explain variances.

**documents**
- Add `timeline-lanes` for document processing workflow (Received → Indexed → Reviewed → Filed).

**library**
- Keep existing `tax-library`; no change required.

**office-manager**
- Header: `status-matrix` (4-up grid).
- Body: `action-list` for HAL-generated tasks.

**hal**
- Primary: `hal-chat` (existing).
- Sidebar: `action-list` for queued recommendations.

## 6. Spec Sketches (JSON shapes, CONSULT ONLY — no invented dollars)

**data-table (Taxes)**
```json
{
  "id": "tax-planning-table",
  "type": "data-table",
  "label": "Tax Planning Items",
  "size": "l",
  "columns": [
    {"key": "item", "label": "Item", "width": "40%"},
    {"key": "status", "label": "Status", "width": "20%"},
    {"key": "estimated_impact", "label": "Est. Impact", "format": "currency", "width": "25%"},
    {"key": "due_date", "label": "Due", "format": "date", "width": "15%"}
  ],
  "rows": [
    {"item": "Q3 Estimated Payment", "status": "Pending Calculation", "estimated_impact": null, "due_date": null},
    {"item": "K-1 Ordinary Income", "status": "Model Required", "estimated_impact": null, "due_date": null}
  ],
  "emptyState": {"message": "Import QuickBooks and SoftDent to populate tax planning items.", "action": {"label": "Import Now", "href": "/imports"}},
  "sortable": true,
  "collapseWhenEmpty": false
}
```

**radial-gauge (Collections)**
```json
{
  "id": "collections-gauge",
  "type": "radial-gauge",
  "label": "Collection Efficiency",
  "size": "m",
  "value": null,
  "target": 98.0,
  "unit": "%",
  "ranges": [
    {"min": 0, "max": 85, "color": "magenta", "label": "Critical"},
    {"min": 85, "max": 95, "color": "amber", "label": "Review"},
    {"min": 95, "max": 100, "color": "cyan", "label": "Target"}
  ],
  "hint": "Actual collections divided by net production. Import SoftDent and QuickBooks to calculate.",
  "emptyValueDisplay": "—"
}
```

**status-matrix (Office-Manager)**
```json
{
  "id": "system-health-matrix",
  "type": "status-matrix",
  "label": "System Health",
  "size": "m",
  "matrix": [
    [
      {"label": "SoftDent", "status": "unknown", "lastSync": null, "hint": "Last import: unknown"},
      {"label": "QuickBooks", "status": "unknown", "lastSync": null, "hint": "Last import: unknown"}
    ],
    [
      {"label": "Claims Feed", "status": "unknown", "count": null},
      {"label": "HAL Core", "status": "active", "hint": "Operational"}
    ]
  ],
  "emptyState": {"message": "Import data sources to activate health monitoring."}
}
```

**action-list (HAL)**
```json
{
  "id": "hal-actions",
  "type": "action-list",
  "label": "Recommended Actions",
  "size": "m",
  "items": [
    {"id": "act-1", "label": "Review Q3 estimated tax variance", "priority": "high", "href": "/taxes?variance=q3", "due": null},
    {"id": "act-2", "label": "Confirm SoftDent patient roster sync", "priority": "medium", "href": "/softdent", "due": null}
  ],
  "emptyState": {"message": "No pending actions. HAL monitoring active."}
}
```

**collection-task-list (A/R)**
```json
{
  "id": "ar-tasks",
  "type": "collection-task-list",
  "label": "Collection Tasks",
  "size": "l",
  "tasks": [
    {"id": "t-1", "patient": "Patient A", "payer": "Payer X", "amount": null, "aging_bucket": "90+", "priority": "high", "status": "call_required"},
    {"id": "t-2", "patient": "Patient B", "payer": "Payer Y", "amount": null, "aging_bucket": "120+", "priority": "critical", "status": "appeal_due"}
  ],
  "filters": ["priority", "aging_bucket"],
  "emptyState": {"message": "No collection tasks. Import A/R aging to generate tasks."}
}
```

**ai-insight (Narratives)**
```json
{
  "id": "variance-insight-1",
  "type": "ai-insight",
  "label": "Variance Explanation",
  "size": "m",
  "insight": "Production variance detected against prior period. Review coding accuracy for D— procedures.",
  "confidence": "medium",
  "sources": ["softdent/production_log", "qb/revenue_recognition"],
  "action": {"label": "View Workpaper", "href": "/workpapers/wp-001"},
  "emptyState": {"message": "No variances detected or insufficient data for analysis."}
}
```

**pareto-chart (A/R)**
```json
{
  "id": "aging-pareto",
  "type": "pareto-chart",
  "label": "A/R Concentration (Pareto)",
  "size": "m",
  "categories": [
    {"label": "120+", "value": null, "cumulative_pct": null},
    {"label": "90-120", "value": null, "cumulative_pct": null},
    {"label": "60-90", "value": null, "cumulative_pct": null},
    {"label": "30-60", "value": null, "cumulative_pct": null},
    {"label": "Current", "value": null, "cumulative_pct": null}
  ],
  "threshold_line": 80,
  "hint": "Sorted by dollar amount. Import A/R aging to populate.",
  "emptyState": {"message": "A/R aging data unavailable."}
}
```

## 7. What NOT to redo

- **KPI Density / Zero-Scroll Fixes:** Already addressed in `hal-10561`/`hal-10566`. Do not re-implement height caps or compact modes.
- **W-01 through W-10:** Already consulted 2026-07-11 (Treemap, Scatter-Plot, etc.). Awaiting operator approval; do not re-propose as new backend targets.
- **Claims Pro (Shelf, Kanban, Workbench):** Already shipped in prior builds.
- **Financial Command Strip / EBITDA Station:** Already emitted via `apex_financial_console_pack` in `_financial_widgets_from_reports`.
- **DEF-001 Register XLS Honesty:** Just shipped in `hal-10566` (content period wins over filename; empty ≠ $0).
- **Horizontal-Bar, Donut, Stacked-Bar, Bullet, Waterfall, Scrubber:** Already shipped and in active use.
- **Third-party embeds:** No TradingView, bank OAuth, or external LLM widgets proposed; all types are native Apex renderers.

## 8. Approval Checklist

**DO NOT APPLY until operator confirms:**
- [ ] Operator confirms intent to reduce Taxes page KPI count via `data-table` (MUST).
- [ ] Operator approves `radial-gauge` emission for collection metrics (MUST).
- [ ] Operator validates `status-matrix` layout for Office-Manager (MUST).
- [ ] Operator prioritizes `collection-task-list` vs. `action-list` for A/R workflow (SHOULD).
- [ ] Operator confirms no overlap with pending W-01..W10 implementation (Treemap, Scatter-Plot excluded).
- [ ] Operator verifies frontend versions support `data-table`, `radial-gauge`, `status-matrix` (confirmed in apex-core.js extract).
- [ ] Operator agrees to PLACEHOLDER-only payloads (no invented dollar amounts) in all new builders.

**Next Step:** Await operator response "approve", "proceed", or "do it" before generating Python builder functions in `apex_backend.py` or page packs.