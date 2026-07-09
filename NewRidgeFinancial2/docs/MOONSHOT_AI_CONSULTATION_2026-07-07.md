# Moonshot AI Consultation — NR2 Wiring Guide

**Date:** 2026-07-07  
**Build epoch:** `hal-10054` (`LAYOUT_EPOCH = "moonshot-mockup"`)  
**Model:** kimi-k2.5 (live API + codebase audit)  
**Status:** **PROPOSED ONLY — do not implement until operator approval**

**Mockup gallery:** `.local_logs/moonshot_financial_eval/page_mockups/` (also served at `http://127.0.0.1:8799/index.html`)  
**Live reload:** `https://127.0.0.1:8765/?v=hal-10054&__nr2_purge=1`

**Validator snapshot (2026-07-07):** `validate-hal.mjs` 103 suites pass · `validate-pages.mjs` pass · `audit-mockup-parity.mjs` 10/10 staff pages pass.

---

## Executive Summary

NR2 Financial (8765) is on the Moonshot mockup epoch: staff pages render through `PageCanvas` + mockup vocabulary CSS; HAL is partially renamed toward mockup class names. Five programs need explicit wiring guidance:

| Program | Port | Schema epoch | Primary gap |
|---------|------|--------------|-------------|
| **Financial** | 8765 | moonshot-mockup | Charts skipped by `NR2MoonshotUI.enhancePage`; canvas charts are inline SVG only |
| **Workstation** | 8766 | `hp-*` legacy | Intentionally separate; prompt chips + SideNotesIM already work |
| **SoftDent** | 8765 | moonshot-mockup | Mockup funnel has 4 stages; live has 3. No operatory grid / chair timeline |
| **QuickBooks** | 8765 | moonshot-mockup | Live uses `treemap-list` + `metric-row`; mockup uses `dashboard-grid`, `kpi-card`, `sync-badge`, `chart-large` |
| **SideNotes** | 8765 HAL + 8766 WS | mixed | HAL `sidenote-*` panel live; 8765 cannot read SideNotesIM message text by design |

**Recommended implementation order:** QuickBooks visual parity (P0) → SoftDent funnel + operatory (P0/P1) → in-canvas chart wiring (P1) → SideNotes cross-port hub poll (P1) → Workstation moonshot skin (P2, optional).

---

## Current Architecture (accurate)

### Schema & chrome

- **`site/moonshot-page-registry.js`** — `PageSchema.PAGES[id].commands`, `.widgets`, `NAV_GROUPS`. Widget keys drive sub-nav labels and `data-hal-widget-key` scroll targets.
- **`site/nr2-moonshot-mockup-chrome.js`** — Renders `nav-sublist` / `nav-subitem` with `data-nav-widget` (staff) or `data-nav-panel` (HAL). Emoji nav icons in chrome; SVG icons via `AppIcons` in page bodies.
- **`site/page-canvas.js`** — Staff renderers (`renderFinancial`, `renderSoftdent`, `renderQuickbooks`, …). Helpers: `canvasMetricTile`, `canvasFunnel`, `chartContainer`, `canvasTreemap`, etc.
- **`site/page-canvas-data.js`** — `PageCanvasData` snapshot binders (not in `moonshot-page-registry.js`; validators require it as separate module).
- **`site/hal-page-canvas.js`** + **`site/hal-page.js`** — HAL body + SideNotes panel, prompt chips, stress panel.
- **`site/nr2-moonshot-ui.js`** — Phase 8 overlays. **Critical:** `enhancePage()` returns early when `PageCanvas.hasPage(pageId)` — canvas pages never get `NR2Charts` injection.

### Subpage scroll (already wired)

```javascript
// app.js — sub-nav click → smooth scroll to widget
function scrollStaffWidgetIntoView(widgetKey) {
  const root = appPage || document.getElementById("appPage");
  const target = root.querySelector(`[data-hal-widget-key="${widgetKey}"]`);
  if (target) target.scrollIntoView({ behavior: "smooth", block: "nearest" });
}
```

HAL panel map: `halAskHal` → `askHal`, `halImportHealth` → `importHealth`, `sidenotesProgram` → `sidenotes`, `officeManagerSurfaces` → `workSurfaces`.

### Charts inventory

| Module | Used for | Wired to PageCanvas? |
|--------|----------|---------------------|
| `site/charts/practice-pulse.js` | Financial / A/R pulse | No (enhancePage skip) |
| `site/charts/ar-heatmap.js` | A/R heatmap | No |
| `site/charts/import-timeline.js` | Import sync timeline | No |
| `site/charts/posting-kanban.js` | Documents posting | No |

Staff pages use inline SVG helpers in `page-canvas.js` (`vBarChart`, `dualLineChart`, `conicDonut`, …) instead.

---

## Program 1 — Financial (8765)

### Prompts & HAL commands

**Schema** (`moonshot-page-registry.js` → `financial.commands`):

- `"Summarize MTD production"`
- `"Compare to prior month"`
- `"Explain payer mix"`

**Proposed wiring** — map chips in page chrome to HAL drawer (mirror HAL page pattern):

```javascript
// nr2-moonshot-mockup-chrome.js or app.js — proposed handler
document.querySelectorAll("[data-page-command]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const text = btn.getAttribute("data-page-command");
    if (typeof openHalDrawer === "function") openHalDrawer({ seed: text, pageId: "financial" });
  });
});
```

HAL context should include `PageCanvasData.financialKpis()`, import readiness from `/api/import-readiness`, and visible widget keys from `PageSchema.byId("financial").widgets`.

### Icons

| Surface | Key | Source |
|---------|-----|--------|
| Nav | `financial` | `AppIcons.nav("financial")` |
| Widgets | `practiceFinancialOverview`, `financialProductionTrend`, `payerMixAndCollections`, `providerPerformance` | `AppIcons.widget(key)` |

### Widgets & subpages

| Widget key | Title | Renderer region |
|------------|-------|-----------------|
| `practiceFinancialOverview` | Practice Financial Overview | KPI row + overview panel |
| `financialProductionTrend` | Production MTD & 12-Month Trend | Trend chart panel |
| `payerMixAndCollections` | Payer Mix & Collection Rate | Donut / mix panel |
| `providerPerformance` | Production by Provider | Provider bar chart |

Sub-nav: auto-generated from `PageSchema.widgets` when Financial is active (`nr2-moonshot-mockup-chrome.js`).

### Charts — proposed

Add canvas-native chart mounts without re-enabling legacy `.ms-page-body` overlay:

```javascript
// nr2-moonshot-ui.js — proposed
async function enhanceCanvasCharts(pageId, root) {
  if (pageId !== "financial" && pageId !== "ar") return;
  const host = root.querySelector("[data-hal-widget-key='financialProductionTrend'] .chart-container");
  if (host && typeof NR2Charts !== "undefined") {
    const canvas = document.createElement("canvas");
    canvas.id = "nr2-practice-pulse";
    host.appendChild(canvas);
    const reports = await fetchJson("/api/financial-reports");
    NR2Charts.renderPracticePulse("nr2-practice-pulse", {
      productionUsd: reports.productionUsd,
      collectionsUsd: reports.collectionsUsd,
      arTotalUsd: reports.arAging?.totalOutstanding,
    });
  }
}

// In enhancePage(), after early-return guard, call:
// if (PageCanvas.hasPage(pageId)) { await enhanceCanvasCharts(pageId, root); return; }
```

### Visual parity

Mockup: `.local_logs/.../page_mockups/financial.html`  
**Done:** `metric-row`, `kpi-grid`, provider bars, aging tiles.  
**Gap:** No canvas `NR2Charts` pulse; production trend is SVG-only.

---

## Program 2 — Workstation (8766)

### Scope decision

Workstation stays on **`hp-*` legacy** (`site/workstation-page.js`, port 8766, `NR2_WORKSTATION_ONLY`). Not part of moonshot-mockup epoch unless operator requests migration.

### Prompt chips (existing)

`DEFAULT_MESSAGE_PROMPTS` — Patient arrived, Doctor ready, Need assistant, Front desk, Running behind, X-ray ready, Checkout, Emergency, etc. Templates use `{station}` substitution.

HAL workstation prompts use `hp-action` chips with `promptIcon()` heuristics (sidenote → `AppIcons.nav("sidenotes")`, import → softdent, etc.).

### Icons

Uses `AppIcons` wrapped in `hp-ico` / `hp-card__ico` — same SVG registry as 8765, different CSS namespace.

### Widgets / surfaces

- Ask HAL tab (local Ollama / gateway)
- Office channel messaging (SideNotes-like, distinct UI)
- Device / station identity from `workstation-schema.js`

### HAL integration

- pywebview bridge: `DesktopBridge.show_workstation_message_popup`, `show_workstation_main_window`
- Clinical paste bridge on 8765: `NR2MoonshotUI.renderClinicalBridge()` posts to `/api/clinical-summaries` (8765 reads summaries from 8766 workflow)

### Proposed (P2 only) — visual alignment

Share CSS variables from `nr2-moonshot-mockup-theme.css` via a thin `workstation-moonshot-bridge.css` — map `hp-card` borders/spacing to mockup `--bg-secondary` tokens. **Do not rename `hp-*` classes** in first pass.

---

## Program 3 — SoftDent (8765)

### Prompts

`PageSchema` commands: `"Review A/R aging"`, `"Open new patient summary"`, `"Explain case acceptance"`.

Wire to HAL with page context:

```javascript
// hal-page.js — proposed pattern (extend existing prompt-chip handler)
function buildSoftdentHalContext() {
  const D = typeof PageCanvasData !== "undefined" ? PageCanvasData : null;
  return {
    kpis: D ? D.softdentKpis() : [],
    aging: D ? D.softdentAgingBars() : null,
    practice: D ? D.practiceStats() : {},
    readiness: window.__NR2_IMPORT_READINESS || null,
  };
}
```

### Icons

| Key | Usage |
|-----|-------|
| `softdent` | Nav |
| `careDeliveryPerformance`, `softdentArAging`, `softdentResponsibility` | Widget headers |
| `newPatients`, `treatmentPlanSummary`, `caseAcceptance`, `hygieneRecall` | Stat widgets |

### Widgets vs mockup

| Widget key | Live (`renderSoftdent`) | Mockup gap |
|------------|-------------------------|------------|
| `careDeliveryPerformance` | `canvasStatGrid` glance stats | OK |
| `softdentArAging` | `chartContainer` + `vBarChart` | OK |
| `softdentResponsibility` | `conicDonut` | OK |
| `caseAcceptance` | `canvasFunnel` **3 steps** | Mockup has **4 steps** (Presented → Accepted → Scheduled → Completed) |
| `hygieneRecall` | `canvasRecallCalendar` | OK |
| — | **Missing** | **Operatory grid** — 6-chair day timeline in mockup |

### Proposed — 4-stage funnel (P0)

```javascript
// page-canvas.js — renderSoftdent(), extend funnelSteps
const funnelSteps = [
  { label: "Presented", value: fmtClaim(practice.treatmentPresented || ca.plansPresented) },
  { label: "Accepted", value: fmtClaim(ca.plansAccepted || practice.caseAccepted) },
  { label: "Scheduled", value: fmtClaim(practice.treatmentScheduled || ca.plansScheduled) }, // new data field
  { label: "Completed", value: fmtClaim(practice.treatmentCompleted || ca.plansCompleted) },
];
```

Add `treatmentScheduled` / `treatmentCompleted` to `PageCanvasData.practiceStats()` from SoftDent dashboard export when available.

CSS: extend `nr2-mockup-page-vocabulary.css`:

```css
.funnel-chart { display: flex; flex-direction: column; gap: 8px; }
.funnel-step { display: grid; grid-template-columns: 100px 1fr 48px; align-items: center; gap: 12px; }
.funnel-bar { height: 28px; border-radius: 4px; background: linear-gradient(90deg, var(--accent-sage), var(--accent-gold)); }
```

Update `canvasFunnel()` to emit mockup class names (`funnel-chart`, `funnel-step`, `funnel-bar`, `funnel-label`, `funnel-value`).

### Proposed — operatory grid (P0)

```javascript
// page-canvas.js — new helper
function canvasOperatoryGrid(chairs) {
  if (!chairs || !chairs.length) {
    return `<div class="operatory-grid">${canvasEmpty("Operatory schedule appears when SoftDent export includes chair columns.")}</div>`;
  }
  return `<div class="operatory-grid">${chairs.map((chair) => `
    <div class="operatory-column">
      <header class="operatory-column__head">${esc(chair.name)}</header>
      ${(chair.slots || []).map((slot) => `
        <article class="operatory-slot operatory-slot--${esc(slot.tone || "default")}">
          <time>${esc(slot.time)}</time>
          <strong>${esc(slot.patient)}</strong>
          <span>${esc(slot.procedure || "")}</span>
        </article>`).join("")}
    </div>`).join("")}</div>`;
}

// PageCanvasData — proposed
function softdentOperatoryGrid() {
  const practice = practiceStats();
  return practice.operatoryChairs || null; // [{ name, slots: [{ time, patient, procedure, tone }] }]
}
```

Register widget in `moonshot-page-registry.js`:

```javascript
{ key: "softdentOperatoryGrid", title: "Operatory Schedule" },
```

Insert as `gridCol(12, canvasPanel({ … widgetKey: "softdentOperatoryGrid", body: canvasOperatoryGrid(D.softdentOperatoryGrid()) }))`.

### Subpages

After operatory widget added, sub-nav auto-lists: Care Delivery Summary, A/R Aging, Insurance vs Patient, New Patients, Treatment Plans, Case Acceptance, Hygiene & Recall, **Operatory Schedule**.

---

## Program 4 — QuickBooks (8765)

### Prompts

`"Explain YTD net income"`, `"Review EBITDA add-backs"`, `"Show supply spend"`.

### Icons

`AppIcons.nav("quickbooks")`, widgets: `quickbooksProfitLossDetail`, `ebitdaNormalization`, `quickbooksSyncHealth`.

### Live vs mockup

**Live** (`renderQuickbooks`):

- Top: `metric-row` + `canvasMetricTile` KPIs
- Row 1: `canvasTreemap` (7 col) + `canvasWaterfall` (5 col)
- Row 2: reconciliation `canvasTable`

**Mockup** (`page_mockups/quickbooks.html`):

- Header: `sync-badge` with pulsing `sync-indicator` + date range
- `dashboard-grid` with four `card kpi-card`
- `chart-large` P&amp;L trend (12 mo)
- `chart-medium` expense breakdown

### Proposed — full mockup layout (P0)

**1. Vocabulary CSS** — add to `nr2-mockup-page-vocabulary.css`:

```css
.sync-badge { display: inline-flex; align-items: center; gap: 8px; padding: 8px 16px;
  background: var(--bg-secondary); border: 1px solid var(--border-color); border-radius: 6px; font-size: 12px; }
.sync-indicator { width: 8px; height: 8px; border-radius: 50%; background: var(--accent-green);
  box-shadow: 0 0 8px var(--accent-green); animation: nr2-sync-pulse 2s infinite; }
.dashboard-grid { display: grid; grid-template-columns: repeat(12, 1fr); gap: 24px; }
.kpi-card { grid-column: span 3; }
.chart-large { grid-column: span 7; min-height: 320px; }
.chart-medium { grid-column: span 5; min-height: 320px; }
@keyframes nr2-sync-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
```

**2. Page chrome sync header** — extend `MoonshotMockupChrome.renderPageHeader()` for `quickbooks` only:

```javascript
function renderQuickbooksSyncBadge(readiness) {
  const level = readiness?.sources?.quickbooks?.level || readiness?.level || "unknown";
  const live = level === "fresh";
  return `<div class="sync-badge" role="status">
    <span class="sync-indicator" style="background:${live ? "var(--accent-green)" : "var(--accent-amber)"}"></span>
    ${live ? "QuickBooks synced" : "Sync stale — review import"}
  </div>`;
}
```

**3. Replace `renderQuickbooks` body structure:**

```javascript
function renderQuickbooks() {
  const D = dataApi();
  const kpis = D ? D.quickbooksKpis() : [];
  const plTrend = D ? D.quickbooksPlTrend() : null; // proposed 12-mo series
  const expenseBars = D ? D.quickbooksExpenseBars() : null;
  const plRows = D ? D.quickbooksPlRows() : [];

  const kpiCards = kpis.slice(0, 4).map((k) => `
    <div class="card kpi-card" data-hal-widget-key="${esc(k.widgetKey || "quickbooksProfitLossDetail")}">
      <div class="card-header"><span class="card-title">${esc(k.label)}</span></div>
      <div class="card-value">${esc(k.value)}</div>
      ${k.delta ? `<span class="trend${k.delta.startsWith("-") ? " negative" : ""}">${esc(k.delta)}</span>` : ""}
    </div>`).join("");

  return `${stackOpen()}
    <div class="dashboard-grid">${kpiCards}</div>
    <div class="dashboard-grid">
      <div class="card chart-large" data-hal-widget-key="quickbooksProfitLossDetail">
        <div class="card-header"><span class="card-title">Profit &amp; Loss Trend (YTD)</span></div>
        ${plTrend ? chartContainer(dualLineChart(plTrend.labels, plTrend.series), true) : chartContainer(canvasEmpty("P&amp;L trend when QuickBooks export loads."))}
      </div>
      <div class="card chart-medium" data-hal-widget-key="ebitdaNormalization">
        <div class="card-header"><span class="card-title">Operating Expenses</span></div>
        ${expenseBars ? chartContainer(vBarChart(expenseBars.labels, expenseBars.values, "#00d4aa")) : chartContainer(canvasEmpty("Expense breakdown unavailable."))}
      </div>
    </div>
    <div class="dashboard-grid">
      <div class="card" style="grid-column: span 12" data-hal-widget-key="quickbooksProfitLossDetail">
        ${plRows.length ? canvasTable(["Account", "Amount", "Source", "Sync"], plRows.slice(0, 8).map(r => [r[0], r[1], "QuickBooks", "Synced"]), true) : canvasEmpty("Reconciliation rows when export loads.")}
      </div>
    </div>
  </div>`;
}
```

**4. Fix duplicate widget key in schema** — `quickbooks.widgets` lists `quickbooksProfitLossDetail` twice (P&amp;L + Operating Expenses). Proposed:

```javascript
widgets: [
  { key: "quickbooksProfitLossDetail", title: "Profit & Loss Summary (YTD)" },
  { key: "ebitdaNormalization", title: "EBITDA Normalization" },
  { key: "quickbooksExpenseBreakdown", title: "Operating Expenses" }, // new distinct key
],
```

**5. Charts:** mount `NR2Charts.renderImportTimeline` on QB page for QuickBooks source row from `/api/import-readiness`.

---

## Program 5 — SideNotes

### Surfaces

| Surface | File | Role |
|---------|------|------|
| HAL SideNotes panel | `hal-page.js` → `liveSideNotesHtml`, `sideNotesMonitorHtml` | Routing metadata, voice announce, station table |
| HAL widget | `hal-page-canvas.js` → `sideNotesProgramCardHtml` | Manager widget on HAL page |
| Office Manager | `moonshot-page-registry.js` → `sidenotesProgram` widget | Staff notes on office-manager page |
| Workstation messaging | `workstation-page.js` | Full compose + broadcast (`hp-*` UI) |
| External | SideNotesIM + `run-sidenotes-helper.bat` | Watcher for voice; message **text** stays in IM app |

### Prompts

HAL commands (office-manager / HAL): monitor sidenotes, staff notes. Workstation: template chips (Patient arrived, Doctor ready, …).

### Icons

`AppIcons.nav("sidenotes")`, `AppIcons.widget("sidenotesProgram")`, `AppIcons.ui("voice")`.

### Class vocabulary (post-rename)

`sidenote-live`, `sidenote-head`, `sidenote-list`, `sidenote-item`, `sidenote-badge--ok`, `sidenote-badge--off`, `sidenote-voice-btn`, `sidenote-stations-table`.

### HAL wiring

- `data-hal-cmd="Monitor sidenotes"` → scroll/focus `sidenotes` panel
- Voice test: `data-hal-voice-test` → `hal-voice.js` neural TTS
- Inbox poll: `/api/sidenotes/inbox` (existing); badges LIVE/OFFLINE from watcher status

### Proposed — 8765 hub awareness (P1)

8765 cannot read IM message bodies (by design). Proposed indicator when 8766 posts office broadcast:

```python
# browser_app.py — proposed
@app.route("/api/hub/notify", method="POST")
def hub_notify():
    payload = request.json or {}
    app_state.set("nr2:hub:last_broadcast", payload, ttl_seconds=604800)
    return {"ok": True}
```

```javascript
// hal-page.js — poll every 30s when SideNotes panel visible
async function refreshHubBroadcastBadge() {
  const r = await fetch("/api/hub/last-broadcast");
  const data = await r.json();
  const el = document.querySelector(".sidenote-live .sidenote-head");
  if (el && data?.at) el.dataset.officeAlert = data.at;
}
```

Workstation POST via existing loopback client after send.

### Subpages

HAL: `sidenotesProgram` → panel `sidenotes` via `data-nav-panel`. Office Manager: widget scroll via `data-nav-widget="sidenotesProgram"`.

---

## Shared Infrastructure Proposals

### 1. Unify chart enhancement for PageCanvas

```javascript
// nr2-moonshot-ui.js
async function enhancePage(pageId, root) {
  if (!root) return;
  const isCanvas = typeof PageCanvas !== "undefined" && PageCanvas.hasPage && PageCanvas.hasPage(pageId);
  if (isCanvas) {
    await enhanceCanvasCharts(pageId, root); // new — see Financial / QB / SoftDent sections
    return;
  }
  // … existing legacy path …
}
```

### 2. Page command chips in chrome

Render `PageSchema.commands` as `prompt-chips` in `MoonshotMockupChrome.renderPageHeader()` (HAL page already uses `prompt-chip` pattern).

### 3. Widget icon injection

In `canvasPanel()`, prepend `AppIcons.widget(widgetKey)` when key exists:

```javascript
const icon = typeof AppIcons !== "undefined" ? AppIcons.widget(widgetKey) : "";
const titleHtml = icon ? `${icon}<span>${esc(title)}</span>` : esc(title);
```

### 4. Audit script extensions

Extend `scripts/audit-mockup-parity.mjs` to assert:

- QuickBooks: `.dashboard-grid`, `.kpi-card`, `.sync-badge`
- SoftDent: `.funnel-chart` with ≥4 `.funnel-step`, `.operatory-grid` when data present

---

## P0 / P1 / P2 Backlog

### P0 — Mockup parity (operator-visible)

| # | Item | Files | Notes |
|---|------|-------|-------|
| 1 | QuickBooks mockup layout | `page-canvas.js`, `nr2-mockup-page-vocabulary.css`, `nr2-moonshot-mockup-chrome.js`, `moonshot-page-registry.js` | Replace treemap-first layout; add sync badge; fix duplicate widget key |
| 2 | SoftDent 4-stage funnel | `page-canvas.js`, `page-canvas-data.js`, vocabulary CSS | Match mockup funnel-chart |
| 3 | SoftDent operatory grid | `page-canvas.js`, `page-canvas-data.js`, `moonshot-page-registry.js` | New widget + data binder |
| 4 | HAL class rename cleanup | `hal-page.js`, `hal-page-canvas.js`, `nr2-moonshot-mockup-theme.css`, `app.js` | Remove stale `ms-hal-*` querySelectors; dedupe `sidenote-badge sidenote-badge--ok` |

### P1 — Wiring & charts

| # | Item | Files |
|---|------|-------|
| 5 | PageCanvas chart bridge | `nr2-moonshot-ui.js`, `site/charts/*.js` |
| 6 | Page command → HAL drawer | `app.js`, `nr2-moonshot-mockup-chrome.js` or mockup chrome |
| 7 | SideNotes hub broadcast badge | `browser_app.py`, `hal-page.js`, `workstation-page.js` |
| 8 | QB import timeline chart | `renderQuickbooks` + `NR2Charts.renderImportTimeline` |
| 9 | `quickbooksPlTrend()` data binder | `page-canvas-data.js` from P&amp;L export |

### P2 — Polish / optional

| # | Item | Files |
|---|------|-------|
| 10 | Workstation CSS token bridge | `workstation/index.html`, new `workstation-moonshot-bridge.css` |
| 11 | Widget header icons everywhere | `page-canvas.js` `canvasPanel()` |
| 12 | Mockup gallery CI link in operator runbook | `docs/OPERATOR_PILOT_RUNBOOK.md` |

---

## Validation Checklist (post-implementation)

- [ ] `node validate-hal.mjs` — 103 suites
- [ ] `node validate-pages.mjs`
- [ ] `node scripts/audit-mockup-parity.mjs` — extend for QB + SoftDent
- [ ] Visual: QB page matches `page_mockups/quickbooks.html` header + grid
- [ ] Visual: SoftDent funnel shows 4 stages; operatory grid renders with export data
- [ ] Sub-nav: every widget key scrolls to `[data-hal-widget-key]`
- [ ] HAL: prompt chips on Financial/QB/SoftDent seed drawer with page context
- [ ] SideNotes: LIVE/OFFLINE badge correct; hub broadcast indicator when 8766 posts
- [ ] Workstation: unchanged behavior on 8766; no regression to `hp-*` messaging
- [ ] Bump build stamp in `index.html`, `sw.js`, `nr2-build.json`, schema files

---

## Moonshot Live Response Notes

Full kimi-k2.5 response (22k chars): `.local_logs/moonshot_financial_eval/MOONSHOT_AI_CONSULTATION_LIVE_2026-07-07.md`

**Corrections applied in this document:**

- **No TDZ failure** — `PageCanvasData` lives in `page-canvas-data.js`; validators pass at hal-10054. Do not move class to `moonshot-page-registry.js` without cause.
- **No `HalPageWidgets.register()` API** — use existing `HalPageCanvas`, `hal-page.js`, and `app.js` scroll/HAL drawer patterns.
- **No `quickbooks-page.js`** — QuickBooks renders inside `page-canvas.js` `renderQuickbooks()`.
- **Workstation moonshot migration** — deferred P2; not required for Financial epoch sign-off.

---

## Approval Gate

**Nothing in this document is implemented.** Reply with approved P0 items (or full list) to begin coding. Recommended first slice: **P0 #1 QuickBooks mockup layout** (highest visual delta, isolated to 3–4 files).
