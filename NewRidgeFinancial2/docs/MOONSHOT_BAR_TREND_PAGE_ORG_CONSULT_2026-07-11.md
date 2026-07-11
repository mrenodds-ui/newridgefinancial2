# Moonshot AI — Bar/Trend Graphs + Page Organization (CONSULT ONLY)

**Date:** 2026-07-11  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Build reviewed:** ~hal-10447  
**Script:** `scripts/run_moonshot_bar_trend_page_org_consult.py`  
**Apply:** DO NOT APPLY / DO NOT CODE until operator approves.

## Operator request (verbatim)

> aks moonshot ai is there any bar and trend graph that can be placed in the program and orgranize the pages better and ask for coding, report until approved

---

# Verdict

## 0. Operator Intent (quote; confirm consult-only)

> "aks moonshot ai is there any bar and trend graph that can be placed in the program and orgranize the pages better and ask for coding, report until approved"

**Confirmed CONSULT-ONLY.** No code will be generated, committed, or applied to build `hal-10441` until the operator explicitly states "approve," "proceed," or "do it" for a specific phase. This report evaluates placeable Apex-native instruments (bar, line, horizontal-bar, stacked-bar, dual-axis-trend, donut) and page reorganization against current import capabilities.

---

## 1. Already-Shipped Bar & Trend Graphs (inventory by page)

| Page | Widget ID | Instrument Type | Data Source | Current State |
|------|-----------|-----------------|-------------|---------------|
| **Financial** | `dual-axis-trend` | dual-axis-trend (line+bar) | SoftDent Register (production) + Daysheet (collections) | **Active** — shows production vs collections pulse when both imports present. |
| **Financial** | `provider-hbar` | horizontal-bar | SoftDent Register (provider production) | **Active** — provider production bars. |
| **Financial** | `ar-aging-chart` | bar (A/R aging buckets) | SoftDent A/R export / QB | **Active** — 0-30, 31-60, 61-90, 90+ bars. |
| **Financial** | `revenue-composition` | stacked-bar | SoftDent Collections/Daysheet (ins vs patient split) | **Empty/Blocked** — awaits Collections export; honesty gate hides misleading 0/100 splits. |
| **Financial** | `payer-donut` | donut | SoftDent Claims (payer classification) | **Empty/Blocked** — awaits Claims export with populated `Payer` field or multi-carrier mix. |
| **Financial** | `ebitda-waterfall` | bar (waterfall) | QuickBooks P&L import | **Active** when QB data present; shows valuation bridge. |
| **Financial** | `ebitda-trend` | line | QuickBooks P&L (historical net income) | **Sparse** — requires multiple QB periods. |
| **Financial** | `prod-trend` | line/sparkline | SoftDent Dashboard exports (multi-period) | **Sparse** — requires historical SoftDent periods. |
| **A/R** | `ar-aging-chart` | bar | Same as Financial | Mirrored or standalone view. |

---

## 2. Recommended NEW Bar & Trend Graphs (placeable now vs blocked on imports)

| ID | Chart | Type | Page | Data Source | Status | Effort |
|----|-------|------|------|-------------|--------|--------|
| **FIN-001** | **Collections Velocity Trend** | line | Financial | SoftDent Daysheet (collections by day) | **Blocked** — requires Collections/Daysheet export pipeline fixed (July 2026 gap). | M |
| **FIN-002** | **Payer Mix Mini-Donut** | donut | Financial | SoftDent Claims (payer field) | **Blocked** — requires Claims export with payer classification; currently monopoly bucket. | S |
| **FIN-003** | **Insurance vs Patient Stacked Bar** | stacked-bar | Financial | SoftDent Collections/Daysheet | **Blocked** — same as FIN-001; needs real split data. | S |
| **FIN-004** | **EBITDA Variance Bar** | bar (variance) | Financial/Taxes | QuickBooks P&L vs prior period | **Add** — placeable now if 2+ QB periods imported. | XS |
| **CLM-001** | **Claims Status Distribution** | bar | Claims | Existing claims kanban data (aggregate status counts) | **Add** — placeable immediately; counts 30/60/90/unmatched. | S |
| **CLM-002** | **Claims Aging Trend** | line | Claims | Claims workbench (historical snapshots) | **Add** — placeable if daily snapshots stored; else start now. | M |
| **AR-001** | **A/R Forecast Trend** | dual-axis-trend | A/R | ERA 835 payer velocity + current claims | **Blocked** — requires IMP-004 (ERA 835 Parser) from prior consult. | L |
| **AR-002** | **Collection Efficiency Bullet** | horizontal-bar | A/R | SoftDent payments / QB deposits | **Add** — placeable now; shows actual vs target collection %. | S |
| **SD-001** | **Import Health Timeline** | line | SoftDent | Bundle diagnostics (`loadedAt`, row counts) | **Add** — placeable now; trend of import freshness over 30 days. | S |
| **QB-001** | **Expense Category Horizontal Bar** | horizontal-bar | QuickBooks | QB P&L (expense accounts) | **Add** — placeable now if QB imported; top 10 expense categories. | S |
| **OM-001** | **Operatory Utilization Trend** | line/bar | Office Manager | `sd_operatory_schedule` (appointment blocks) | **Add** — placeable now; shows chair utilization % over time. | M |

**Key:** **Add** = recommended new instrument placeable with existing imports; **Blocked** = honesty architecture prevents display until specific SoftDent/QB export gaps closed.

---

## 3. Page Organization Plan (before/after map; what moves where; why)

**Problem:** Current Financial page stacks nine large/full-width instruments vertically, creating "warehouse obesity" where empty widgets (collections-mtd, payer-donut, ins-patient-split) render as 300px voids, signaling system failure rather than transient import gaps.

**Solution:** Executive Console Strip Architecture — collapsible composite strips that respect current nav pages but reorganize content density.

### Before (Current Financial Page)
```
[full] import-freshness
[full] financial-period-scrubber
[l]    payer-donut (empty)
[l]    ins-patient-split (empty)
[default] collections-mtd (empty)
[l]    provider-hbar (thin data)
[l]    liquidity-pulse
[xl]   ebitda-waterfall
[full] ebitda-scrubber
[l]    ebitda-trend
[bar]  ar-aging-chart
```

### After (Proposed Financial Executive Console)
```
STRIP 1: Command Status (60px full-width composite)
├─ Import health chip + Period selector + HAL brief
STRIP 2: Vital Signs (3-column medium mosaic)
├─ Production MTD | Collections MTD (⏳ Pending chip if empty) | A/R Outstanding
STRIP 3: Velocity & Provider (large split panel)
├─ Production Trend (sparkline) | Provider Production (horizontal-bar)
   └─ Provider panel collapses to 40px if <2 providers
STRIP 4: Revenue Composition (large conditional)
├─ Insurance vs Patient (stacked-bar when data) OR HAL action card: "Import Collections/Daysheet"
STRIP 5: A/R Analysis (full compact)
├─ A/R Aging (bar) + Collection Efficiency % (inline bullet)
STRIP 6: EBITDA Command Station (full collapsible)
├─ Waterfall (primary) + Scrubber docked below + Trend sparkline header
   └─ Shows "Import QB P&L" chip if netIncome missing
```

### Other Page Adjustments (Respecting Current Nav)

| Page | Current State | Proposed Change | Why |
|------|---------------|-----------------|-----|
| **A/R** | Sparse or mirrors Financial | Consolidate into Financial Strip 5; add Forecast Trend (AR-001) when unblocked. | Single source of truth for A/R; reduces duplication. |
| **Claims** | Kanban only (read-only) | Add Strip: Claims Status Distribution (CLM-001) above kanban; Add Aging Trend (CLM-002) sidebar. | Visual summary of kanban volume; trend visibility. |
| **Office Manager** | Generic placeholder | New "Daily Huddle" mosaic: Operatory Utilization (OM-001), Claims >90 days alert, Unpaid A/R >$5k list. | Operational command center for S-corp owner. |
| **Documents** | Disconnected | Link to Claim Attachment Bridge (IMP-006 from prior consult); show attachment count chips. | Completes claims workflow evidence. |
| **Taxes** | EBITDA scrubber strong | Add EBITDA Variance Bar (FIN-004) below scrubber; Quarterly Tax tracker (manual entry with progress bars). | Visual variance storytelling for CPA. |
| **SoftDent** | Data tables | Add Import Health Timeline (SD-001) as page header trend; freshness KPI widget. | Proactive data pipeline monitoring. |
| **QuickBooks** | Mapping tables | Add Expense Category Horizontal Bar (QB-001); Reconciliation variance mini-chart. | Immediate visual P&L insight. |

---

## 4. Coding Phases (ask-for-coding — DO NOT APPLY)

**Phase 1: Financial Executive Console Restructure**
- **Goal:** Replace vertical widget warehouse with composite strips; implement conditional collapse for empty states (chips instead of voids).
- **Effort:** M (3 days)
- **Files Touched:** `apex_financial_console_pack.py`, `site/index.html` (financial section), `apex-bridge.css`, `apex-backend.js` (strip orchestration).
- **Widgets:** `morning-brief-strip`, `vital-signs-mosaic`, `velocity-pair`, `revenue-conditional`, `ar-compact`, `ebitda-station`.
- **Validation Gate:** Visual regression check at 1920x1080 — empty collections widgets render as 24px "⏳ Pending" chips, not 300px voids; HAL suggestions populate in Strip 1.

**Phase 2: Claims Workbench Charting (Summary Instruments)**
- **Goal:** Add aggregate bar charts to Claims page using existing kanban data; no write-back to SoftDent.
- **Effort:** S (2 days)
- **Files Touched:** `claims.js`, `claims.css`, `apex-backend.js` (claims aggregation endpoint).
- **Widgets:** `claims-status-bar` (bar), `claims-aging-mini-trend` (line).
- **Validation Gate:** Bar chart counts match kanban card counts exactly; refresh respects 30-minute interval.

**Phase 3: Import Health & SoftDent Timeline**
- **Goal:** Visualize import freshness trend on SoftDent page; HAL proactive alerts for stale exports.
- **Effort:** S (2 days)
- **Files Touched:** `softdent.js`, `hal-brain.js`, `apex-backend.js` (diagnostics history).
- **Widgets:** `import-health-timeline` (line), `stale-alert-chip`.
- **Validation Gate:** Alert triggers when `loadedAt` >7 days; timeline shows last 30 days of row counts.

**Phase 4: Office Manager Daily Huddle**
- **Goal:** Morning command mosaic with operatory utilization, high-risk claims, A/R alerts.
- **Effort:** M (3 days)
- **Files Touched:** `office-manager.js/css`, `apex-backend.js` (huddle aggregation).
- **Widgets:** `huddle-mosaic` (composite), `operatory-util-trend` (line/bar), `priority-list`.
- **Validation Gate:** Data matches `sd_operatory_schedule` and claims workbench; loads <500ms.

**Phase 5: A/R Forecast & Payer Velocity (Blocked Pre-req)**
- **Goal:** Dual-axis trend forecasting A/R outlook based on payer historical velocity.
- **Effort:** L (5 days) — **Blocked until IMP-004 (ERA 835 Parser) completed**
- **Files Touched:** `ar.js`, `era-parser.py`, `apex-backend.js`.
- **Widgets:** `ar-forecast-trend` (dual-axis-trend).
- **Validation Gate:** Forecast accuracy within 10% of actual collections after 30 days of 835 data.

**Phase 6: QuickBooks Expense Visualization**
- **Goal:** Horizontal bar chart of top expense categories from QB P&L.
- **Effort:** S (1 day)
- **Files Touched:** `quickbooks.js`, `apex-backend.js`.
- **Widgets:** `qb-expense-hbar`.
- **Validation Gate:** Bar totals reconcile to QB P&L expense total.

---

## 5. Risks & Honesty Rules

1. **No Invented Dollars:** All trend lines must be backed by import series (`SoftDent Register`, `Daysheet`, `QB P&L`). If historical data is sparse (e.g., only one period), the chart renders an honest "Insufficient data" chip rather than a flat line at zero.
2. **Empty State Integrity:** Blocked widgets (FIN-001, FIN-002, FIN-003) must not render fake placeholder bars or trend lines. They display HAL action cards: "Import [Specific Export] to reveal this view."
3. **PHI Locality:** No third-party JS embeds (TradingView, Investing.com, etc.) as evaluated in prior consult; all instruments Apex-native canvas/SVG.
4. **Refresh Respect:** Coding must honor the 30-minute auto-refresh interval (changed from 30s) to prevent page flicker.
5. **CSP Compliance:** All new instruments must comply with existing Content Security Policy (no external data URIs).
6. **Data Dependency Risk:** Phase 5 (A/R Forecast) cannot proceed until ERA 835 parsing is operational; attempting to code before imports ready will result in false forecasting algorithms.

---

## 6. Approval Checklist (what operator must approve before coding)

**DO NOT APPLY** until operator explicitly confirms:

- [ ] **Scope Approval:** Which phase(s) to proceed with (recommend starting Phase 1 only).
- [ ] **Data Source Confirmation:** Confirm path to SoftDent Collections/Daysheet export for Phase 1 revenue composition strip (currently blocked).
- [ ] **Empty State Behavior:** Confirm preference for "⏳ Pending" chips vs. HAL action cards when imports missing.
- [ ] **Navigation Freeze:** Confirm no new nav pages added (current 11 pages preserved).
- [ ] **Refresh Interval:** Acknowledge 30-minute refresh will remain in place during development.
- [ ] **HAL Integration:** Confirm HAL suggestions should populate Strip 1 (requires HAL backend hooks).
- [ ] **Phase 5 Hold:** Explicitly acknowledge Phase 5 is blocked pending ERA 835 parser completion (IMP-004).

**Awaiting operator "proceed," "approve," or "do it" with specified phase number.**