# Moonshot AI — Final Mockup & Widget Fix Report

**Date:** 2026-07-08  
**Build:** hal-10099 · epoch `moonshot-mockup`  
**Model:** kimi-k2.6 via `OPENROUTER_API_KEY` @ `api.moonshot.ai`  
**Sources:** Part 1 (`MOONSHOT_MOCKUP_FIX_COMPARISON_2026-07-08.md`) · Part 2 · Part 3  
**Audit:** `.local_logs/moonshot_financial_eval/MOCKUP_WIDGET_AUDIT_LATEST.md`  
**Scripts:** `run_moonshot_mockup_fix_comparison.py` · `run_moonshot_issues_4_6.py` · `run_moonshot_issues_4_6_part3.py`

---

## Executive summary

Moonshot (live kimi-k2.6) reviewed the mockup parity gaps, widget empty bodies, and Cursor fix plan. **Verdict:** diagnosis is correct; **priority reorder required.**

| Priority | Focus | Why |
|----------|-------|-----|
| **P0 #1** | Data pipeline | `softdent.procedures` + `softdent.claimStatus` missing; QB datasets stale 43+ hours |
| **P0 #2** | QuickBooks layout collapse | 10 nested `dashboard-grid` blocks → page renders as vertical strip; 5 empty placeholders |
| **P1 #3** | Renderer data resolution | Feed shows 50/50 widgets with data; bodies empty because `page-canvas.js` gets partial data bags |
| **P1 #4–6** | Chart panels → vocabulary → chart mount | DOM first, CSS second, `enhancePage` third |

**Library page** is the only page with full structural parity today. **9/10 staff pages** diverge from mockup gallery.

---

## Audit snapshot (2026-07-08)

| Page | Empty markers | Top mockup gap |
|------|---------------|----------------|
| financial | 6 | chart-container 4→1 |
| quickbooks | 5 | dashboard-grid 4→10 (nested) |
| softdent | 7 | chart-container missing |
| claims | 1 | chart-container missing; 6 real claim cards (mock has 23 placeholders) |
| ar | 0 | kpi-grid 3→1; chart-container 3→1 |
| taxes | 0 | missing kpi-card + kpi-grid |
| narratives | 2 | composer-grid 4→1 |
| documents | 1 | widget-grid 3→1 |
| office-manager | 1 | dashboard-grid + chart-container missing |
| library | 0 | **aligned** |

**sourceHealth:** SoftDent DEGRADED (9/11) · QuickBooks SUCCESS but 2/5 stale · documents/library OK

---

## Cursor plan vs Moonshot — reconciliation

### Agreement
- Phase A (data) is P0
- Phases D–F (panels, vocabulary, chart mount) are the correct mechanical sequence
- Phase G (sign-off / build bump) stays P2

### Moonshot disagreements
1. **QuickBooks layout is P0**, not P1 — page is unusable even when data exists
2. **Not a “badge honesty” problem** — fix `PageCanvas.resolveData()` / renderer binders, not HAL feed status alone
3. **Chart mount must follow panel insertion** — vocabulary can run in parallel

### Merged priority table

| Rank | Cursor | Moonshot | Action |
|------|--------|----------|--------|
| 1 | A — data | **1** | procedures + claimStatus exports; QB stale refresh |
| 2 | B — status honesty | **3** | Reframe: renderer `resolveData()` + `hasRenderableData()` |
| 3 | C — QB layout | **2** | Single root `dashboard-grid`; remove nested `dashboardHost` |
| 4 | D — chart panels | **4** | Add chart-container panels per page (audit counts) |
| 5 | E — vocabulary | **5** | taxes kpi-card; narratives 4-col composer; documents 3-col grid |
| 6 | F — chart mount | **6** | `enhancePage` for PageCanvas; replace-not-stack |
| 7 | G — sign-off | **7** | Validators + mockup gallery side-by-side |

---

## Implementation note (adapt Moonshot code to NR2)

Moonshot code blocks use illustrative patterns. **Adapt before paste:**

| Moonshot uses | NR2 actual |
|---------------|------------|
| `PageCanvas.renderFinancial = function` on global | `renderFinancial()` inside `page-canvas.js` IIFE; export via `PageCanvas.render` map |
| `window.HAL.bus.snapshot.datasets` | `PageCanvasData` + `SnapshotStore` + `buildProgramSnapshotCore()` |
| `NR2UI.enhancePage` | `NR2MoonshotUI.enhancePage(pageId, root)` in `nr2-moonshot-ui.js` |
| `renderARPage(container)` | `renderAr()` returning HTML string; wired in `PageViews.renderPageView` |
| White `#ffffff` cards in CSS | Dark mockup tokens in `nr2-mockup-page-vocabulary.css` (`--bg-surface`, etc.) |

---

# Issue 1: Data pipeline — CODE

### `import_sync.py`

```python
# Extend operational sync — already has build_daysheet_procedures_dataset() in
# _sync_operational_softdent_exports(). Ensure it runs and writes:
#   softdent_procedures_export.csv
#   softdent_claim_status_export.csv

def ensure_quickbooks_fresh(max_age_minutes: int = 1440):
    """Queue priority refresh when QB datasets exceed max age."""
    qb_sets = [
        "quickbooks.revenue", "quickbooks.profitAndLoss", "quickbooks.expenses",
        "quickbooks.expenseCategories", "quickbooks.ar",
    ]
    for ds_key in qb_sets:
        meta = get_dataset_meta(ds_key)  # adapt to import_contract diagnostics
        age = (meta or {}).get("age_minutes", 999999)
        if age > max_age_minutes:
            queue_priority_sync(ds_key, source="quickbooks", reason="stale_refresh")
```

**Operator:** `python NewRidgeFinancial2\import_sync.py`

### `page-canvas-data.js` — add binders

```javascript
function softdentProceduresRows() {
  const snap = currentSnapshot();
  const rows = snap?.claims?.procedures || snap?.dashboards?.softdent?.procedures || [];
  return Array.isArray(rows) ? rows : (rows.rows || []);
}

function softdentClaimStatusRows() {
  const snap = currentSnapshot();
  const rows = snap?.claims?.statusRows || [];
  return Array.isArray(rows) ? rows : (rows.rows || []);
}

function quickbooksDatasetStale(datasetKey, maxAgeMin = 1440) {
  const diag = importDiagnosticsFor(datasetKey);
  const age = diag?.ageMinutes ?? Infinity;
  return { stale: age > maxAgeMin, ageMin: age, rows: diag?.rows || [] };
}
```

### `hal-skills.js` — health checks

Extend `softDentReadSourceStatus()` to treat missing `softdent.procedures` / `softdent.claimStatus` as DEGRADED. Extend QB status when `expenseCategories` or `ar` age > 1440 min.

---

# Issue 2: Widget feed vs canvas empty — CODE

### `page-canvas.js`

```javascript
function hasRenderableData(snapshot, binderFn, minRows = 1) {
  if (!binderFn) return false;
  const result = binderFn();
  if (result == null) return false;
  if (result.hasData === false) return false;
  if (Array.isArray(result)) return result.length >= minRows;
  if (Array.isArray(result.points)) return result.points.length >= minRows;
  if (Array.isArray(result.rows)) return result.rows.length >= minRows;
  if (Array.isArray(result.labels)) return result.labels.length >= minRows;
  return typeof result === "object" && Object.keys(result).length > 0;
}

// In each render*(): call PageCanvasData binders directly; only canvasEmpty()
// when hasRenderableData returns false for THAT panel's binder — not global page empty.
```

**Root cause (Moonshot):** Feed metadata says SUCCESS because dashboard objects exist; individual series arrays are empty.

---

# Issue 3: QuickBooks layout collapse — CODE

### `page-canvas.js` — replace nested `dashboardHost()` pattern

```javascript
function renderQuickbooks() {
  if (quickbooksViewMode() === "legacy") return renderQuickbooksLegacy();
  const D = dataApi();
  const kpis = D ? D.quickbooksKpis() : [];
  const plTrend = D ? D.quickbooksPlTrend() : null;
  const expenseBars = D ? D.quickbooksExpenseBars() : null;
  const plRows = D ? D.quickbooksPlRows() : [];

  const kpiCards = (kpis.length ? kpis : [{ label: "Net income YTD", value: "—" }])
    .slice(0, 4)
    .map((k, i) => { /* kpi-card markup — existing pattern */ })
    .join("");

  // Option A (Moonshot): root dashboard-grid — NO widget-grid wrapper, NO per-row dashboardHost
  return `<div class="ms-page ms-page--quickbooks" data-nr2-layout="moonshot-qb-root">
    <div class="dashboard-grid">${kpiCards}</div>
    <div class="dashboard-grid">
      <div class="card chart-large widget-glow-border" data-hal-widget-key="quickbooksProfitLossDetail" data-nr2-chart-host="quickbooksProfitLossDetail">
        ${plTrend ? chartContainer(dualLineChart(plTrend.labels, plTrend.series), true)
          : chartContainer(canvasEmpty("Awaiting QuickBooks sync — P&amp;L trend will appear when export is loaded."))}
      </div>
      <div class="card chart-medium widget-glow-border" data-hal-widget-key="quickbooksExpenseBreakdown">
        ${expenseBars ? chartContainer(vBarChart(expenseBars.labels, expenseBars.values, "#00d4aa"))
          : chartContainer(canvasEmpty("Awaiting QuickBooks sync — expense breakdown will appear when export is loaded."))}
      </div>
    </div>
    <div class="dashboard-grid">
      <div class="card chart-full" data-hal-widget-key="ebitdaNormalization">
        ${plRows.length ? canvasTable(["Account", "Amount", "Source", "Sync"], /* rows */) 
          : canvasEmpty("Awaiting QuickBooks sync — P&amp;L rows will appear when export is loaded.")}
      </div>
    </div>
  </div>`;
}
```

### Sync badge — `nr2-moonshot-mockup-chrome.js`

Add `renderQuickbooksSyncBadge(readiness)` in page header tools when `pageId === "quickbooks"`.

---

# Issue 4: Missing chart panels — CODE

### Financial — 4 chart containers (mock=4, live=1)

Add to `renderFinancial()` after KPI ribbon:

```javascript
${gridCol(12, canvasPanel({
  title: "Analytics charts",
  widgetKey: "financialProductionTrend",
  colSpan: 12,
  body: `<div class="chart-panel-grid">
    <div class="chart-container" data-nr2-chart-host="financialProductionTrend"></div>
    <div class="chart-container" data-nr2-chart-host="payerMixAndCollections"></div>
    <div class="chart-container" data-nr2-chart-host="providerPerformance"></div>
    <div class="chart-container" data-nr2-chart-host="softdentProductionDaily"></div>
  </div>`,
}))}
```

### SoftDent — 4 chart containers

```javascript
<div class="chart-panel-grid">
  <div class="chart-container" data-hal-widget-key="softdentProduction" data-nr2-chart-host="softdentProductionDaily"></div>
  <div class="chart-container" data-hal-widget-key="softdentClaimStatus"></div>
  <div class="chart-container" data-hal-widget-key="softdentCollections"></div>
  <div class="chart-container" data-hal-widget-key="softdentArAging"></div>
</div>
```

### A/R — 3 kpi-grid tiles + 3 chart containers

```javascript
// kpi-grid with 3 kpi-tile (aging buckets)
<div class="kpi-grid">...</div>
<div class="chart-panel-grid">
  <div class="chart-container" data-nr2-chart-host="arAgingWaterfall"></div>
  <div class="chart-container" data-nr2-chart-host="payerMixAndCollections"></div>
  <div class="chart-container" data-nr2-chart-host="followUpQueue"></div>
</div>
```

### Claims — 4 chart containers + real claim cards (not 23 placeholders)

```javascript
<div class="chart-panel-grid">
  <div class="chart-container" data-hal-widget-key="claimsDenialRate"></div>
  <div class="chart-container" data-hal-widget-key="claimsTurnaround"></div>
  <div class="chart-container" data-hal-widget-key="claimsPayerMix"></div>
  <div class="chart-container" data-hal-widget-key="claimsPipeline"></div>
</div>
<!-- kanban-board with real claim-card count from claims export -->
```

### Office Manager — dashboard-grid (3) + chart-container (2)

```javascript
<div class="dashboard-grid stats-bar">...</div>
<div class="chart-panel-grid">
  <div class="chart-container" data-hal-widget-key="officeTaskQueue"></div>
  <div class="chart-container" data-hal-widget-key="sidenotesProgram"></div>
</div>
```

### Documents — widget-grid (3 sections)

```javascript
<div class="widget-grid">
  <div class="widget-card" data-hal-widget-key="documentsRecent">...</div>
  <div class="widget-card" data-hal-widget-key="documentsSourceBreakdown">...</div>
  <div class="widget-card" data-hal-widget-key="documentsPostingQueue">...</div>
</div>
```

---

# Issue 5: Page vocabulary — CODE

### `nr2-mockup-page-vocabulary.css` (dark mockup tokens — adapt Moonshot light CSS)

```css
.app--moonshot-mockup .ms-page .kpi-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}
.app--moonshot-mockup .ms-page .kpi-card {
  background: var(--bg-elevated, #252525);
  border: 1px solid var(--border-subtle, #333);
  border-radius: 8px;
  padding: 16px;
}
.app--moonshot-mockup .ms-page .composer-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.app--moonshot-mockup .ms-page .chart-panel-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}
@media (max-width: 1024px) {
  .app--moonshot-mockup .ms-page .composer-grid { grid-template-columns: 1fr 1fr; }
  .app--moonshot-mockup .ms-page .chart-panel-grid { grid-template-columns: 1fr; }
}
```

### Taxes — switch KPI row to `kpi-card` inside `kpi-grid` (replace `widget-card` for hero KPIs)

### Narratives — expand to 4-column `composer-grid`: CDT list | draft textarea | history | preview panel

---

# Issue 6: Chart mount / enhancePage — CODE

### `nr2-moonshot-ui.js`

```javascript
function mountChart(host, renderFn) {
  if (!host) return;
  host.classList.add("chart-mount--canvas");
  host.querySelectorAll(".nr2-chart-overlay, canvas").forEach((el) => el.remove());
  host.querySelectorAll(".trend-chart-svg, .bar-chart, .donut-chart").forEach((el) => {
    el.style.display = "none";
  });
  const overlay = document.createElement("div");
  overlay.className = "nr2-chart-overlay";
  host.appendChild(overlay);
  renderFn(overlay);
}

async function enhanceCanvasCharts(pageId, root) {
  const policy = chartMountPolicy[pageId];
  if (!policy) return;
  for (const { widgetKey, mount } of policy) {
    const host =
      resolveWidgetMount(root, widgetKey) ||
      root.querySelector(`[data-nr2-chart-host="${widgetKey}"] .chart-container`) ||
      root.querySelector(`[data-nr2-chart-host="${widgetKey}"]`);
    if (host && mount) mountChart(host, () => mount(host, widgetKey));
  }
}

async function enhancePage(pageId, root) {
  if (!root) return;
  if (typeof PageCanvas !== "undefined" && PageCanvas.hasPage && PageCanvas.hasPage(pageId)) {
    await enhanceCanvasCharts(pageId, root);
    return;
  }
  /* legacy ms-page path ... */
}
```

### `app.js` — after `PageViews.renderPageView(...)`

```javascript
if (typeof NR2MoonshotUI !== "undefined" && NR2MoonshotUI.enhancePage) {
  requestAnimationFrame(() => NR2MoonshotUI.enhancePage(currentId, appPage));
}
```

**F5 guard:** destroy existing `Chart.getChart(canvas)` before remount; sign-off test #6 expects ≤1 `.nr2-chart-overlay` after 5 reloads.

---

# Moonshot independent roadmap (next 5 commits)

| Commit | Focus | Files | Acceptance |
|--------|-------|-------|------------|
| **1** | Data: procedures + claimStatus + QB stale refresh | `import_sync.py`, `softdent_operational_pipeline.py` | SoftDent 11/11; QB 5/5 fresh |
| **2** | QB layout emergency + sync badge | `page-canvas.js`, `nr2-moonshot-mockup-chrome.js` | `dashboard-grid` count ≈ mockup; full-width page |
| **3** | Renderer resolveData + chart panels (financial, softdent, ar) | `page-canvas.js`, `page-canvas-data.js` | Empty markers → 0 when imports fresh |
| **4** | Vocabulary + remaining panels (claims, OM, documents, taxes, narratives) | `page-canvas.js`, `nr2-mockup-page-vocabulary.css` | `audit-mockup-parity.mjs` class counts match |
| **5** | enhancePage + replace-not-stack + sign-off | `nr2-moonshot-ui.js`, `app.js` | F5×5 ≤1 overlay; operator sign-off PASS |

---

# Operator smoke test

### CLI (before browser)
1. `node NewRidgeFinancial2/validate-pages.mjs` — green
2. `node NewRidgeFinancial2/scripts/audit-mockup-parity.mjs` — green
3. `node NewRidgeFinancial2/scripts/collect-mockup-widget-audit.mjs` — review empty counts
4. `python NewRidgeFinancial2/import_sync.py` — procedures + claim_status CSVs written

### Browser (8765)
5. `#quickbooks` — 4 KPI cards in one row; P&L + expense charts side-by-side; sync badge visible
6. `#financial` — KPI ribbon + 4 chart containers (not 1)
7. `#softdent` — 4 funnel steps + operatory grid + 4 chart panels
8. `#ar` — 3 kpi-tile + 3 chart containers
9. `#claims` — kanban populated; 4 mini charts; real claim count (not padded to 23)
10. `#taxes` — kpi-card / kpi-grid layout
11. `#narratives` — 4-column composer-grid
12. `#documents` — 3-section widget-grid
13. `#office-manager` — dashboard-grid + 2 charts
14. Rapid page switch + F5×5 on QuickBooks — no stacked `.nr2-chart-overlay`

### Mockup gallery
15. Side-by-side with `http://127.0.0.1:8799/index.html` at 1440px and 768px

---

# Appendix — source documents

| Part | File | Content |
|------|------|---------|
| 1 | `docs/MOONSHOT_MOCKUP_FIX_COMPARISON_2026-07-08.md` | Verdict, Issues 1–3, partial Issue 4 |
| 2 | `docs/MOONSHOT_MOCKUP_FIX_PART2_2026-07-08.md` | Issue 4 financial/softdent (partial) |
| 3 | `docs/MOONSHOT_MOCKUP_FIX_PART3_2026-07-08.md` | Issue 4 AR/claims/OM/docs, Issues 5–6, roadmap, smoke test |
| Audit | `.local_logs/.../MOCKUP_WIDGET_AUDIT_LATEST.md` | Auto page-by-page class counts |
| Prior | `docs/MOONSHOT_AI_CONSULTATION_2026-07-07.md` | Original mockup wiring guide |

---

**Moonshot final verdict:** Fix data + QB layout first (P0). Then renderer data resolution and chart panels (P1). Adapt all code blocks to NR2's IIFE `PageCanvas` / `PageCanvasData` / `NR2MoonshotUI` architecture before paste. Sign off only after mockup gallery side-by-side passes.
