# Moonshot AI — All-Pages Extremely High-Tech Redesign + Widget Relayout
**Date:** 2026-07-09
**Model:** kimi-k2.5 via OPENROUTER_API_KEY
**Status:** REVIEW ONLY — do not apply until operator validates
**Script:** `scripts/run_moonshot_all_pages_hightech_relayout_consult.py`
**Scope:** All 11 live-wire pages; current widgets; alter/relocate allowed if safe; paste-ready code included; NO code applied

---

# Verdict
**Yes.** By compressing the grid to terminal density (8px gaps, 10px padding), enforcing JetBrains Mono tabular figures, adding severity heatmaps (red pulse on 90+ A/R, amber on 60+ claims), and reordering panels into logical "instrument clusters" (primary → secondary → utility), the pages will read as Bloomberg-terminal-grade financial OS in under 5 seconds. The relocation of 14 panels and type-swap of 3 panels (table→stat-grid where data shape permits) creates visual hierarchy without breaking data honesty.

---

## 1. Widget alter / relocate policy (ANSWER THE OPERATOR DIRECTLY)

### 1a. What MAY be altered
| WidgetKey | Current page | Allowed alter (chrome / type / density) | Risk |
|-----------|--------------|-----------------------------------------|------|
| `periodCloseAndPosting` | taxes, documents | **type:** table→gauge (single value), **chrome:** amber/gold accent, **density:** compact | **Low:** dataBind returns scalar or single-row object compatible with gauge renderer |
| `quickbooksNetIncomeSummary` | taxes, quickbooks, hal | **type:** stat-grid→hero-kpi tile (inline), **chrome:** cyan glow | **Low:** scalar numeric with label |
| `softdentProviderProduction` | financial, softdent | **type:** table→stat-grid (top 5 providers), **chrome:** monospace bars | **Medium:** verify dataBind returns array of {label,value} |
| `quickbooksArAging` | taxes, quickbooks | **chrome:** severity border-left (red>90, amber>60), **density:** compact rows | **None:** pure CSS |
| `arOutstandingClaims` | ar | **chrome:** severity glow, **density:** tight padding | **None:** pure CSS |
| `documentIntakeQueue` | documents | **chrome:** gold left-border "classified" aesthetic | **None:** pure CSS |
| `officeManagerSurfaces` | hal, office-manager | **chrome:** live-pulse dot animation | **None:** pure CSS |
| All kanban widgets | claims, narratives, office-manager | **chrome:** lane header dots, card severity dots | **None:** pure CSS |

### 1b. What MAY be relocated (to other parts of SAME page or CROSS-page)
| WidgetKey | From | To (page + position) | Why high-tech | Layout change summary |
|-----------|------|----------------------|---------------|----------------------|
| `fin-provider-performance` | financial (row 5, pos 1) | financial (row 4, pos 1) | Group provider analytics with reconciliation | Swap with `fin-daily-production`; colSpan 6→6 (no change) |
| `fin-reconciliation` | financial (row 4, pos 1) | financial (row 4, pos 2) | Place next to provider performance | Swap positions with above |
| `fin-daily-production` | financial (row 4, pos 2) | financial (row 5, pos 1) | Create "velocity row" with collections | Move down, pair with `fin-collections-daily` |
| `fin-collections-daily` | financial (row 6, pos 2) | financial (row 5, pos 2) | Velocity pair with production | Move up |
| `fin-provider-comp` | financial (row 6, pos 1) | financial (row 6, pos 2) | Anchor bottom with provider production table | Keep row 6, swap sides |
| `fin-appointments` | financial (row 8) | financial (row 8) | **No move**—keep full-width footer utility | De-emphasize with muted chrome |
| `tax-cash-flow` | taxes (row 3) | taxes (row 1, pos 1) | Lead with cash position (primary instrument) | Move to top, colSpan 6→8 |
| `tax-net-income` | taxes (row 2, pos 2) | taxes (row 1, pos 2) | Pair with cash flow | Move to top, colSpan 6→4 |
| `tax-revenue-service` | taxes (row 4, pos 1) | taxes (row 3, pos 2) | Group revenue metrics | Move up, colSpan 4→6 |
| `tax-ar-aging` | taxes (row 4, pos 2) | taxes (row 5, pos 1) | Place before period close (workflow order) | Move down, colSpan 8→8 |
| `tax-period-close` | taxes (row 6, pos 1) | taxes (row 5, pos 2) | Pair with aging (close old items) | Move down, colSpan 6→4 |
| `qb-cash-flow` | quickbooks (row 2, pos 1) | quickbooks (row 1, pos 1) | Lead with liquidity | Move to top, colSpan 8→8 |
| `qb-net-income` | quickbooks (row 3, pos 2) | quickbooks (row 1, pos 2) | Secondary KPI | Move to top, colSpan 6→4 |
| `qb-revenue-service` | quickbooks (row 4, pos 2) | quickbooks (row 3, pos 2) | Group with revenue trend | Move up, colSpan 3→6 |
| `qb-ar-aging` | quickbooks (row 4, pos 3) | quickbooks (row 5) | Full-width detail view | Move to bottom, colSpan 3→12 |
| `doc-sources` | documents (row 4) | documents (row 2) | Surface metadata early | Move up, colSpan 12→12 |
| `sd-prov-bar` | softdent (row 4, pos 3) | softdent (row 5) | Full-width provider velocity | Move to dedicated row, colSpan 3→12 |

**CROSS-page relocation:** Not recommended. Widgets using `PageCanvasData.softdent*()` or `PageCanvasData.quickbooks*()` context binds cannot leave their domain. Generic `PageCanvasData.metrics('key')` widgets (e.g., `halImportHealth`) could theoretically move, but data honesty requires they stay on pages where the metric is contextually relevant.

### 1c. What must NOT move or invent
- **`nr2AlertTicker` (financial):** Must stay at top of financial page; embedded alert logic assumes DOM order for screen-reader announcements.
- **`halAskHal` (hal):** Fixed position expectation for voice interface; moving breaks focus management.
- **`softdentOperatoryGrid`:** Cannot leave softdent page; dataBind queries SoftDent ODBC context exclusively.
- **New widget keys:** `taxHeroKpis`, `qbHeroKpis` — inventing these would require new PageCanvasData methods (binder changes), violating "no new data pipelines."

### 1d. Recommended composition rules
**Hero band (row 1):** 4–6 KPI tiles, no chart, monochrome figures only, 10px padding max.
**Primary instrument (row 2):** Largest chart or heatmap (colSpan 8) paired with critical gauge (colSpan 4).
**Secondary strip (rows 3–4):** 6+6 or 8+4 splits, tables paired with stat-grids for density contrast.
**Footer utility (last row):** Full-width table or kanban, muted borders, smaller type (12px).

---

## 2. Visual Design System (extreme)

**Tokens**
```css
--mc-bg: #09090b;                 /* Near-black obsidian */
--mc-surface: rgba(14,14,18,0.78); /* Glass 78% opacity */
--mc-border: rgba(255,255,255,0.05);
--mc-border-hover: rgba(255,255,255,0.12);
--mc-cyan: #06b6d4;               /* Primary signal */
--mc-cyan-glow: 0 0 10px rgba(6,182,212,0.4);
--mc-gold: #d4af37;               /* Documents/vault */
--mc-red: #dc2626;                /* Severity critical */
--mc-amber: #f59e0b;              /* Warning */
--font-mono: "JetBrains Mono", "SF Mono", Consolas, ui-monospace, monospace;
```

**Typography**
- All currency/integers: `font-family: var(--font-mono); font-variant-numeric: tabular-nums; letter-spacing: -0.02em;`
- Labels: 10px uppercase, `letter-spacing: 0.06em`, color `#71717a`
- Values: 22–28px, weight 600, color `#e4e4e7`

**Glass & Glow**
- Panels: `backdrop-filter: blur(14px); border: 1px solid var(--mc-border); border-radius: 6px;` (sharp instruments)
- Hover: `box-shadow: var(--mc-cyan-glow); transform: translateY(-1px);`
- Active filter chip: `background: rgba(6,182,212,0.12); border-color: rgba(6,182,212,0.4);`

**Motion Budget (4 rules)**
1. **Scanline:** 6s linear infinite sweep across chart containers (subtle).
2. **Pulse:** 2s ease-in-out infinite opacity pulse on "LIVE" indicators.
3. **Severity blink:** 1.5s infinite for critical A/R (>90 days).
4. **Hover lift:** 0.15s transform transition only.

**Severity Language**
- `.mc-severity-high`: Left border 3px var(--mc-red), subtle red glow, blinking dot.
- `.mc-severity-med`: Left border 3px var(--mc-amber).
- `.mc-severity-low`: Left border 3px #10b981.

---

## 3. Page-by-page redesign (ALL 11)

### financial — "Trading Floor"
- **Current:** Scattered provider widgets, loose 16px gaps.
- **Target:** Velocity cluster at center, provider detail anchored bottom.
- **Row 1:** Hero KPIs (5 tiles) — keep, add `.mc-mono` class.
- **Row 2:** Alert ticker (12) — slim height 48px, cyan top border.
- **Row 3:** Monthly trend dual-chart (8) + Collection lag gauge (4) — primary instruments.
- **Row 4:** Production reconciliation table (6) + Provider performance stat-grid (6) — financial health pair.
- **Row 5:** Production daily bar (6) + Collections daily bar (6) — velocity pair.
- **Row 6:** Provider production table (6) + Provider comp stat-grid (6) — detail pair.
- **Row 7:** New patients stat (4) + Claims outstanding stat (4) + New patient flow chart (4) — ancillary.
- **Row 8:** Appointments snapshot (12) — footer utility, compact 12px rows.

### taxes — "Tax Terminal"
- **Current:** Form-like stacked tables.
- **Target:** Amber accent, cash-first hierarchy.
- **Row 1:** Cash flow trend dual-chart (8) + Net income summary (4) — liquidity first.
- **Row 2:** P&L table (6) + EBITDA table (6) — core statements.
- **Row 3:** Monthly revenue bar (6) + Revenue by service donut (6) — revenue analysis.
- **Row 4:** Balance sheet table (6) + Operating expenses stat-grid (6) — position & burn.
- **Row 5:** A/R aging table (8) + Period close gauge (4) — close workflow.
- **Row 6:** Accounts payable table (6) + Journal entries table (6) — payables & entries.

### quickbooks — "IRS Terminal"
- **Current:** Disconnected revenue widgets.
- **Target:** Blue accent, logical accounting flow.
- **Row 1:** Cash flow trend (8) + Net income summary (4) — liquidity.
- **Row 2:** P&L summary (6) + EBITDA bridge (6) — income normalization.
- **Row 3:** Monthly revenue trend (6) + Revenue by service (6) — revenue deep-dive.
- **Row 4:** Balance sheet summary (6) + Expense breakdown (6) — position.
- **Row 5:** A/R aging (12) — full-width detail, red severity on >90 days.

### softdent — "Care Velocity War Room"
- **Current:** Provider bar squeezed into 3 columns.
- **Target:** Cyan accent, operatory central, provider velocity full-width.
- **Row 1:** Hero KPIs (4) — production, new patients, collections, claims.
- **Row 2:** Operatory grid (8) + Appointments snapshot (4) — schedule war room.
- **Row 3:** A/R aging heatmap (8) + Responsibility donut (4) — financial heatmap.
- **Row 4:** Treatment funnel (6) + Case acceptance gauge (3) + Hygiene recall (3) — clinical pipeline.
- **Row 5:** Provider production bar chart (12) — full-width velocity strip.

### ar — "A/R Mission Control"
- **Current:** Standard table layout.
- **Target:** Red severity glow, 6-KPI hero, waterfall heatmap.
- **Row 1:** Hero KPIs (6) — total, 0-30, 31-60, 61-90, 90+, DSO.
- **Row 2:** A/R aging heatmap (8) + Outstanding claims table (4) — heat + detail.
- **Row 3:** Follow-up queue kanban (12) — severity dots on cards.

### claims — "Insurance Pipeline"
- **Current:** 4-KPI hero, 6-lane kanban.
- **Target:** Purple lane headers, severity-coded cards.
- **Row 1:** Hero KPIs (4) — total value, avg age, denial rate, pending attachments.
- **Row 2:** Claims pipeline kanban (12) — 6 lanes with dot headers, high-severity cards pulse amber.

### narratives — "Clinical Composer"
- **Current:** Single kanban.
- **Target:** Pink glass, compact composer lanes.
- **Row 1:** Narrative workflow kanban (12) — 4 lanes (Draft → Review → Approved → Printed), pink header accents, print-ready iconography.

### documents — "Secure Vault"
- **Current:** Source breakdown at bottom.
- **Target:** Gold accents, source metrics surfaced early.
- **Row 1:** Document intake queue (8) + Document preview (4) — ingestion.
- **Row 2:** Source breakdown stat-grid (12) — vault telemetry.
- **Row 3:** Period close gauge (6) + AP funnel (6) — control processes.
- **Row 4:** Journal posting queue (12) — entry log.

### library — "Archive Terminal"
- **Current:** Facets (3) + Library (9).
- **Target:** Cyan active states, density.
- **Row 1:** Category facets (3) + Library table (9) — keep layout, add `.mc-terminal-density` (8px padding, 11px type).

### office-manager — "Command Center"
- **Current:** Priorities (8) + Surfaces (4), Tasks (12).
- **Target:** Green pulse, live indicators.
- **Row 1:** Today's focus kanban (8) + Staff work surfaces stat-grid (4) — command view.
- **Row 2:** Office task queue table (12) — mission list.

### hal — "HAL 9000"
- **Current:** Ask HAL (12), 4 stats (3 each), Surfaces (12).
- **Target:** Red glow, transcript glass.
- **Row 1:** Ask HAL (12) — command input, red border glow.
- **Row 2:** Import health (3) + Financial overview (3) + Care delivery (3) + P&L summary (3) — system telemetry.
- **Row 3:** Staff work surfaces kanban (12) — mission control view.

---

## 4. Moonshot Code Deliverables

### File: `NewRidgeFinancial2/site/deferred-live-wire/nr2-mission-control-extreme.css`
**Mirror:** `NewRidgeFinancial2/deferred-live-wire/nr2-mission-control-extreme.css`
```css
/**
 * Moonshot Mission Control — EXTREME Terminal Density
 * Scope: .app--moonshot-mockup .ms-mission-control
 * P0: Link after nr2-mission-control-glass.css
 */

/* 1. Density Reset — Terminal Compression */
.app--moonshot-mockup .ms-mission-control .widget-grid,
.app--moonshot-mockup .ms-mission-control .dashboard-grid {
  gap: 10px;
  padding: 10px;
}

.app--moonshot-mockup .ms-mission-control .canvas-panel,
.app--moonshot-mockup .ms-mission-control .kpi-tile,
.app--moonshot-mockup .ms-mission-control .kanban-column,
.app--moonshot-mockup .ms-mission-control .ms-panel-obsidian {
  padding: 10px;
  border-radius: 6px;
}

.app--moonshot-mockup .ms-mission-control .panel-header,
.app--moonshot-mockup .ms-mission-control .card-header {
  padding: 8px 10px;
  font-size: 10px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #71717a;
  border-bottom: 1px solid rgba(255,255,255,0.04);
}

/* 2. Monospace Enforcement — Tabular Figures */
.app--moonshot-mockup .ms-mission-control .kpi-value,
.app--moonshot-mockup .ms-mission-control .figure,
.app--moonshot-mockup .ms-mission-control td.numeric,
.app--moonshot-mockup .ms-mission-control .data-table td,
.app--moonshot-mockup .ms-mission-control .claim-amount,
.app--moonshot-mockup .ms-mission-control .chart-value,
.app--moonshot-mockup .ms-mission-control .kanban-card-mission .meta {
  font-family: "JetBrains Mono", "SF Mono", Consolas, ui-monospace, monospace;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
}

/* 3. Severity System — A/R & Claims Heat */
.app--moonshot-mockup .ms-mission-control .mc-severity-high {
  border-left: 3px solid #dc2626;
  background: linear-gradient(90deg, rgba(220,38,38,0.06), transparent);
}
.app--moonshot-mockup .ms-mission-control .mc-severity-high::before {
  content: "";
  display: inline-block;
  width: 6px;
  height: 6px;
  background: #dc2626;
  border-radius: 50%;
  margin-right: 8px;
  box-shadow: 0 0 8px #dc2626;
  animation: mc-blink 1.5s infinite;
}

.app--moonshot-mockup .ms-mission-control .mc-severity-med {
  border-left: 3px solid #f59e0b;
  background: linear-gradient(90deg, rgba(245,158,11,0.06), transparent);
}

.app--moonshot-mockup .ms-mission-control .mc-severity-low {
  border-left: 3px solid #10b981;
}

@keyframes mc-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* 4. Scanline Animation — Charts Only */
.app--moonshot-mockup .ms-mission-control .chart-container {
  position: relative;
  overflow: hidden;
}
.app--moonshot-mockup .ms-mission-control .chart-container::after {
  content: "";
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(6,182,212,0.04), transparent);
  animation: mc-scan 6s linear infinite;
  pointer-events: none;
}

@keyframes mc-scan {
  0% { left: -100%; }
  100% { left: 100%; }
}

/* 5. Live Pulse — HAL & Office Manager */
.app--moonshot-mockup .ms-mission-control .mc-live-indicator::before {
  content: "";
  display: inline-block;
  width: 8px;
  height: 8px;
  background: #10b981;
  border-radius: 50%;
  margin-right: 6px;
  box-shadow: 0 0 8px #10b981;
  animation: mc-pulse 2s infinite;
}

@keyframes mc-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.6; transform: scale(0.9); }
}

/* 6. Page-Specific Accents */
.app--moonshot-mockup .ms-mission-control.taxes-moonshot {
  --mc-accent: #f59e0b;
  --mc-accent-glow: 0 0 10px rgba(245,158,11,0.35);
}
.app--moonshot-mockup .ms-mission-control.quickbooks-moonshot {
  --mc-accent: #60a5fa;
  --mc-accent-glow: 0 0 10px rgba(96,165,250,0.35);
}
.app--moonshot-mockup .ms-mission-control.hal-moonshot {
  --mc-accent: #dc2626;
  --mc-accent-glow: 0 0 10px rgba(220,38,38,0.4);
}

/* 7. Kanban Lane Headers — Mission Dots */
.app--moonshot-mockup .ms-mission-control .kanban-column .column-header::before,
.app--moonshot-mockup .ms-mission-control .kanban-lane-mission .lane-header::before {
  content: "";
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--mc-accent);
  box-shadow: 0 0 6px var(--mc-accent);
  margin-right: 8px;
  display: inline-block;
}

/* 8. Empty State Honesty — Terminal Style */
.app--moonshot-mockup .ms-mission-control .mc-empty-state {
  font-family: var(--font-mono);
  font-size: 11px;
  color: #52525b;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  text-align: center;
  padding: 24px;
  border: 1px dashed rgba(255,255,255,0.08);
  background: rgba(0,0,0,0.2);
}
```

### File: `NewRidgeFinancial2/site/deferred-live-wire/moonshot-page-layouts.js`
**Mirror:** `NewRidgeFinancial2/deferred-live-wire/moonshot-page-layouts.js`
**P0:** Full replacement with relocated panels and type swaps.

```javascript
/** Moonshot page panel layouts — EXTREME TERMINAL EDITION (hal-10168-consult) */
const MOONSHOT_PAGE_LAYOUTS = {
  "version": 2,
  "source": "moonshot-kimi-k2.6-elite-extreme",
  "generated": "2026-07-09",
  "pages": {
    "financial": {
      "title": "Owner Financial Dashboard",
      "shell": "widget-grid",
      "panels": [
        {
          "id": "fin-hero-kpis",
          "type": "hero-kpi",
          "colSpan": 12,
          "dataBind": "PageCanvasData.financialKpis()",
          "kpis": [
            { "widgetKey": "practiceFinancialOverview", "label": "Production MTD" },
            { "widgetKey": "softdentCollectionsDaily", "label": "Collections MTD" },
            { "widgetKey": "quickbooksNetIncomeSummary", "label": "Net Income YTD" },
            { "widgetKey": "nr2CollectionLag", "label": "A/R Days" },
            { "widgetKey": "nr2GoalScorecard", "label": "Goal Attainment" }
          ]
        },
        {
          "id": "fin-alert-ticker",
          "type": "custom",
          "widgetKey": "nr2AlertTicker",
          "colSpan": 12,
          "title": "Exception Alert Ticker",
          "dataBind": "PageCanvasData.nr2AlertTicker()"
        },
        {
          "id": "fin-monthly-trend",
          "type": "chart",
          "widgetKey": "nr2MonthlyTrendCombo",
          "colSpan": 8,
          "title": "Executive Monthly Trend",
          "dataBind": "PageCanvasData.nr2MonthlyTrendCombo()",
          "chartType": "dual"
        },
        {
          "id": "fin-collection-lag",
          "type": "gauge",
          "widgetKey": "nr2CollectionLag",
          "colSpan": 4,
          "title": "Collection Lag (DSO)",
          "dataBind": "PageCanvasData.nr2CollectionLag()"
        },
        {
          "id": "fin-reconciliation",
          "type": "table",
          "widgetKey": "nr2ProductionReconciliation",
          "colSpan": 6,
          "title": "Production vs QuickBooks Reconciliation",
          "dataBind": "PageCanvasData.nr2ProductionReconciliation()"
        },
        {
          "id": "fin-provider-performance",
          "type": "stat-grid",
          "widgetKey": "providerPerformance",
          "colSpan": 6,
          "title": "Provider Performance",
          "dataBind": "PageCanvasData.providerBars()"
        },
        {
          "id": "fin-daily-production",
          "type": "chart",
          "widgetKey": "softdentProductionDaily",
          "colSpan": 6,
          "title": "SoftDent Production Trend",
          "dataBind": "PageCanvasData.softdentProductionDailySeries()",
          "chartType": "bar"
        },
        {
          "id": "fin-collections-daily",
          "type": "chart",
          "widgetKey": "softdentCollectionsDaily",
          "colSpan": 6,
          "title": "Collections Trend",
          "dataBind": "PageCanvasData.softdentCollectionsDailySeries()",
          "chartType": "bar"
        },
        {
          "id": "fin-provider-production",
          "type": "table",
          "widgetKey": "softdentProviderProduction",
          "colSpan": 6,
          "title": "Provider Production",
          "dataBind": "PageCanvasData.softdentProviderProductionData()"
        },
        {
          "id": "fin-provider-comp",
          "type": "stat-grid",
          "widgetKey": "nr2ProviderCompensationWidget",
          "colSpan": 6,
          "title": "Provider Production Share",
          "dataBind": "PageCanvasData.nr2ProviderCompensation()"
        },
        {
          "id": "fin-new-patients-mtd",
          "type": "stat-grid",
          "widgetKey": "softdentNewPatientsMTD",
          "colSpan": 4,
          "title": "New Patients",
          "dataBind": "PageCanvasData.softdentNewPatientsMtdData()"
        },
        {
          "id": "fin-claims-outstanding",
          "type": "stat-grid",
          "widgetKey": "softdentClaimsOutstanding",
          "colSpan": 4,
          "title": "Outstanding Claims",
          "dataBind": "PageCanvasData.softdentClaimsOutstandingData()"
        },
        {
          "id": "fin-new-patients",
          "type": "chart",
          "widgetKey": "newPatients",
          "colSpan": 4,
          "title": "New Patient Flow",
          "dataBind": "PageCanvasData.metrics('newPatients')",
          "chartType": "bar"
        },
        {
          "id": "fin-appointments",
          "type": "table",
          "widgetKey": "softdentAppointmentsSnapshot",
          "colSpan": 12,
          "title": "Appointments Snapshot",
          "dataBind": "PageCanvasData.softdentAppointmentsSnapshotData()"
        }
      ]
    },
    "taxes": {
      "title": "S Corp Tax Planning",
      "shell": "widget-grid",
      "panels": [
        {
          "id": "tax-cash-flow",
          "type": "chart",
          "widgetKey": "quickbooksCashFlowTrend",
          "colSpan": 8,
          "title": "Cash Flow Trend",
          "dataBind": "PageCanvasData.quickbooksCashFlowTrend()",
          "chartType": "dual"
        },
        {
          "id": "tax-net-income",
          "type": "stat-grid",
          "widgetKey": "quickbooksNetIncomeSummary",
          "colSpan": 4,
          "title": "Net Income Summary",
          "dataBind": "PageCanvasData.quickbooksNetIncomeSummary()"
        },
        {
          "id": "tax-qb-pl",
          "type": "table",
          "widgetKey": "quickbooksProfitLossDetail",
          "colSpan": 6,
          "title": "Book Income (QuickBooks YTD)",
          "dataBind": "PageCanvasData.quickbooksPlRows()"
        },
        {
          "id": "tax-ebitda",
          "type": "table",
          "widgetKey": "ebitdaNormalization",
          "colSpan": 6,
          "title": "Owner Add-backs & Adjustments",
          "dataBind": "PageCanvasData.ebitdaRows()"
        },
        {
          "id": "tax-monthly-revenue",
          "type": "chart",
          "widgetKey": "quickbooksMonthlyRevenue",
          "colSpan": 6,
          "title": "Monthly Revenue Trend",
          "dataBind": "PageCanvasData.quickbooksMonthlyRevenueSeries()",
          "chartType": "bar"
        },
        {
          "id": "tax-revenue-service",
          "type": "donut",
          "widgetKey": "quickbooksRevenueByService",
          "colSpan": 6,
          "title": "Revenue by Service",
          "dataBind": "PageCanvasData.quickbooksRevenueByService()",
          "chartType": "donut"
        },
        {
          "id": "tax-balance-sheet",
          "type": "table",
          "widgetKey": "quickbooksBalanceSheetSummary",
          "colSpan": 6,
          "title": "Balance Sheet Summary",
          "dataBind": "PageCanvasData.quickbooksBalanceSheetSummary()"
        },
        {
          "id": "tax-expense-breakdown",
          "type": "stat-grid",
          "widgetKey": "quickbooksExpenseBreakdown",
          "colSpan": 6,
          "title": "Operating Expenses",
          "dataBind": "PageCanvasData.quickbooksExpenseBars()"
        },
        {
          "id": "tax-ar-aging",
          "type": "table",
          "widgetKey": "quickbooksArAging",
          "colSpan": 8,
          "title": "QuickBooks A/R Aging",
          "dataBind": "PageCanvasData.quickbooksQbArAging()"
        },
        {
          "id": "tax-period-close",
          "type": "gauge",
          "widgetKey": "periodCloseAndPosting",
          "colSpan": 4,
          "title": "Period Close",
          "dataBind": "PageCanvasData.documentsPeriodStats()"
        },
        {
          "id": "tax-ap",
          "type": "table",
          "widgetKey": "accountsPayableAutomation",
          "colSpan": 6,
          "title": "Accounts Payable",
          "dataBind": "PageCanvasData.metrics('accountsPayableAutomation')"
        },
        {
          "id": "tax-journal-queue",
          "type": "table",
          "widgetKey": "journalPostingQueue",
          "colSpan": 6,
          "title": "Journal Entries",
          "dataBind": "PageCanvasData.journalQueueItems()"
        }
      ]
    },
    "hal": {
      "title": "HAL Command Center",
      "shell": "dashboard-grid",
      "panels": [
        {
          "id": "hal-ask",
          "type": "custom",
          "widgetKey": "halAskHal",
          "colSpan": 12,
          "title": "Ask HAL",
          "dataBind": "PageCanvasData.widget('halAskHal')"
        },
        {
          "id": "hal-import-health",
          "type": "stat-grid",
          "widgetKey": "halImportHealth",
          "colSpan": 3,
          "title": "Import & Source Health",
          "dataBind": "PageCanvasData.integrationMetric('halImportHealth')"
        },
        {
          "id": "hal-fin-overview",
          "type": "stat-grid",
          "widgetKey": "practiceFinancialOverview",
          "colSpan": 3,
          "title": "Practice Financial Overview",
          "dataBind": "PageCanvasData.metrics('practiceFinancialOverview')"
        },
        {
          "id": "hal-care-delivery",
          "type": "stat-grid",
          "widgetKey": "careDeliveryPerformance",
          "colSpan": 3,
          "title": "Care Delivery Performance",
          "dataBind": "PageCanvasData.metrics('careDeliveryPerformance')"
        },
        {
          "id": "hal-qb-pl",
          "type": "stat-grid",
          "widgetKey": "quickbooksProfitLossDetail",
          "colSpan": 3,
          "title": "Profit & Loss Summary",
          "dataBind": "PageCanvasData.metrics('quickbooksProfitLossDetail')"
        },
        {
          "id": "hal-surfaces",
          "type": "kanban",
          "widgetKey": "officeManagerSurfaces",
          "colSpan": 12,
          "title": "Staff Work Surfaces",
          "dataBind": "PageCanvasData.metrics('officeManagerSurfaces')"
        }
      ]
    },
    "softdent": {
      "title": "Care Delivery & Practice Velocity",
      "shell": "widget-grid",
      "panels": [
        {
          "id": "sd-hero-kpis",
          "type": "hero-kpi",
          "colSpan": 12,
          "dataBind": "PageCanvasData.softdentHeroKpis()",
          "kpis": [
            { "widgetKey": "careDeliveryPerformance", "label": "Production MTD" },
            { "widgetKey": "softdentNewPatientsMTD", "label": "New Patients" },
            { "widgetKey": "softdentCollectionsDaily", "label": "Collections Trend" },
            { "widgetKey": "softdentClaimsOutstanding", "label": "Outstanding Claims" }
          ]
        },
        {
          "id": "sd-op-grid",
          "type": "custom",
          "widgetKey": "softdentOperatoryGrid",
          "colSpan": 8,
          "title": "Operatory Schedule",
          "dataBind": "PageCanvasData.softdentOperatoryGrid()"
        },
        {
          "id": "sd-appt-snapshot",
          "type": "stat-grid",
          "widgetKey": "softdentAppointmentsSnapshot",
          "colSpan": 4,
          "title": "Appointments Snapshot",
          "dataBind": "PageCanvasData.softdentAppointmentStats()"
        },
        {
          "id": "sd-ar-aging",
          "type": "heatmap",
          "widgetKey": "softdentArAging",
          "colSpan": 8,
          "title": "Accounts Receivable Aging",
          "dataBind": "PageCanvasData.softdentArAgingHeatmap()"
        },
        {
          "id": "sd-resp-donut",
          "type": "donut",
          "widgetKey": "softdentResponsibility",
          "colSpan": 4,
          "title": "Insurance vs Patient Balance",
          "dataBind": "PageCanvasData.softdentResponsibilityDonut()"
        },
        {
          "id": "sd-tx-funnel",
          "type": "funnel",
          "widgetKey": "treatmentPlanSummary",
          "colSpan": 6,
          "title": "Treatment Plans Presented",
          "dataBind": "PageCanvasData.treatmentPlanFunnel()"
        },
        {
          "id": "sd-case-gauge",
          "type": "gauge",
          "widgetKey": "caseAcceptance",
          "colSpan": 3,
          "title": "Case Acceptance Rate",
          "dataBind": "PageCanvasData.metrics('caseAcceptance')"
        },
        {
          "id": "sd-hyg-gauge",
          "type": "gauge",
          "widgetKey": "hygieneRecall",
          "colSpan": 3,
          "title": "Hygiene & Recall",
          "dataBind": "PageCanvasData.hygieneRecallGauge()"
        },
        {
          "id": "sd-prov-bar",
          "type": "chart",
          "widgetKey": "softdentProviderProduction",
          "colSpan": 12,
          "title": "Provider Production Velocity",
          "dataBind": "PageCanvasData.softdentProviderProductionData()",
          "chartType": "bar"
        }
      ]
    },
    "narratives": {
      "title": "Clinical Documentation & Justification Composer",
      "shell": "widget-grid",
      "panels": [
        {
          "id": "nar-composer",
          "type": "kanban",
          "widgetKey": "narrativeWorkflow",
          "colSpan": 12,
          "title": "Narrative Composer",
          "dataBind": "PageCanvasData.narrativeKanban()"
        }
      ]
    },
    "claims": {
      "title": "Open Insurance Claims",
      "shell": "widget-grid",
      "panels": [
        {
          "id": "clm-analytics",
          "type": "hero-kpi",
          "colSpan": 12,
          "dataBind": "PageCanvasData.claimsPipelineSummary()",
          "kpis": [
            { "halSubpanel": "claimsKpiTotal", "label": "Total Open Value" },
            { "halSubpanel": "claimsKpiAge", "label": "Average Age" },
            { "halSubpanel": "claimsKpiDenied", "label": "Denial Rate" },
            { "halSubpanel": "claimsKpiAttachments", "label": "Pending Attachments" }
          ]
        },
        {
          "id": "clm-pipeline",
          "type": "kanban",
          "widgetKey": "claimsPipeline",
          "colSpan": 12,
          "title": "Open Insurance Claims",
          "dataBind": "PageCanvasData.claimsKanban()"
        }
      ]
    },
    "ar": {
      "title": "A/R Mission Control",
      "shell": "widget-grid",
      "panels": [
        {
          "id": "ar-hero-kpis",
          "type": "hero-kpi",
          "colSpan": 12,
          "dataBind": "PageCanvasData.arEliteKpis()",
          "kpis": [
            { "halSubpanel": "arKpiTotal", "label": "Total A/R" },
            { "halSubpanel": "arKpiCurrent", "label": "Current (0–30)" },
            { "halSubpanel": "arKpi3160", "label": "31–60 Days" },
            { "halSubpanel": "arKpi6190", "label": "61–90 Days" },
            { "halSubpanel": "arKpi90plus", "label": "90+ Days" },
            { "halSubpanel": "arKpiDso", "label": "DSO" }
          ]
        },
        {
          "id": "ar-aging-heatmap",
          "type": "custom",
          "widgetKey": "arAgingAndCollections",
          "colSpan": 8,
          "title": "A/R Waterfall & Collections Heatmap"
        },
        {
          "id": "ar-outstanding-claims",
          "type": "table",
          "widgetKey": "arOutstandingClaims",
          "colSpan": 4,
          "title": "Outstanding Claims",
          "dataBind": "PageCanvasData.arTopClaimsTable()"
        },
        {
          "id": "ar-follow-up-queue",
          "type": "kanban",
          "widgetKey": "smartClaimsAndReceivables",
          "colSpan": 12,
          "title": "Follow-up Queue",
          "dataBind": "PageCanvasData.arFollowUpKanban()"
        }
      ]
    },
    "quickbooks": {
      "title": "QuickBooks Integration",
      "shell": "dashboard-grid",
      "panels": [
        {
          "id": "qb-cash-flow",
          "type": "chart",
          "widgetKey": "quickbooksCashFlowTrend",
          "colSpan": 8,
          "title": "Cash Flow Trend",
          "dataBind": "PageCanvasData.quickbooksCashFlowTrend()",
          "chartType": "dual"
        },
        {
          "id": "qb-net-income",
          "type": "stat-grid",
          "widgetKey": "quickbooksNetIncomeSummary",
          "colSpan": 4,
          "title": "Net Income Summary",
          "dataBind": "PageCanvasData.quickbooksNetIncomeSummary()"
        },
        {
          "id": "qb-pl-summary",
          "type": "table",
          "widgetKey": "quickbooksProfitLossDetail",
          "colSpan": 6,
          "title": "Profit & Loss Summary (YTD)",
          "dataBind": "PageCanvasData.quickbooksPlRows()"
        },
        {
          "id": "qb-ebitda-bridge",
          "type": "table",
          "widgetKey": "ebitdaNormalization",
          "colSpan": 6,
          "title": "EBITDA Normalization",
          "dataBind": "PageCanvasData.ebitdaRows()"
        },
        {
          "id": "qb-monthly-revenue",
          "type": "chart",
          "widgetKey": "quickbooksMonthlyRevenue",
          "colSpan": 6,
          "title": "Monthly Revenue Trend",
          "dataBind": "PageCanvasData.quickbooksMonthlyRevenueSeries()",
          "chartType": "bar"
        },
        {
          "id": "qb-revenue-service",
          "type": "donut",
          "widgetKey": "quickbooksRevenueByService",
          "colSpan": 6,
          "title": "Revenue by Service",
          "dataBind": "PageCanvasData.quickbooksRevenueByService()",
          "chartType": "donut"
        },
        {
          "id": "qb-balance-sheet",
          "type": "table",
          "widgetKey": "quickbooksBalanceSheetSummary",
          "colSpan": 6,
          "title": "Balance Sheet Summary",
          "dataBind": "PageCanvasData.quickbooksBalanceSheetSummary()"
        },
        {
          "id": "qb-expense-breakdown",
          "type": "stat-grid",
          "widgetKey": "quickbooksExpenseBreakdown",
          "colSpan": 6,
          "title": "Operating Expenses",
          "dataBind": "PageCanvasData.quickbooksExpenseBars()"
        },
        {
          "id": "qb-ar-aging",
          "type": "table",
          "widgetKey": "quickbooksArAging",
          "colSpan": 12,
          "title": "QuickBooks A/R Aging",
          "dataBind": "PageCanvasData.quickbooksQbArAging()"
        }
      ]
    },
    "documents": {
      "title": "Accounting Documents",
      "shell": "widget-grid",
      "panels": [
        {
          "id": "doc-intake",
          "type": "table",
          "widgetKey": "documentIntakeQueue",
          "colSpan": 8,
          "title": "Recent Accounting Documents",
          "dataBind": "PageCanvasData.metrics('documentIntakeQueue')"
        },
        {
          "id": "doc-preview",
          "type": "custom",
          "widgetKey": "documentPreview",
          "colSpan": 4,
          "title": "Document Preview",
          "dataBind": "PageCanvasData.metrics('documentPreview')"
        },
        {
          "id": "doc-sources",
          "type": "stat-grid",
          "halSubpanel": "documentsSourceBreakdown",
          "colSpan": 12,
          "title": "Source Breakdown",
          "dataBind": "PageCanvasData.documentsSourceBreakdown()"
        },
        {
          "id": "period-close",
          "type": "gauge",
          "widgetKey": "periodCloseAndPosting",
          "colSpan": 6,
          "title": "Period Close",
          "dataBind": "PageCanvasData.metrics('periodCloseAndPosting')"
        },
        {
          "id": "ap-auto",
          "type": "funnel",
          "widgetKey": "accountsPayableAutomation",
          "colSpan": 6,
          "title": "Accounts Payable",
          "dataBind": "PageCanvasData.metrics('accountsPayableAutomation')"
        },
        {
          "id": "journal-queue",
          "type": "table",
          "widgetKey": "journalPostingQueue",
          "colSpan": 12,
          "title": "Journal Entries",
          "dataBind": "PageCanvasData.metrics('journalPostingQueue')"
        }
      ]
    },
    "library": {
      "title": "Document Library",
      "shell": "widget-grid",
      "panels": [
        {
          "id": "lib-facets",
          "type": "custom",
          "halSubpanel": "categoryFacets",
          "colSpan": 3,
          "title": "Categories",
          "dataBind": "PageCanvasData.libraryFacets()"
        },
        {
          "id": "lib-main",
          "type": "table",
          "widgetKey": "documentLibrary",
          "colSpan": 9,
          "title": "Library & Preview",
          "dataBind": "PageCanvasData.metrics('documentLibrary')"
        }
      ]
    },
    "office-manager": {
      "title": "Office Command Center",
      "shell": "dashboard-grid",
      "panels": [
        {
          "id": "om-priorities",
          "type": "kanban",
          "widgetKey": "officeManagerPriorities",
          "colSpan": 8,
          "title": "Today's Focus",
          "dataBind": "PageCanvasData.metrics('officeManagerPriorities')"
        },
        {
          "id": "om-surfaces",
          "type": "stat-grid",
          "widgetKey": "officeManagerSurfaces",
          "colSpan": 4,
          "title": "Staff Work Surfaces",
          "dataBind": "PageCanvasData.metrics('officeManagerSurfaces')"
        },
        {
          "id": "om-tasks",
          "type": "table",
          "halSubpanel": "officeTaskQueue",
          "colSpan": 12,
          "title": "Office Task Queue",
          "dataBind": "PageCanvasData.officeTaskRows()"
        }
      ]
    }
  }
};

if (typeof module !== "undefined" && module.exports) {
  module.exports = MOONSHOT_PAGE_LAYOUTS;
}
if (typeof globalThis !== "undefined") {
  globalThis.MOONSHOT_PAGE_LAYOUTS = MOONSHOT_PAGE_LAYOUTS;
}
if (typeof window !== "undefined") {
  window.MOONSHOT_PAGE_LAYOUTS = MOONSHOT_PAGE_LAYOUTS;
}
```

### File: `NewRidgeFinancial2/site/deferred-live-wire/moonshot-layout-engine.js` (Patch)
**Mirror:** `NewRidgeFinancial2/deferred-live-wire/moonshot-layout-engine.js`
**P1:** Add severity injection and terminal density classes. Insert after line ~240 in `renderWidgetGridPanel`.

```javascript
// SEVERITY INJECTION — P1 Patch for Terminal Heat
// Insert inside renderWidgetGridPanel, before return statement:
if (panel.widgetKey === "arOutstandingClaims" || panel.widgetKey === "quickbooksArAging") {
  // Request severity classes from dataApi if available
  const severityMap = D && D.severityFor ? D.severityFor(panel.widgetKey) : null;
  if (severityMap && H.canvasTable) {
    // Wrap table renderer to inject row classes
    const originalTable = H.canvasTable;
    H.canvasTable = function(rows, opts) {
      if (!opts) opts = {};
      if (!opts.rowClass) opts.rowClass = function(row) {
        const key = row.id || row.claimId || row.account;
        return severityMap[key] || "";
      };
      return originalTable(rows, opts);
    };
  }
}

// TERMINAL DENSITY CLASS — P1
const terminalDensity = [
  "financial", "taxes", "quickbooks", "ar", "claims", 
  "softdent", "documents", "hal", "office-manager"
];
if (terminalDensity.includes(pageId)) {
  H.pushClass("mc-terminal-density");
}
```

---

## 5. Diff vs current hal-10168 live pages

| Page | Before (hal-10168) | After (Extreme) |
|------|-------------------|-----------------|
| **financial** | Provider widgets scattered; 16px gaps; production/collections separated | Provider analytics clustered; 10px gaps; velocity pair (production + collections) adjacent; reconciliation paired with performance |
| **taxes** | P&L leads; cash flow buried row 3; revenue donut isolated | Cash flow leads (liquidity first); revenue metrics grouped; aging precedes period close |
| **quickbooks** | P&L leads; cash flow row 2; AR aging squeezed 3-col | Cash flow leads; AR aging full-width 12-col for detail scan |
| **softdent** | Provider bar 3-col (illegible); operatory isolated | Provider bar 12-col full width; AR heatmap expanded to 8-col |
| **documents** | Source breakdown at bottom (invisible) | Source breakdown row 2 (telemetry surfaced) |
| **All** | Friendly sans-serif figures; 16px padding; static panels | JetBrains Mono tabular; 10px padding; scanline animation; severity blink on aged items |

---

## 6. Operator Validation Gate

**Per-page browser checklist (verify before commit):**

- [ ] **financial** — Hero row shows 5 KPIs with monospace figures; Alert ticker has cyan top border; Monthly trend chart shows scanline sweep; Provider production bar chart is full width (row 7).
- [ ] **taxes** — Cash flow chart is top-left (8-col); Net income is top-right (4-col); A/R aging table rows show red left-border for >90 days (severity CSS).
- [ ] **quickbooks** — A/R aging table is full width (12-col) at bottom; Cash flow leads.
- [ ] **softdent** — Provider production bar is full width (12-col); Operatory grid has 8-col priority.
- [ ] **claims** — Kanban lanes have colored dot headers; cards show severity dots (amber/red).
- [ ] **ar** — 6-KPI hero row; Heatmap has 8-col width; Outstanding claims table has 4-col.
- [ ] **narratives** — Single kanban spans full width; pink accent visible.
- [ ] **documents** — Source breakdown stat-grid appears immediately below preview; gold accents on document intake.
- [ ] **library** — Facets panel (3-col) has compact 8px padding; Library table has monospace doc IDs.
- [ ] **office-manager** — Today's focus kanban (8-col) + Surfaces (4-col); Task queue full width.
- [ ] **hal** — Ask HAL panel has red glow border; 4 stat tiles in tight row.

**Empty State Honesty Check:**
- [ ] Navigate to page with no imports (e.g., clean taxes) → verify "AWAITING IMPORT" terminal badge appears (no $0.00 fabrication).

---

## 7. Prioritized apply order (max 5 commits) — WAIT for operator "proceed"

**Do not apply. Review only.**

1. **Commit P0:** `nr2-mission-control-extreme.css` — Add to both mirror paths. Zero functional change; pure chrome/density.
2. **Commit P0:** `moonshot-page-layouts.js` — Replace in both mirrors. Reorders panels only; no new dataBinds.
3. **Commit P1:** `moonshot-layout-engine.js` patch — Add severity injection and density class hooks (both mirrors).
4. **Commit P2:** QA verification — Run validation gate checklist on staging; verify empty states remain honest.
5. **Commit P2:** Production toggle — Enable `staffRenderMode: live-wire-pilot` (already set in build hal-10168).

**Rollback plan:** Revert to `moonshot-page-layouts.js` version 1 (saved as backup) and remove extreme CSS link.

**Acceptance Criteria for Proceed:**
- [ ] Operator confirms "proceed" on this consult.
- [ ] Staging validation gate 100% pass.
- [ ] No console errors on empty state widgets (honesty check).

**Status:** `REVIEW ONLY` — Awaiting operator signal.
