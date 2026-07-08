# NR2 Mockup Parity & Widget Data — Plan and Report

**Date:** 2026-07-08  
**Build:** hal-10099 · epoch `moonshot-mockup`  
**Practice:** New Ridge Family Dental (solo operator)  
**Scope:** 8765 staff pages vs Moonshot mockup gallery; widget data pipeline  
**Consultation:** Live Moonshot AI (kimi-k2.6) + automated audit + codebase review  

**Related docs:**
- Moonshot code (raw): `MOONSHOT_MOCKUP_FIX_COMPARISON_2026-07-08.md`, `MOONSHOT_MOCKUP_FIX_PART3_2026-07-08.md`
- Moonshot synthesis: `MOONSHOT_MOCKUP_WIDGET_FINAL_REPORT_2026-07-08.md`
- Auto audit: `.local_logs/moonshot_financial_eval/MOCKUP_WIDGET_AUDIT_LATEST.md`
- Mockup gallery: `.local_logs/moonshot_financial_eval/page_mockups/` · `http://127.0.0.1:8799/index.html`

---

## 1. Status report

### What works today

| Area | Status | Evidence |
|------|--------|----------|
| Moonshot epoch enforced | OK | `LAYOUT_EPOCH = moonshot-mockup`; legacy `pv-*` retired |
| Structural validators | OK | `validate-pages.mjs`, `audit-mockup-parity.mjs` — 10/10 pass |
| HAL widget keys wired | OK | All schema widget keys present in rendered HTML |
| Library page | OK | Only page with full mockup class parity |
| Documents / library data | OK | sourceHealth SUCCESS |
| Moonshot API consult | OK | kimi-k2.6 via `OPENROUTER_API_KEY` @ `api.moonshot.ai` |

### What is broken (operator-visible)

| Problem | Impact | Root cause |
|---------|--------|------------|
| Widgets show empty / “Awaiting sync” | Operators see blank panels despite green HAL badges | Renderer binders return empty series; feed metadata ≠ panel body |
| QuickBooks page layout collapsed | Page looks like a narrow vertical strip | `dashboardHost()` nests 10 `dashboard-grid` blocks inside `widget-grid` without `col-12` |
| 9/10 pages don’t match mockups | Visual parity fails side-by-side with gallery | Missing `chart-container` panels, wrong grid vocabulary |
| SoftDent DEGRADED | Procedures, narratives, production depth limited | `softdent.procedures`, `softdent.claimStatus` exports missing (9/11 datasets) |
| QuickBooks stale | Expense breakdown, A/R aging empty or wrong | `expenseCategories`, `ar` datasets >24h old |

### Validators vs reality

Automated tests check **CSS class names**, not **data in panels** or **pixel layout**. A page can pass `audit-mockup-parity.mjs` and still show empty widgets or wrong grid width. Operator sign-off requires browser + mockup gallery comparison.

---

## 2. Findings summary

### Finding A — Data pipeline gaps (P0)

```
SoftDent:  9/11 connected — MISSING procedures, claimStatus
QuickBooks: 3/5 fresh     — STALE expenseCategories, ar (~43 hours)
```

- `import_sync.py` already calls `build_daysheet_procedures_dataset()` but exports may not land in import inbox.
- Payment/adjustment parsing may leave `sd_payments` at 0 (Moonshot extract report Phase 1).
- QB stale data causes `canvasEmpty()` in expense and A/R panels even when core P&L loads.

### Finding B — QuickBooks layout collapse (P0)

```1294:1336:NewRidgeFinancial2/site/page-canvas.js
  function renderQuickbooks() {
    ...
    return `${stackOpen()}
      ${dashboardHost(`<div class="dashboard-grid">${kpiCards}</div>`)}
      ${dashboardHost(`<div class="dashboard-grid">
```

Each `dashboardHost()` sits inside `widget-grid` without full-width span → parent 12-column grid assigns **1 column** per row. Audit: `dashboard-grid` mock=4, live=10.

### Finding C — Widget feed vs canvas disconnect (P1)

- `buildWidgetFeed()` reports **50/50 widgets with data**.
- Live HTML has **26+ empty/placeholder markers** across pages.
- HAL SUCCESS reflects dashboard object presence, not whether `PageCanvasData.productionTrendSeries()` etc. return arrays.

### Finding D — Missing mockup panels (P1)

| Page | Mockup expects | Live has |
|------|----------------|----------|
| financial | 4 chart-container | 1 |
| softdent | 4 chart-container | 0 |
| ar | 3 kpi-grid + 3 chart-container | 1 each |
| claims | 4 chart-container | 0 |
| office-manager | 3 dashboard-grid + 2 chart-container | missing |
| taxes | kpi-card + kpi-grid | widget-card only |
| narratives | 4 composer-grid | 1 |
| documents | 3 widget-grid | 1 |

### Finding E — Chart mount skipped (P1)

`NR2MoonshotUI.enhancePage()` returns early for PageCanvas pages. Inline SVG renders but live Chart.js overlays never mount; F5 reload can stack overlays when enabled.

### Finding F — Moonshot code is blueprint, not paste-ready

Moonshot provided code for all 6 issues but used generic patterns (`window.HAL.bus`, `NR2UI`, light CSS). Must adapt to:

- `PageCanvas` / `PageCanvasData` IIFE in `page-canvas.js` / `page-canvas-data.js`
- `SnapshotStore` + `Services.buildProgramSnapshotCore()`
- `NR2MoonshotUI.enhancePage(pageId, root)` in `nr2-moonshot-ui.js`
- Dark mockup tokens in `nr2-mockup-page-vocabulary.css`

---

## 3. Implementation plan

### Guiding principles

1. **Data before chrome** — empty panels with correct layout still fail operator sign-off.
2. **One grid discipline** — 12-column math; no unspanned children in `widget-grid`.
3. **Replace-not-stack charts** — one chart technology per host; destroy before remount.
4. **Mockup gallery is acceptance** — side-by-side at 1440px and 768px.
5. **Smallest shippable commits** — one concern per commit; bump build stamp after validators pass.

### Phase 0 — Operator prep (30 min, no code)

| Step | Action |
|------|--------|
| 0.1 | Start NR2 on 8765; confirm `https://127.0.0.1:8765/api/app-info` |
| 0.2 | Run `python NewRidgeFinancial2\import_sync.py` |
| 0.3 | Verify `softdent_procedures_export.csv` and `softdent_claim_status_export.csv` in import inbox |
| 0.4 | Refresh QuickBooks SDK sync if stale |
| 0.5 | Re-run `node NewRidgeFinancial2/scripts/collect-mockup-widget-audit.mjs` — baseline empty counts |

---

### Commit 1 — Data pipeline (P0) · target hal-10100

**Goal:** SoftDent 11/11 connected; QB 5/5 fresh; collections widgets show numbers.

| Task | File | Moonshot reference |
|------|------|-------------------|
| Ensure procedures + claim_status CSV written | `import_sync.py`, `softdent_operational_pipeline.py` | Issue 1 |
| Align payment/adjustment codes if `sd_payments=0` | `softdent_odbc_extract.py` | Extract report Phase 1 |
| QB stale guard / priority refresh | `import_sync.py` | Issue 1 `ensure_quickbooks_fresh()` |
| Wire binders for procedures, claim status, QB stale | `page-canvas-data.js` | Issue 1 binders (adapt to SnapshotStore) |
| Extend sourceHealth for missing datasets | `hal-skills.js`, `import-diagnostics.js` | Issue 1 health checks |

**Acceptance:**
- [ ] `sourceHealth.softdent` → SUCCESS (11/11)
- [ ] `sourceHealth.quickbooks` → no stale datasets
- [ ] Financial + SoftDent production/collection panels show numbers after sync
- [ ] `collect-mockup-widget-audit.mjs` empty count drops on financial, softdent, quickbooks

---

### Commit 2 — QuickBooks layout emergency (P0) · target hal-10101

**Goal:** QB page full width; matches mockup grid structure.

| Task | File | Moonshot reference |
|------|------|-------------------|
| Remove nested `dashboardHost()` wrappers | `page-canvas.js` `renderQuickbooks()` | Issue 3 Option A |
| Single root `dashboard-grid`: KPI row → chart-large + chart-medium → reconciliation table | `page-canvas.js` | Issue 3 |
| Sync badge in page header | `nr2-moonshot-mockup-chrome.js` | Issue 3 sync badge |
| Option B fallback: wrap each row in `widget-card col-12` if keeping `widget-grid` | `page-canvas.js`, CSS | Deep visual doc |

**Acceptance:**
- [ ] Audit: `dashboard-grid` count mock≈live (4 not 10)
- [ ] Page uses full content width at 1440px (not 1-column strip)
- [ ] 4 KPI cards in top row; P&L + expense charts side-by-side
- [ ] Side-by-side with `page_mockups/quickbooks.html`

---

### Commit 3 — Renderer data resolution (P1) · target hal-10102

**Goal:** Panels use live snapshot data; empty states only when binder truly empty.

| Task | File | Moonshot reference |
|------|------|-------------------|
| Add `hasRenderableData(binderResult)` helper | `page-canvas.js` or `widget-contract.js` | Issue 2 |
| Per-panel empty checks (not page-level blanket empty) | `page-canvas.js` all `render*()` | Issue 2 |
| Align widget feed DEGRADED when binder empty | `hal-skills.js` | Issue 2 |
| Analytics DB fallback when dashboard series empty | `page-canvas-data.js` | Extract Phase 2 |

**Acceptance:**
- [ ] No SUCCESS badge on panel whose body says “Awaiting QuickBooks sync” when QB P&L data exists
- [ ] Feed empty count matches HTML empty count in audit script

---

### Commit 4 — Chart panels (P1) · target hal-10103

**Goal:** Mockup panel counts per page.

| Page | Add | File |
|------|-----|------|
| financial | 4× `chart-container` in `chart-panel-grid` | `page-canvas.js` |
| softdent | 4× `chart-container` + keep operatory/funnel | `page-canvas.js` |
| ar | 3× `kpi-tile` + 3× `chart-container` | `page-canvas.js` |
| claims | 4× mini chart containers + real kanban (not 23 fake cards) | `page-canvas.js` |
| office-manager | `dashboard-grid` + 2× `chart-container` | `page-canvas.js` |
| documents | 3-section `widget-grid` | `page-canvas.js` |

**Acceptance:**
- [ ] Audit class counts within ±1 of mockup for each page
- [ ] All panels have `data-hal-widget-key` / `data-nr2-chart-host` for scroll + mount

---

### Commit 5 — Page vocabulary (P1) · target hal-10104

**Goal:** CSS + markup match mockup vocabulary.

| Page | Change | File |
|------|--------|------|
| taxes | `kpi-card` + `kpi-grid` for hero KPIs | `page-canvas.js`, CSS |
| narratives | 4-column `composer-grid` (CDT \| draft \| history \| preview) | `page-canvas.js` |
| documents | 3-column `widget-grid` | `page-canvas.js` |
| all | `chart-panel-grid`, dark tokens (not Moonshot light `#fff`) | `nr2-mockup-page-vocabulary.css` |

**Acceptance:**
- [ ] taxes: audit no longer reports MISSING `kpi-card`, `kpi-grid`
- [ ] narratives: `composer-grid` count mock≈live
- [ ] `audit-mockup-parity.mjs` PASS

---

### Commit 6 — Chart mount + sign-off (P1) · target hal-10105

**Goal:** Live charts mount; no double-stack on reload.

| Task | File | Moonshot reference |
|------|------|-------------------|
| `enhanceCanvasCharts(pageId, root)` for PageCanvas pages | `nr2-moonshot-ui.js` | Issue 6 |
| `mountChart()` replace-not-stack | `nr2-moonshot-ui.js` | Issue 6 |
| Hook after `PageViews.renderPageView` | `app.js` | Issue 6 |
| Fix QB cash flow `{ data: cf.net }` if still wrong | `page-canvas.js` | Deep visual P1 #7 |
| Run operator sign-off script | `scripts/run-moonshot-operator-signoff.mjs` | — |

**Acceptance:**
- [ ] F5×5 on QuickBooks: ≤1 `.nr2-chart-overlay`
- [ ] Charts animate on financial, ar, quickbooks when data present
- [ ] `run-moonshot-operator-signoff.mjs` ≥8 PASS
- [ ] Mockup gallery side-by-side sign-off (operator eyes)

---

## 4. File touch map

| File | Commits | Role |
|------|---------|------|
| `import_sync.py` | 1 | Procedures/claim_status exports, QB stale refresh |
| `softdent_odbc_extract.py` | 1 | Payment/adjustment codes |
| `page-canvas-data.js` | 1, 3 | Binders, fallbacks, stale detection |
| `page-canvas.js` | 2, 3, 4, 5 | Layout, panels, vocabulary markup |
| `hal-skills.js` | 1, 3 | sourceHealth, feed status honesty |
| `nr2-moonshot-mockup-chrome.js` | 2 | QB sync badge |
| `nr2-mockup-page-vocabulary.css` | 5 | kpi-grid, composer-grid, chart-panel-grid |
| `nr2-moonshot-ui.js` | 6 | enhancePage, mountChart |
| `app.js` | 6 | Post-render chart hook |
| `scripts/collect-mockup-widget-audit.mjs` | 3 | Feed vs HTML empty parity check |

---

## 5. Risk register

| Risk | Severity | Mitigation |
|------|----------|------------|
| Procedures export path wrong | High | Verify daysheet pipeline; check `C:\SoftDentFinancialExports` |
| Moonshot code pasted without adaptation | High | Use adaptation table in Section 2 Finding F |
| Chart double-mount on F5 | Medium | replace-not-stack in Commit 6 |
| Claims padded to 23 fake cards | Low | Use real claim count only (Moonshot + operator agree) |
| Validators pass but layout still wrong | Medium | Mockup gallery sign-off required |
| API key routing | Low | Use `OPENROUTER_API_KEY` @ `api.moonshot.ai`, temperature 1.0 |

---

## 6. Operator smoke test (post Phase 6)

### CLI
```powershell
cd C:\NewRidgeFamilyFinancial\NewRidgeFinancial2
node validate-pages.mjs
node scripts/audit-mockup-parity.mjs
node scripts/collect-mockup-widget-audit.mjs
python import_sync.py
node scripts/run-moonshot-operator-signoff.mjs
```

### Browser (8765)
1. `#quickbooks` — full width, 4 KPIs, P&L + expense charts, sync badge
2. `#financial` — KPI ribbon populated, 4 chart panels
3. `#softdent` — 4 funnel steps, operatory grid, 4 charts
4. `#ar` — 3 KPI tiles, 3 charts, queue populated
5. `#claims` — kanban with real claims, 4 mini charts
6. `#taxes` — kpi-card layout
7. `#narratives` — 4-column composer
8. `#documents` — 3-column widget grid
9. F5×5 on QuickBooks — no stacked overlays
10. Compare each page to `http://127.0.0.1:8799/index.html`

### Sign-off
Record operator name in sign-off log when satisfied. Bump build to hal-10105+.

---

## 7. Moonshot code inventory (what to implement)

Moonshot **did provide code** for all 6 issues. Use as blueprint; adapt to NR2 patterns.

| Issue | Moonshot delivered | NR2 adaptation |
|-------|-------------------|----------------|
| 1 Data | `import_sync` collectors, `PageCanvasData` binders, `hal-skills` health | Use `SnapshotStore`, existing `import_contract.py` keys |
| 2 Empty widgets | `hasRenderableData`, `resolveData`, SoftDent renderer patch | Integrate into IIFE helpers; per-panel `canvasEmpty()` |
| 3 QB layout | Flat `renderQuickbooks` with single `dashboard-grid` | Replace current `dashboardHost` pattern in existing function |
| 4 Panels | Per-page `chart-panel-grid` structures | Extend existing `renderFinancial`, `renderAr`, etc. |
| 5 Vocabulary | CSS for kpi-grid, composer-grid, widget-grid | Scope under `.app--moonshot-mockup .ms-page`; dark tokens |
| 6 Chart mount | `mountChart`, `enhancePage`, `app.js` rAF hook | Wire to `NR2MoonshotUI`; use `data-nr2-chart-host` |

Raw Moonshot output: `docs/MOONSHOT_MOCKUP_FIX_COMPARISON_2026-07-08.md` (Issues 1–3), `docs/MOONSHOT_MOCKUP_FIX_PART3_2026-07-08.md` (Issues 4–6).

---

## 8. Recommended next action

**Start Commit 1 + Commit 2 in parallel:**
- Operator runs import sync and verifies export files (Phase 0).
- Developer flattens `renderQuickbooks()` (Commit 2) — pure layout fix, no data dependency.

Then Commit 3 → 4 → 5 → 6 in order.

**Estimated effort:** 6 focused commits · ~3–5 working sessions for solo operator/developer.

---

## 9. Verdict

| Reviewer | Verdict |
|----------|---------|
| **Automated audit** | Structural class parity PASS; data and layout FAIL |
| **Moonshot AI** | CONDITIONAL — correct diagnosis; reorder QB layout to P0; adapt code to NR2 |
| **This plan** | **APPROVE for implementation** — 6 commits, clear acceptance, mockup gallery sign-off |

The program is one data refresh and one layout commit away from stopping the “broken / empty” operator experience. Full mockup parity requires Commits 4–6.
