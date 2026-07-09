# Moonshot Full Capacity Consultation

**At:** 2026-07-08T01:10:32.679297+00:00
**Build:** hal-10062
**Status:** ok

---



# Verdict
**PHASED BUILD REQUIRED** — The hal-10062 foundation is architecturally sound and validators are green, but closing the eight known gaps spans visual systems, database schema expansion, SDK scheduling, and subpage chrome polish. A single monolithic commit risks validator regressions and data-binding failures. A five-phase build (hal-10063 through hal-10067/68) delivers maximum visible impact in Phase 1 while safely plumbing SoftDent and QuickBooks live data in subsequent stages.

## Executive Summary
Operator wants the program at “full capacity”: HAL must match the `page_mockups/hal.html` cyber-grid density and neon accent system; every widget in `moonshot-page-registry.js` must read from live SoftDent analytics DB tables or the QuickBooks SDK rather than import-cache placeholders; and all ten staff pages must share the same high-tech token/glow language. The path below keeps the existing PageCanvas architecture intact, hardens the analytics DB as the single source of truth for SoftDent, auto-triggers the QB SDK sync lifecycle, and lands workstation chrome parity last.

## Current State vs Operator Goal (gap table)

| Capability | Current State (hal-10062) | Operator Goal | Gap Severity |
|---|---|---|---|
| HAL Visual Fidelity | Functional HAL commands & hub poll; sparse widget grid | Pixel-match `hal.html`: cyber grid, pulsing status rings, dense mosaic, neon accents | **High** |
| SoftDent Live Data | Analytics DB probed by `softdent_practice_exports`; operatory still reads JSONL; not all widgets consume DB | All SoftDent widgets bound to analytics DB tables; no empty states | **High** |
| QuickBooks Live Data | `quickbooks_monthly_sync.py` writes `quickbooks_profit_loss_summary`; UI depends on cache freshness | Auto-sync on stale data; expense breakdown & EBITDA fully calculated | **Medium** |
| Widget Empty-State Resilience | Many widgets show “Awaiting import” when cache is cold | Show last-known data with amber staleness badge; never blank | **Medium** |
| Staff Subpage Design | 10/10 mock parity per audit; some pages lack glow/chart polish | Every subpage matches `hal.html`/`financial.html` high-tech bar | **Medium** |
| Workstation 8766 Chrome | CSS bridge loaded | Full mockup chrome parity with 8765 | **Low** |
| HAL Command Context | Chips wired to `NR2_FLAGS.hal_commands` | Full prompt-chip glow, stress-test panel, runtime health | **Medium** |

## HAL Command Center — Mock Parity Plan

### Layout & Visual Design (match page_mockups/hal.html)
- **Root container** in `site/hal/hal-page-canvas.js`: apply `.hal-cyber-grid` background pattern (`background-image: radial-gradient(...)`) and set `background-color: #181818`.
- **Status grid** in `site/hal/hal-page.js`: rebuild the top status bar to use `.hal-status-ring` (SVG circle with `stroke-dasharray` for health %), `.hal-status-pulse` (CSS `@keyframes` cyan shadow), and `.hal-consent-chip` for HIPAA consent state.
- **Typography & neon**: inject CSS custom properties `--neon-cyan`, `--neon-green`, `--neon-orange` into the HAL scope via `nr2-moonshot-mockup-chrome.js` or a scoped `site/css/hal-mockup-overrides.css`. All KPI values use `.text-glow`.
- **Drawer & chrome**: ensure `site/app.js` drawer toggle retains cyan accent border when HAL is active.

### Widget Grid & Subpage Navigation
- **Mosaic density**: change HAL grid layout in `hal-page-canvas.js` from sparse flex rows to `grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px;` with `.widget-mosaic-tile` cards.
- **HAL widget set**: `halAskHal`, `halImportHealth`, `practiceFinancialOverview`, `careDeliveryPerformance`, `quickbooksProfitLossDetail`, `officeManagerSurfaces`, `sidenotesProgram` must all render as dense tiles with header icons and sparkline/chart placeholders where specified by the mock.
- **Sub-nav**: `moonshot-page-registry.js` HAL entry gains a `navGroups` array (“Command”, “Health”, “Surfaces”) so `nr2-moonshot-mockup-chrome.js` renders a scrollable sub-nav rail inside the left sidebar.

### HAL-Specific Wiring (prompt chips, import health, sidenotes, work surfaces)
- **Prompt chips**: `bindHalAsk()` in `site/page-canvas-data.js` returns chip payloads; `hal-page.js` renders them as `<button class="hal-prompt-chip">` with `:hover { box-shadow: var(--neon-cyan); }`.
- **Import health**: `bindHalImportHealth()` queries `/api/hub/status` and `import-manifest.json` to populate the `.hal-health-ring` dataset (`data-health-score`, `data-last-sync`). Empty state shows last sync timestamp in amber if older than 1 hour.
- **Sidenotes**: `sidenotesProgram` widget uses `sidenotes-office-fallback.js` but upgrades badges to `.badge-live` (green pulse) vs `.badge-offline` (red) matching mock styling.
- **Work surfaces**: `officeManagerSurfaces` in HAL context surfaces the same surface-switcher used on the Office Manager page, rendered as a compact `.surface-grid` tile.

## Staff Pages — Subpages, Layout & High-Tech Design

### Per-Page Mockup Delta (financial, softdent, quickbooks, ar, claims, documents, office-manager, taxes, narratives, library)
| Page | Mock Reference | Delta to Close |
|---|---|---|
| **Financial** | `financial.html` | `.kpi-glow-card` borders; `financialProductionTrend` sparkline mounted via `enhanceCanvasCharts()`; `payerMixAndCollections` donut chart dark-grid polish. |
| **SoftDent** | `softdent.html` | `careDeliveryPerformance` funnel stage glow; `softdentOperatoryGrid` dense chair tiles (4×2) with status dots; `softdentArAging` table row hover glow. |
| **QuickBooks** | `quickbooks.html` | `quickbooksProfitLossDetail` line chart with cyan glow line; `quickbooksExpenseBreakdown` treemap/bar with neon segment borders; `ebitdaNormalization` card orange accent. |
| **A/R** | `ar.html` (implied) | `arAgingAndCollections` heatmap cell glow; `arOutstandingClaims` list with aging badges. |
| **Claims** | `claims.html` (implied) | `claimsPipeline` horizontal stage pipeline with neon active step. |
| **Documents** | `documents.html` (implied) | `documentIntakeQueue` filmstrip density; `documentPreview` pane with dark chrome; `periodCloseAndPosting` checklist glow on pending items. |
| **Office Manager** | `office-manager.html` (implied) | `officeManagerPriorities` priority matrix; `officeManagerSurfaces` large-format surface cards. |
| **Taxes** | `taxes.html` (implied) | High-tech data-table styling; neon row highlights for deadline proximity. |
| **Narratives** | `narratives.html` (implied) | `narrativeWorkflow` kanban lanes with status neon headers. |
| **Library** | `library.html` (implied) | `documentLibrary` card grid with hover lift + glow border. |

### Shared Design System Upgrades (tokens, glow, animations, chart polish)
- **Tokens**: add to `nr2-moonshot-mockup-chrome.js` style injection (or `site/css/design-tokens.css`):
  - `--ms-bg-deep: #181818`
  - `--ms-glow-cyan: 0 0 8px rgba(6,182,212,0.6)`
  - `--ms-glow-green: 0 0 8px rgba(34,197,94,0.6)`
  - `--ms-glow-orange: 0 0 8px rgba(249,115,22,0.6)`
- **Glow utility**: `.widget-glow-border` class applied by `page-canvas.js` renderer on all widgets when `data-theme="moonshot"`.
- **Animations**: `.pulse-ring`, `.scanline-overlay` for HAL; `.widget-mount-glow` fade-in for staff pages.
- **Chart polish**: `site/charts/chart-practice-pulse.js` and siblings updated to draw dark grid lines (`rgba(255,255,255,0.06)`), cyan line shadows, and transparent fills.

## Widget Wiring Matrix

### Table: widgetKey → data binder → import dataset / DB table → empty-state behavior

| widgetKey | Binder (page-canvas-data.js) | Source (DB / manifest) | Empty-State Behavior |
|---|---|---|---|
| `practiceFinancialOverview` | `bindFinancialOverview()` | `quickbooks_profit_loss_summary` + `softdent.collections` | Last-known KPIs with amber stale badge; never blank. |
| `financialProductionTrend` | `bindProductionTrend()` | `softdent_practice_exports.collections` (analytics DB) | 90-day sparkline from DB; fallback to flat line. |
| `payerMixAndCollections` | `bindPayerMix()` | `softdent.payer_mix` (manifest → DB table) | Donut from aggregated buckets; stale badge if >24h. |
| `providerPerformance` | `bindProviderPerformance()` | `softdent_practice_exports.provider_performance` | Bar chart by provider; empty = “No production this period”. |
| `careDeliveryPerformance` | `bindCareDelivery()` | `softdent_practice_exports.case_acceptance` | 4-stage funnel percentages; glow active stage. |
| `softdentArAging` | `bindArAging()` | `softdent.accountAging` (analytics DB) | Aging buckets table; 0-30/31-60/61-90/90+. |
| `softdentResponsibility` | `bindResponsibility()` | `softdent.accountAging` (responsibility bucket) | Donut: patient vs insurance vs other. |
| `newPatients` | `bindNewPatients()` | `softdent_practice_exports.new_patients` | KPI tile with trend arrow vs prior period. |
| `treatmentPlanSummary` | `bindTreatmentPlans()` | `softdent_practice_exports.treatment_plans` | Total presented / accepted $; list top 5. |
| `caseAcceptance` | `bindCaseAcceptance()` | `softdent_practice_exports.case_acceptance` | % tile with mini sparkline. |
| `hygieneRecall` | `bindHygieneRecall()` | `softdent_practice_exports.hygiene_recall` | Gauge: due / scheduled / completed. |
| `softdentOperatoryGrid` | `bindOperatoryGrid()` | `operatory_schedule` (analytics DB) | 4×2 chair grid; color dot by status. |
| `quickbooksProfitLossDetail` | `bindQbPnl()` | `quickbooks_profit_loss_summary`| 300s | Row-level P&L detail with class/location segmentation |

## 4. Data Contracts & Type Safety

All QuickBooks-bound widgets share a strict type contract to prevent drift between the API surface and the UI.

### 4.1 Core Interfaces
```typescript
interface ProfitLossSummary {
  reportHeader: {
    startDate: string; // ISO-8601
    endDate: string;
    currency: string;
  };
  rows: PnlRow[];
  summary: {
    totalIncome: Decimal;
    totalExpenses: Decimal;
    netIncome: Decimal;
  };
}

interface PnlRow {
  id: string;
  accountName: string;
  accountId: string;
  amount: Decimal;
  class?: string;
  location?: string;
  rowType: 'header' | 'section' | 'detail' | 'summary';
}
```

### 4.2 Runtime Validation
- **Zod schema** `QuickBooksPnlSchema` gates every inbound payload.
- Rejections trigger `QB_DATA_SHAPE_MISMATCH` Sentry events with a sanitized payload hash.

### 4.3 Error Response Shape
```typescript
type QbApiError = {
  code: 'AUTH_EXPIRED' | 'RATE_LIMITED' | 'REPORT_NOT_READY' | 'UNKNOWN';
  retryable: boolean;
  estimatedRetryAfter?: number;
};
```

## 5. Mount Lifecycle & Binding Semantics

Each widget exports a single binding function that satisfies the `WidgetBinding<TProps, TData>` interface.

### 5.1 `bindQbPnl()` Specification
- **Signature:** `(containerRef: HTMLElement, props: PnlWidgetProps) => BindingHandle`
- **Responsibilities:**
  1. Instantiate a dedicated `AbortController` scoped to the container.
  2. Dispatch `qb/pnl-request` telemetry event with `correlationId`.
  3. Call `GET /api/v1/integrations/quickbooks/reports/profit-loss` with `props.dateRange` and `props.groupBy`.
  4. Hydrate the React root inside `containerRef` only after schema validation passes.
  5. Return a `BindingHandle` containing `destroy()` and `refresh()` methods.

### 5.2 Cleanup Guarantees
- `destroy()` must:
  - Call `abortController.abort()`.
  - Unmount the React root (React 18 `root.unmount()`).
  - Release any IntersectionObserver or ResizeObserver handles.
- Invoked automatically by the shell on route change or widget eviction from the viewport pool.

## 6. Error Boundaries & Resilience Patterns

### 6.1 Widget-Level Error Boundary
- Every mount target is wrapped in `<QbWidgetErrorBoundary>`.
- Catches React render errors and binding initialization errors.
- Fallback UI: inline card with error code, "Retry" button, and link to QB reconnect flow.

### 6.2 Network Resilience
- **Retry policy:** 3 attempts with exponential backoff (1s, 2s, 4s) for `5xx` and network timeouts.
- **Rate limiting:** On `429`, read `Retry-After` header and pause the binding’s scheduler.
- **Auth failure:** If `AUTH_EXPIRED`, emit `qb:auth-required` global event so the top-bar auth widget can trigger re-OAuth without unmounting the dashboard.

### 6.3 Degraded Modes
| Failure Mode | Fallback |
|---|---|
| Detail API fails but Summary succeeds | Render summary card with “Detail unavailable” badge |
| Both fail | Show empty state with QB reconnect CTA |
| Partial row corruption | Render healthy rows; log corrupted row IDs |

## 7. Cache, Sync & Performance Budget

### 7.1 Server-State Cache
- **Layer:** TanStack Query (React Query) via the shared `useQbReport` hook.
- **Key:** `['qb','profit-loss', realmId, startDate, endDate, groupBy]`.
- **TTL:** `staleTime: 5 * 60 * 1000` (5 min).
- **Background refetch:** Enabled on window focus and network reconnect.

### 7.2 Client-Side Memoization
- `bindQbPnl()` receives a `comparisonFn` prop (default deep-equal) to prevent re-mounts when parent filters change cosmetically.

### 7.3 Performance Budget
| Metric | Budget | Enforcement |
|---|---|---|
| First widget paint | < 180 ms | Lighthouse `render` audit |
| JS bundle per widget | < 45 kB gzip | `bundlesize` CI gate |
| API response to render | < 300 ms | Datadog RUM custom metric |

## 8. Access Control & Feature Flags

### 8.1 OAuth Scope Matrix
| Scope | Widget Impact | Enforcement |
|---|---|---|
| `com.intuit.quickbooks.accounting` | Required for all QB widgets | Backend 403 if missing |
| `com.intuit.quickbooks.accounting.reports` | Required for P&L detail | Checked at binding time |

### 8.2 Feature Flags
- `dashboard-qb-pnl-detail`: Master kill-switch for the detail widget.
- `dashboard-qb-class-location`: Enables class/location column rendering.
- Evaluated via LaunchDarkly in the shell; props passed down as `FeatureContext`.

### 8.3 RBAC
- **Admin / Accountant:** Full read + export.
- **Viewer:** Read-only, export button hidden via `usePermissions()`.
- **External Auditor:** Time-boxed access; binding checks `accessExpiresAt` before each fetch.

## 9. Testing Strategy

### 9.1 Unit Tests (Jest)
- `bindQbPnl()`: Verify abort semantics, telemetry dispatch, and correct query-key formation.
- Zod schema: Fuzz-test with 1,000 generated QB payloads.

### 9.2 Integration Tests (RTL + MSW)
- Render widget shell with mock MSW handler returning `ProfitLossSummary`.
- Assert row count, sort behavior, and error boundary trigger on `500`.
- Simulate auth expiry and verify `qb:auth-required` event bubble.

### 9.3 End-to-End (Playwright)
- **Flow:** Connect QB sandbox → navigate to Dashboard → assert P&L widget renders > 0 rows.
- **Auth failure path:** Expire the session cookie → assert reconnect banner appears.
- **Performance:** Capture LCP and CLS for the widget container in a clean profile.

### 9.4 Contract Tests
- Pact verification between frontend `GET /api/v1/integrations/quickbooks/reports/profit-loss` consumer and backend provider on every CI build.

## 10. First Commit Slice

The first commit introduces the widget scaffold, binding contract, and mock-backed story. It does **not** call live QuickBooks endpoints.

### 10.1 Scope
1. **New Files**
   - `src/widgets/quickbooks/ProfitLossDetail/`
     - `index.ts` — public export
     - `bindQbPnl.ts` — binding function with mocked `Promise.resolve(PNL_MOCK)`
     - `ProfitLossDetail.tsx` — presentational component
     - `types.ts` — shared interfaces
     - `ProfitLossDetail.test.tsx` — RTL tests against mocked binding
   - `src/components/QbWidgetErrorBoundary.tsx` — reusable error boundary
2. **Modified Files**
   - `src/widgetRegistry.ts` — register `quickbooksProfitLossDetail` key
   - `src/mocks/handlers.ts` — add MSW handler for P&L detail

### 10.2 Acceptance Criteria
- [ ] `bindQbPnl()` mounts the component into a provided DOM node and unmounts cleanly on `destroy()`.
- [ ] Widget renders 5 mock rows with correct currency formatting.
- [ ] Error boundary renders fallback when mock binding rejects.
- [ ] CI passes: lint, type-check, unit tests, and bundle-size gate (< 45 kB).
- [ ] No live QB API keys or real network requests are invoked.

### 10.3 Rollback Plan
- Feature flag `dashboard-qb-pnl-detail` defaults to `false` in production.
- If issues arise, disable the flag; the registry skips mounting and renders a null fallback.
- Database: no migrations required.

### 10.4 Merge Checklist
- [ ] PR reviewed by **Platform** and **Integrations** teams.
- [ ] Storybook story published for UX review.
- [ ] Datadog RUM custom metric `widget.qb_pnl_detail.first_paint` is defined (no-op in this slice).
- [ ] Documentation: update `WIDGET_CATALOG.md` with mount contract and props table.

Below is the complete continuation from the `quickbooksProfitLossDetail` row through deployment hardening.  
All keys, binders, Bottle routes, and file references are concrete to the NR2 plain-JS / Bottle / SQLite stack.

---

## 1. Widget Wiring Matrix (Complete)

| Widget Key | JS Binder (`hal-page.js`) | Bottle Route | SQLite Source / SQL View | Refresh | Phase |
|---|---|---|---|---|---|
| **QuickBooks** |
| `quickbooksProfitLossDetail` | `bindQbPnl()` | `GET /api/qb/profit_loss_summary` | `qb_profit_loss` (monthly, class-aware) | 30 min | *finish* |
| `quickbooksBalanceSheetSummary` | `bindQbBs()` | `GET /api/qb/balance_sheet_summary` | `qb_balance_sheet` (assets/liab/equity roll-up) | 1 h | hal-10064 |
| `quickbooksCashFlowTrend` | `bindQbCf()` | `GET /api/qb/cash_flow_trend` | `qb_cash_flow` (12-month rolling) | 1 h | hal-10064 |
| `quickbooksExpenseBreakdown` | `bindQbExp()` | `GET /api/qb/expense_breakdown` | `qb_expenses_by_account` | 30 min | hal-10064 |
| `quickbooksRevenueByService` | `bindQbRevSvc()` | `GET /api/qb/revenue_by_service` | `qb_revenue_by_item` | 30 min | hal-10064 |
| `quickbooksMonthlyRevenue` | `bindQbMoRev()` | `GET /api/qb/monthly_revenue` | `qb_monthly_revenue` | 1 h | hal-10064 |
| `quickbooksNetIncomeSummary` | `bindQbNi()` | `GET /api/qb/net_income` | `qb_net_income` | 1 h | hal-10064 |
| `quickbooksApAging` | `bindQbAp()` | `GET /api/qb/ap_aging` | `qb_ap_aging` | 2 h | hal-10065 |
| `quickbooksArAging` | `bindQbAr()` | `GET /api/qb/ar_aging` | `qb_ar_aging` | 2 h | hal-10065 |
| `quickbooksCreditCardBalances` | `bindQbCc()` | `GET /api/qb/cc_balances` | `qb_cc_balances` | 4 h | hal-10065 |
| **SoftDent** |
| `softdentProductionDaily` | `bindSdProd()` | `GET /api/sd/production_daily` | `sd_production_daily` | 15 min | hal-10063 |
| `softdentCollectionsDaily` | `bindSdColl()` | `GET /api/sd/collections_daily` | `sd_collections_daily` | 15 min | hal-10063 |
| `softdentAgingReceivables` | `bindSdAr()` | `GET /api/sd/ar_aging` | `sd_ar_aging` | 1 h | hal-10063 |
| `softdentNewPatientsMTD` | `bindSdNewPt()` | `GET /api/sd/new_patients` | `sd_new_patients` | 30 min | hal-10063 |
| `softdentAppointmentsSnapshot` | `bindSdAppt()` | `GET /api/sd/appointments_today` | `sd_appointments` | 5 min | hal-10063 |
| `softdentClaimsOutstanding` | `bindSdClaims()` | `GET /api/sd/claims_outstanding` | `sd_claims` | 30 min | hal-10064 |
| `softdentProviderProduction` | `bindSdProvProd()` | `GET /api/sd/provider_production` | `sd_provider_production` | 1 h | hal-10064 |
| `softdentAdjustmentLog` | `bindSdAdj()` | `GET /api/sd/adjustment_log` | `sd_adjustments` | 30 min | hal-10064 |
| `softdentPatientRetention` | `bindSdRet()` | `GET /api/sd/patient_retention` | `sd_patients` (cohort view) | 24 h | hal-10065 |
| **NR2 Cross-Analytics** |
| `nr2ProductionReconciliation` | `bindNr2Recon()` | `GET /api/nr2/reconciliation` | `nr2_recon_gap` (QB rev − SD prod) | 30 min | hal-10065 |
| `nr2CollectionLag` | `bindNr2Lag()` | `GET /api/nr2/collection_lag` | `nr2_collection_lag` (days) | 1 h | hal-10066 |
| `nr2GoalScorecard` | `bindNr2Goals()` | `GET /api/nr2/goals` | `nr2_goals` + live actuals | 15 min | hal-10066 |
| `nr2KpiRibbon` | `bindNr2Kpi()` | `GET /api/nr2/kpi_ribbon` | `nr2_kpi_materialized` | 5 min | hal-10066 |
| `nr2AlertTicker` | `bindNr2Alerts()` | `GET /api/nr2/alerts` | `nr2_alerts` (exceptions) | 1 min | hal-10066 |
| `nr2ProviderCompensationWidget` | `bindNr2Comp()` | `GET /api/nr2/provider_comp` | `nr2_provider_comp` | 1 h | hal-10067 |
| `nr2MonthlyTrendCombo` | `bindNr2Trend()` | `GET /api/nr2/monthly_trend` | `nr2_monthly_trend` (24-mo) | 30 min | hal-10067 |

---

## 2. Widgets Currently Stubbed

All widgets below return **HAL mock parity JSON** today (shape-identical to live targets, sourced from `halMockStore` in `hal-page.js`):

- **QuickBooks:** `quickbooksBalanceSheetSummary`, `quickbooksCashFlowTrend`, `quickbooksExpenseBreakdown`, `quickbooksRevenueByService`, `quickbooksApAging`, `quickbooksArAging`, `quickbooksMonthlyRevenue`, `quickbooksNetIncomeSummary`, `quickbooksCreditCardBalances`
- **SoftDent:** `softdentProductionDaily`, `softdentCollectionsDaily`, `softdentAgingReceivables`, `softdentNewPatientsMTD`, `softdentAppointmentsSnapshot`, `softdentClaimsOutstanding`, `softdentProviderProduction`, `softdentAdjustmentLog`, `softdentPatientRetention`
- **NR2 Analytics:** `nr2ProductionReconciliation`, `nr2CollectionLag`, `nr2GoalScorecard`, `nr2KpiRibbon`, `nr2AlertTicker`, `nr2ProviderCompensationWidget`, `nr2MonthlyTrendCombo`

*Note:* `quickbooksProfitLossDetail` is partially wired; its binder exists but the route currently falls back to mock on >30-day ranges.

---

## 3. SoftDent Full Database Access Plan

**Objective:** Replace all SoftDent stubs with live read-only data without touching the practice management UI.

| Layer | Implementation | Detail |
|---|---|---|
| **Transport** | ODBC read-only DSN **preferred**; CSV hot-folder fallback | Use `pyodbc` in `softdent_practice_exports.py`. If SoftDent runs SQL Anywhere/Advantage, install native 64-bit driver on the NR2 host. |
| **Extract** | `softdent_practice_exports.py` | Add `extract_production(date)`, `extract_collections(date)`, `extract_ar_aging()`, `extract_appointments(range)`, `extract_new_patients(month)`, `extract_claims()`, `extract_provider_production()`, `extract_adjustments()`. Each returns `list[dict]`. |
| **Load** | SQLite analytics DB | Upsert into `sd_*` tables with `synced_at` timestamps. Use `INSERT OR REPLACE` keyed by natural composite keys (e.g., `trans_date` + `provider_id` + `patient_id`). |
| **Schema additions** | `analytics.db` | `sd_production_daily`, `sd