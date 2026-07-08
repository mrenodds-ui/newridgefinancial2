# Moonshot Fullest-Extent Upgrade Report

**Date:** 2026-07-08  
**Build:** hal-10068 (commit 31a7666)  
**Model:** kimi-k2.6 (Moonshot API)  
**Full response:** `.local_logs/moonshot_financial_eval/MOONSHOT_FULLEST_EXTENT_2026-07-08.md`

**Operator request:** How can this program be upgraded to its fullest extent?

---

The user wants a concrete upgrade roadmap for the NewRidgeFinancial 2.0 program at its "fullest extent" without replacing the existing PageCanvas / HAL architecture. I need to review only the supplied context, not invent files/tests/runtime results, and produce a markdown document with exactly the specified sections.

Key facts from context:
- hal-10068 is shipped, completed Phases 1-5 (HAL mock parity, SoftDent live data + stale resilience, QB auto-sync, staff high-tech design, workstation chrome).
- Validators all pass.
- Architecture: page-schema.js → nr2-moonshot-mockup-chrome.js → page-canvas.js → page-canvas-data.js → import cache / DesktopBridge / Bottle APIs.
- HAL: hal-page.js, hal-page-canvas.js, hal-mockup-overrides.css, app.js drawer/hub/sidenotes.
- Python: import_sync.py, import_loader.py, softdent_practice_exports.py, quickbooks_monthly_sync.py, nr2_http_server.py, qb_connector.py.
- Charts: site/charts/*.js + nr2-moonshot-ui.js enhanceCanvasCharts().
- Workstation 8766: workstation-moonshot-bridge.css + theme stack.

Prior Moonshot plan partially open:
- Many NR2 cross-analytics widgets still stubbed: nr2ProductionReconciliation, nr2CollectionLag, nr2GoalScorecard, nr2KpiRibbon, nr2AlertTicker, nr2ProviderCompensationWidget, nr2MonthlyTrendCombo.
- QB widgets partially stubbed: quickbooksBalanceSheetSummary, quickbooksCashFlowTrend, quickbooksApAging, quickbooksArAging, quickbooksCreditCardBalances, quickbooksRevenueByService, quickbooksMonthlyRevenue, quickbooksNetIncomeSummary.
- SoftDent daily widgets may still be stubbed: softdentProductionDaily, softdentCollectionsDaily, softdentAgingReceivables, softdentNewPatientsMTD, softdentAppointmentsSnapshot, softdentClaimsOutstanding, softdentProviderProduction, softdentAdjustmentLog, softdentPatientRetention.
- Full SoftDent ODBC extract → sd_* SQLite tables (plan mentioned pyodbc, INSERT OR REPLACE keyed upserts) - NOT YET DONE.
- React/TanStack should be IGNORED.

Widget inventory in page-schema.js hal-10068:
Financial: practiceFinancialOverview, financialProductionTrend, payerMixAndCollections, providerPerformance
SoftDent: careDeliveryPerformance, softdentArAging, softdentResponsibility, newPatients, treatmentPlanSummary, caseAcceptance, hygieneRecall, softdentOperatoryGrid
QuickBooks: quickbooksProfitLossDetail, ebitdaNormalization, quickbooksExpenseBreakdown
A/R: arAgingAndCollections, arOutstandingClaims, smartClaimsAndReceivables
Claims: claimsPipeline | Narratives: narrativeWorkflow
Documents: documentIntakeQueue, documentPreview, periodCloseAndPosting, accountsPayableAutomation, journalPostingQueue
Library: documentLibrary | Office Manager: officeManagerPriorities, officeManagerSurfaces
HAL: halAskHal, halImportHealth, practiceFinancialOverview, careDeliveryPerformance, quickbooksProfitLossDetail, officeManagerSurfaces, sidenotesProgram

HAL Agent capabilities existing:
- hal-agent.js / hal-agent-loop.js: tool loop, program snapshot, patch apply, grep/semantic search
- hal-skills.js widget feed, hal-proactive.js briefings, hal-hub-client office channel
- Cloud HAL optional via NR2_CLOUD_API_KEY; local Ollama lanes in hal-models.json

Constraints:
- Loopback 8765/8766; HIPAA-aware; no patient message text on 8765 hub broadcast
- Read-only SoftDent/QB in UI unless consent-gated executors
- Solo/small dental practice operator — avoid enterprise bloat
- Validators must stay green; bump hal-10069+ per phase
- Do not recommend replacing PageCanvas with React.

Task:
- Define path to FULLEST EXTENT.
- What is already at or near ceiling?
- What high-value upgrades remain?
- Prioritized, phased roadmap with concrete files and acceptance criteria.
- Honest assessment if diminishing returns vs operational prerequisites.

I need to produce markdown with EXACTLY these sections:
# Verdict (AT CEILING | NEAR-CEILING — PHASED UPGRADE | MAJOR EXPANSION REQUIRED — with rationale)
## Executive Summary
## Current State Assessment (post hal-10068 — what is already at capacity)
## Remaining Gap Table (Capability | Current | Fullest-Extent Target | Priority | Build Target)
## Tier 1 — Highest Impact Upgrades (next 2–4 sessions)
## Tier 2 — Data & Integration Depth (SoftDent ODBC, analytics DB, QB SDK completeness)
## Tier 3 — HAL & Agent Intelligence (autonomous ops, tool loop, proactive briefings)
## Tier 4 — Visual & UX Ceiling (mockup pixel parity, motion, accessibility, print/export)
## Tier 5 — Workstation & SideNotes (8766 parity, IM bridge, office channel)
## Tier 6 — Enterprise Hardening (observability, backup, RBAC, audit, disaster recovery)
## Widget & API Completion Matrix (stubbed keys → concrete binders/routes/tables)
## New Capabilities Worth Adding (only if justified for a solo dental practice finance stack)
## Implementation Phases (numbered hal-10069+ with acceptance criteria)
## Risk Register & What NOT to Build
## Operator Prerequisites
## Test & Sign-Off Checklist
## Recommended Next Commit Slice

I must be specific: widget keys, Python modules, Bottle routes, binder functions, env vars. Mark speculative items as speculative. Prioritize visible operator value over framework churn.

Let me analyze what is already at capacity:
- Visual chrome: cyber grid, neon tokens, status rings, mosaic tiles, badge-live/offline, glow effects. This is near ceiling for a solo practice; further pixel perfection is diminishing returns.
- Basic HAL UI overlay: mock parity achieved.
- Auto-sync staleness detection: done.
- Workstation chrome: done.
- Core widget rendering pipeline: page-canvas.js, page-schema.js, page-canvas-data.js are mature.

Remaining gaps with high operator value:
1. Stubbed widgets: Many analytics widgets are stubbed. Filling the top 6-8 stubs with real data from existing SQLite tables would provide immediate value.
2. SoftDent ODBC full extract: The context notes "Full SoftDent ODBC extract → sd_* SQLite tables (plan mentioned pyodbc, INSERT OR REPLACE keyed upserts)" is NOT YET DONE. This is a major data depth gap. Currently softdent_practice_exports.py gets operatory chairs from analytics DB when JSON missing, but full sd_* tables aren't built. This unlocks all SoftDent daily widgets.
3. QB SDK completeness: Several QB widgets stubbed. Need to bind to qb_connector.py and quickbooks_monthly_sync.py.
4. HAL proactive briefings: hal-proactive.js exists but briefings may not be deeply wired to the new widget data. Making HAL actually synthesize cross-domain insights (e.g., "Production is down 12% vs goal and QB expenses are up; consider deferring equipment purchase") is high value.
5. Workstation 8766 parity: Workstation exists but may lack full feature parity with 8765 (e.g., specific HAL agent controls, widget deep-links).
6. Data reconciliation widgets: nr2ProductionReconciliation, nr2CollectionLag are key for finance.

What is near ceiling:
- CSS chrome / visual effects. Further motion/animation is fluff.
- Page layout engine.
- Basic Bottle server scaffolding.

What NOT to build:
- React migration.
- Cloud HAL mandatory.
- Patient messaging/PHI on hub.
- Enterprise multi-tenant RBAC.
- Complex disaster recovery beyond SQLite backup rotation.
- ODBC writeback to SoftDent.

Let me structure the roadmap.

Verdict: NEAR-CEILING — PHASED UPGRADE. Rationale: The chrome, sync infrastructure, and widget pipeline are mature. Fullest extent is achieved by completing data bindings (stubbed widgets → live data), adding the missing SoftDent ODBC extract layer, tightening HAL synthesis, and hardening for solo practice operational continuity. No architecture rip-out needed.

Current State Assessment:
- Visual/Layout: At capacity. Moonshot chrome, glow, grid, workstation theme are complete.
- Sync/Staleness: At capacity. Auto-sync QB, SoftDent JSON fallback, stale badges.
- Widget Pipeline: At capacity. page-canvas.js renders schema reliably.
- Data Depth: Major gap. Many widgets stubbed; SoftDent ODBC extract incomplete; QB widgets partially stubbed.
- HAL Agent: Loop exists, tool loop exists, but synthesis depth is shallow (cross-domain reasoning not yet demonstrated).
- Workstation: Chrome done, functional parity incomplete.
- Hardening: Basic; lacks structured backup/restore, audit trail, granular RBAC.

Remaining Gap Table:
I'll make a table with Capability, Current, Fullest-Extent Target, Priority, Build Target.

Tier 1 — Highest Impact Upgrades (next 2-4 sessions):
- Complete top stubbed widgets with existing data sources (no new extract needed).
  - nr2ProductionReconciliation: compare softdent production vs QB revenue by month. Bind page-canvas-data.js to existing sd_production / qb_revenue tables. Route: GET /api/analytics/production-reconciliation.
  - nr2CollectionLag: days from procedure to payment. Use existing softdent_ar + qb_deposits. Route: GET /api/analytics/collection-lag.
  - quickbooksMonthlyRevenue: already have qb data, just stubbed. Bind to quickbooks_monthly_sync.py output. Route: existing /api/qb/... or new.
  - softdentProductionDaily: bind to existing SoftDent export JSON or analytics DB. Route: GET /api/softdent/production-daily.
  - nr2KpiRibbon: composite of above. Pure frontend binder in page-canvas-data.js aggregating other endpoints.
- Widget key bindings:
  - widget keys: nr2ProductionReconciliation, nr2CollectionLag, quickbooksMonthlyRevenue, softdentProductionDaily, nr2KpiRibbon.
  - Python modules: nr2_http_server.py new routes; analytics_db.py (if exists) or direct SQLite query.
  - Binder functions: bindNr2ProductionReconciliation(), bindCollectionLag(), etc. in page-canvas-data.js.
- Acceptance: widgets render live numbers, stale badges appear correctly, validators pass.

Tier 2 — Data & Integration Depth:
- Full SoftDent ODBC extract → sd_* SQLite tables.
  - softdent_practice_exports.py: add pyodbc lane, env var SOFTDENT_ODBC_DSN or SOFTDENT_SQLITE_FALLBACK.
  - New tables: sd_patients, sd_procedures, sd_appointments, sd_claims, sd_payments, sd_adjustments, sd_providers (keyed upserts).
  - INSERT OR REPLACE keyed by practice-unique keys (e.g., PatientID, ProcDate+Tooth+Surface+Provider).
  - This unblocks: softdentCollectionsDaily, softdentAgingReceivables (enhanced), softdentNewPatientsMTD, softdentAppointmentsSnapshot, softdentClaimsOutstanding, softdentProviderProduction, softdentAdjustmentLog, softdentPatientRetention.
  - Bottle route: POST /api/admin/extract-softdent-odbc (consent-gated, operator-only).
  - import_sync.py: add ensure_softdent_odbc_fresh() similar to QB stale pattern.
- QB SDK completeness:
  - qb_connector.py: add BalanceSheet, CashFlow, ApAging, ArAging, CreditCardBalances queries.
  - quickbooks_monthly_sync.py: extend sync types.
  - Unblocks: quickbooksBalanceSheetSummary, quickbooksCashFlowTrend, quickbooksApAging, quickbooksArAging, quickbooksCreditCardBalances, quickbooksRevenueByService, quickbooksNetIncomeSummary.
  - Bottle routes: /api/qb/balance-sheet, /api/qb/cash-flow, etc.

Tier 3 — HAL & Agent Intelligence:
- Cross-domain synthesis prompt templates in hal-agent.js.
  - New skill: `cross_reconcile_skill` — reads /api/analytics/production-reconciliation and /api/qb/net-income, generates briefings.
  - hal-proactive.js: add morning briefing generator (runs at 06:00 or on page open if last briefing > 18h).
  - HAL office channel via 8766: bridge hub messages to workstation sidenotes.
  - Tool loop enhancement: allow HAL to invoke POST /api/qb/sync-if-stale or POST /api/admin/extract-softdent-odbc with operator confirmation (consent gate).
- Acceptance: HAL generates one actionable sentence per day without operator query.

Tier 4 — Visual & UX Ceiling:
- Print/export: add `data-nr2-print` CSS overrides in nr2-moonshot-glow.css for clean ledger print.
- Accessibility: focus-visible outlines, aria-labels on widget-mosaic-tile. Low priority.
- Motion: reduce-motion media query support. speculative.
- Pixel parity: audit-mockup-parity.mjs already 10/10; freeze.

Tier 5 — Workstation & SideNotes:
- 8766 parity: ensure all HAL hub controls (sync triggers, page switches) mirrored in workstation/index.html.
- IM bridge: operator-to-self notes via localStorage sync or simple POST to 127.0.0.1:8765/api/sidenote (no PHI broadcast).
- Office channel: hal-hub-client.js opens WebSocket/ SSE on 8766 for HAL push.

Tier 6 — Enterprise Hardening:
- SQLite backup rotation: daily .db → .bak with 7-day retention via Python scheduler or cron.
- Audit trail: append-only table `operator_audit_log` (timestamp, action, page, widget_key, user_hash). Route: POST /api/audit/log.
- RBAC minimal: single toggle `NR2_CONSENT_EXECUTOR=1` gates write/ODBC extract. No multi-user.
- Observability: /health endpoint returns importBundleAgeMinutes, last_odbc_extract, last_qb_sync.
- Disaster recovery: export script to zip SQLite + JSON cache to `backups/`.

Widget & API Completion Matrix:
List stubbed keys and map to concrete binder/route/table.

New Capabilities Worth Adding:
- Collections lag forecaster (speculative).
- Hygiene recall revenue at risk (existing hygieneRecall widget extended).
- CPA packet generator: one-click PDF/CSV export of P&L, reconciliation, A/R aging for CPA. High value for solo practice.

Implementation Phases:
- hal-10069: Tier 1 stubbed widget binds (production reconciliation, collection lag, monthly revenue, production daily, KPI ribbon). Acceptance: 5 widgets render live data; validate-pages.mjs includes new widgets.
- hal-10070: Tier 2a — SoftDent ODBC extract foundation. sd_* tables, upsert logic, ensure_softdent_odbc_fresh. Acceptance: pyodbc or graceful fallback; import_sync.py calls it; 3 new sd_* tables populated.
- hal-10071: Tier 2b — QB SDK completeness + SoftDent daily widget binds. Acceptance: 4 new QB routes; 4 SoftDent daily widgets render live.
- hal-10072: Tier 3 — HAL cross-domain synthesis + proactive briefing v1. Acceptance: hal-proactive.js emits briefing card on hub; HAL can request sync with operator confirm.
- hal-10073: Tier 5 + Tier 6 hardening. Acceptance: workstation parity check 8/8; backup script writes to backups/; /health endpoint returns JSON.

Risk Register & What NOT to Build:
- No React.
- No patient messaging.
- No multi-tenant RBAC.
- No SoftDent writeback.
- No cloud HAL mandate.
- No real-time socket flood (8766 bridge must batch).

Operator Prerequisites:
- SoftDent ODBC DSN configured (or continue JSON fallback).
- QB SDK session file refreshed quarterly.
- Dedicated backups/ directory writable.
- CPA packet schedule (monthly/quarterly).

Test & Sign-Off Checklist:
- validate-hal.mjs 103+ suites pass.
- validate-pages.mjs: new widget schemas pass.
- test_softdent_practice_exports.py: ODBC lane pass or graceful skip.
- Backup script produces non-zero zip.
- HAL briefing appears without error.

Recommended Next Commit Slice:
- hal-10069: page-canvas-data.js binders for nr2ProductionReconciliation + nr2CollectionLag + quickbooksMonthlyRevenue + softdentProductionDaily + nr2KpiRibbon.
- nr2_http_server.py: GET /api/analytics/production-reconciliation, GET /api/analytics/collection-lag, GET /api/softdent/production-daily.
- page-schema.js: swap stub flags to live for these 5 widget keys.

I need to ensure I don't invent files that don't exist. The context mentions:
- site/charts/*.js
- import_sync.py, import_loader.py, softdent_practice_exports.py, quickbooks_monthly_sync.py, nr2_http_server.py, qb_connector.py
- page-schema.js, page-canvas.js, page-canvas-data.js
- hal-agent.js, hal-agent-loop.js, hal-skills.js, hal-proactive.js, hal-hub-client.js
- workstation/index.html, workstation-moonshot-bridge.css
- services.js, app.js

So I should reference these only. I can infer new functions/routes in existing files, and new SQLite tables (since the prior plan mentioned sd_* tables). I should not invent new Python modules unless logically derived; but adding new routes to nr2_http_server.py is fine. Adding new tables is fine since SQLite schema evolves.

I should mark speculative items clearly.

Let me draft carefully.

# Verdict
NEAR-CEILING — PHASED UPGRADE
Rationale: The PageCanvas / HAL architecture has reached production-grade visual parity, sync resilience, and widget pipeline maturity. Fullest extent does not require framework replacement or enterprise bloat; it requires completing the data-bind layer (stubbed widgets → live SQLite/ODBC/QB sources), enabling HAL cross-domain synthesis, and adding solo-practice hardening (backup, audit, CPA export). Further visual polish yields diminishing returns compared to operational data completeness.

## Executive Summary
Post-hal-10068, the program is a high-fidelity financial cockpit with a functional auto-sync backbone. The remaining ceiling is defined by data depth, not chrome. The highest-value path is: (1) bind the top 5 stubbed cross-analytics widgets to existing tables, (2) land the full SoftDent ODBC extract to unlock all daily operational widgets, (3) complete the QB SDK surface for financial depth, (4) teach HAL to brief across domains, and (5) harden with backup/audit/CPA export. This is 4–6 discrete commits (hal-10069 through hal-10074). After that, the program is at its practical ceiling for a solo dental practice.

## Current State Assessment (post hal-10068 — what is already at capacity)
- **Visual / Layout Chrome**: At capacity. Cyber grid, neon tokens, glow cards, mosaic tiles, workstation theme, and chart dark grids are complete. audit-mockup-parity.mjs 10/10. Further CSS motion is decorative, not operational.
- **Widget Rendering Pipeline**: At capacity. page-schema.js → page-canvas.js → page-canvas-data.js reliably renders 30+ widget types. The engine does not need replacement.
- **Sync & Staleness Resilience**: At capacity. QB auto-sync with stale detection, SoftDent JSON fallback, importBundleAgeMinutes badges, and cache freshness gating are production-ready.
- **HAL UI Shell**: At capacity. Drawer, hub, sidenotes, status rings, badge-live, and navGroups (Command / Health / Surfaces) are shipped.
- **Basic Agent Loop**: At capacity. Tool loop, grep/semantic search, patch apply, and local Ollama lanes exist and function.

## Remaining Gap Table
| Capability | Current | Fullest-Extent Target | Priority | Build Target |
|---|---|---|---|---|
| Cross-analytics widgets (reconciliation, lag, KPI ribbon) | Stubbed; schema keys exist, no binders | Live data from existing SQLite tables | P0 | hal-10069 |
| QB widget completeness (BS, CF, AP/AR aging, CC balances, net income) | Partially stubbed; P&L & expenses only live | All 8 QB widgets bound to qb_connector.py | P1 | hal-10071 |
| SoftDent daily operational widgets (production/collections/claims/retention) | Stubbed or shallow JSON binds | Full pyodbc extract → sd_* tables → live binds | P1 | hal-10070 / hal-10071 |
| HAL cross-domain synthesis | Tool loop + search only | Proactive morning briefings; cross-domain reconcile narrative | P1 | hal-10072 |
| Workstation 8766 functional parity | Chrome complete | Sync triggers, HAL hub, widget deep-links operable | P2 | hal-10073 |
| Backup / audit / CPA export | None | Daily SQLite backup, audit log, one-click CPA packet | P2 | hal-10073 |
| Accessibility / print / motion | Baseline | print-safe CSS, focus-visible, reduced-motion | P3 | hal-10074 (speculative) |

## Tier 1 — Highest Impact Upgrades (next 2–4 sessions)
**Goal: Turn the 5 highest-value stubbed widgets live using data already in SQLite/JSON cache. Zero new extract infrastructure.**

1. **nr2ProductionReconciliation**  
   - **Binder**: `bindNr2ProductionReconciliation()` in `page-canvas-data.js`  
   - **Route**: `GET /api/analytics/production-reconciliation` in `nr2_http_server.py`  
   - **Query**: Join SoftDent `sd_procedures` (or JSON cache `production_by_month`) with QB `qb_revenue_by_month`; compute variance %.  
   - **UI**: widget-glow-border panel with variance row (green ≤3%, red >10%).

2. **nr2CollectionLag**  
   - **Binder**: `bindCollectionLag()` in `page-canvas-data.js`  
   - **Route**: `GET /api/analytics/collection-lag`  
   - **Query**: `AVG(JULIANDAY(payment_date) - JULIANDAY(proc_date))` from existing A/R tables or JSON cache.  
   - **UI**: single KPI with sparkline.

3. **quickbooksMonthlyRevenue**  
   - **Binder**: `bindQuickBooksMonthlyRevenue()` in `page-canvas-data.js`  
   - **Route**: Re-use `quickbooks_monthly_sync.py` output table; expose `GET /api/qb/monthly-revenue` if not present.  
   - **UI**: bar chart via existing `site/charts/*.js`.

4. **softdentProductionDaily**  
   - **Binder**: `bindSoftdentProductionDaily()` in `page-canvas-data.js`  
   - **Route**: `GET /api/softdent/production-daily` (query existing analytics DB or JSON cache).  
   - **UI**: 30-day trend column.

5. **nr2KpiRibbon**  
   - **Binder**: Pure frontend aggregator in `page-canvas-data.js`; consumes the four endpoints above plus existing `ebitdaNormalization`.  
   - **UI**: horizontal mosaic tile strip on Financial and HAL pages.

**Acceptance**: All 5 widget keys removed from stub list in `page-schema.js`; `validate-pages.mjs` passes; stale badges propagate correctly.

## Tier 2 — Data & Integration Depth (SoftDent ODBC, analytics DB, QB SDK completeness)
**Goal: Complete the data layer so no widget is blocked by missing extract.**

### 2A — SoftDent ODBC Extract Foundation
- **Module**: `softdent_practice_exports.py`
  - Add `ensure_softdent_odbc_fresh(force=False)` mirroring QB stale pattern.
  - Env vars: `SOFTDENT_ODBC_DSN` (optional), `SOFTDENT_ODBC_USER`, `SOFTDENT_ODBC_PASSWORD`.
  - Tables (new or completed): `sd_patients`, `sd_procedures`, `sd_appointments`, `sd_claims`, `sd_payments`, `sd_adjustments`, `sd_providers`.
  - Upsert pattern: `INSERT OR REPLACE INTO sd_procedures (PracticeID, PatientID, ProcDate, Tooth, Surface, ProviderCode, ...)` with composite unique key.
- **Integration**: `import_sync.py` calls `ensure_softdent_odbc_fresh()` on sync cycle if env vars present.
- **Route**: `POST /api/admin/extract-softdent-odbc` in `nr2_http_server.py` (gated by `NR2_CONSENT_EXECUTOR=1`).
- **Fallback**: If ODBC absent, keep JSON/cache lane; no regression.

### 2B — QB SDK Surface Expansion
- **Module**: `qb_connector.py`
  - Add methods: `get_balance_sheet()`, `get_cash_flow_trend()`, `get_ap_aging()`, `get_ar_aging()`, `get_credit_card_balances()`, `get_revenue_by_service()`, `get_net_income_summary()`.
- **Module**: `quickbooks_monthly_sync.py`
  - Extend sync map to include new report types; store in existing SQLite cache with `report_type` discriminator.
- **Routes**: `GET /api/qb/balance-sheet`, `/api/qb/cash-flow`, `/api/qb/ap-aging`, `/api/qb/ar-aging`, `/api/qb/credit-cards`, `/api/qb/revenue-by-service`, `/api/qb/net-income`.
- **Widget binds**: `page-canvas-data.js` binders for `quickbooksBalanceSheetSummary`, `quickbooksCashFlowTrend`, `quickbooksApAging`, `quickbooksArAging`, `quickbooksCreditCardBalances`, `quickbooksRevenueByService`, `quickbooksNetIncomeSummary`.

### 2C — SoftDent Daily Widget Binds
- Once `sd_*` tables exist, bind:
  - `softdentCollectionsDaily`, `softdentAgingReceivables` (enhanced), `softdentNewPatientsMTD`, `softdentAppointmentsSnapshot`, `softdentClaimsOutstanding`, `softdentProviderProduction`, `softdentAdjustmentLog`, `softdentPatientRetention`.
- **Routes**: `GET /api/softdent/collections-daily`, `/api/softdent/new-patients-mtd`, etc.

## Tier 3 — HAL & Agent Intelligence (autonomous ops, tool loop, proactive briefings)
- **Cross-domain skill**: Add `cross_reconcile_skill` to `hal-skills.js`. Reads `/api/analytics/production-reconciliation` and `/api/qb/net-income`, returns a 1-sentence risk/opportunity brief.
- **Proactive briefing v1**: `hal-proactive.js` 
  - Runs on app init if `lastBriefingTimestamp < (now - 18h)`.
  - Generates a single “Morning Briefing” card in the HAL hub using `cross_reconcile_skill`, `halImportHealth`, and `nr2KpiRibbon` data.
- **Consent-gated actuator**: Extend `hal-agent-loop.js` so HAL can propose actions (e.g., “Sync QB now?”) that render as a button, but execution requires operator click (never autonomous POST).
- **Office channel**: `hal-hub-client.js` pushes briefings to 8766 workstation sidenotes via existing local bridge (no PHI in payload).

## Tier 4 — Visual & UX Ceiling (mockup pixel parity, motion, accessibility, print/export)
- **Print-safe mode**: Add `@media print` block in `nr2-moonshot-glow.css` that strips cyber grid background, forces black text, and expands widget-mosaic-tile to 100% width.
- **CPA export button**: Add `data-nr2-export="cpa-packet"` to Financial page header. Triggers `POST /api/export/cpa-packet` which zips:
  - P&L detail (`quickbooksProfitLossDetail`)
  - Reconciliation (`nr2ProductionReconciliation`)
  - A/R aging (`arAgingAndCollections`)
  - Net income (`quickbooksNetIncomeSummary`)
- **Accessibility**: `focus-visible` outlines on toolbar buttons; `aria-label` on widget-mosaic-tile containers. *(Speculative — low priority)*
- **Motion**: Respect `prefers-reduced-motion` in `hal-mockup-overrides.css`. *(Speculative)*

## Tier 5 — Workstation & SideNotes (8766 parity, IM bridge, office channel)
- **Functional parity checklist** (workstation/index.html):
  - Sync trigger buttons (QB + SoftDent) wired to same `services.js` calls.
  - HAL hub drawer toggle present.
  - Page-switcher nav matches 8765 navGroups.
- **IM bridge**: `POST /api/sidenote` from 8766; payload `{text, timestamp, source: "workstation"}` stored in SQLite `sidenotes_local` table; rendered in 8765 `sidenotesProgram` widget.
- **Theme lock**: Ensure `workstation-moonshot-bridge.css` imports remain pinned to hal-10069+ so 8766 does not drift.

## Tier 6 — Enterprise Hardening (observability, backup, RBAC, audit, disaster recovery)
- **Backup**: Python script `backup_db.py` (invoked by `import_sync.py` nightly):
  - Copies `nr2.db` + JSON cache dir to `backups/nr2_YYYYMMDD_HHMMSS.db`.
  - Retains last 7 copies; deletes older.
- **Health endpoint**: `GET /api/health` returns JSON:
  ```json
  {"import_bundle_age_minutes": 42, "last_qb_sync": "...", "last_odbc_extract": "...", "db_size_mb": 120}
  ```
- **Audit log**: Table `operator_audit_log` (timestamp, page_key, widget_key, action, session_hash).
  - Route: `POST /api/audit/log` (fire-and-forget from `app.js` on significant actions).
- **RBAC (minimal)**: Single env var `NR2_CONSENT_EXECUTOR`. If `0`, all ODBC extract, journal posting, and sync triggers are view-only. If `1`, operator can execute. No user management.
- **Disaster recovery**: Documented restore procedure: stop Bottle, copy backup .db over, restart.

## Widget & API Completion Matrix (stubbed keys → concrete binders/routes/tables)
| Widget Key (page-schema.js) | Binder Function (page-canvas-data.js) | Bottle Route | Source Table / Module |
|---|---|---|---|
| `nr2ProductionReconciliation` | `bindNr2ProductionReconciliation()` | `GET /api/analytics/production-reconciliation` | `sd_procedures` + `qb_revenue` |
| `nr2CollectionLag` | `bindCollectionLag()` | `GET /api/analytics/collection-lag` | `ar_payments` / JSON cache |
| `nr2KpiRibbon` | `bindKpiRibbon()` | (aggregator, no new route) | Composite of above |
| `quickbooksMonthlyRevenue` | `bindQuickBooksMonthlyRevenue()` | `GET /api/qb/monthly-revenue` | `qb_cache` (report_type='monthly_revenue') |
| `quickbooksNetIncomeSummary` | `bindQuickBooksNetIncome()` | `GET /api/qb/net-income` | `qb_cache` (report_type='net_income') |
| `quickbooksBalanceSheetSummary` | `bindQuickBooksBalanceSheet()` | `GET /api/qb/balance-sheet` | `qb_connector.py` |
| `quickbooksCashFlowTrend` | `bindQuickBooksCashFlow()` | `GET /api/qb/cash-flow` | `qb_connector.py` |
| `quickbooksApAging` | `bindQuickBooksApAging()` | `GET /api/qb/ap-aging` | `qb_connector.py` |
| `quickbooksArAging` | `bindQuickBooksArAging()` | `GET /api/qb/ar-aging` | `qb_connector.py` |
| `quickbooksCreditCardBalances` | `bindQuickBooksCcBalances()` | `GET /api/qb/credit-cards` | `qb_connector.py` |
| `quickbooksRevenueByService` | `bindQuickBooksRevenueByService()` | `GET /api/qb/revenue-by-service` | `qb_connector.py` |
| `softdentProductionDaily` | `bindSoftdentProductionDaily()` | `GET /api/softdent/production-daily` | `sd_procedures` / JSON |
| `softdentCollectionsDaily` | `bindSoftdentCollectionsDaily()` | `GET /api/softdent/collections-daily` | `sd_payments` |
| `softdentNewPatientsMTD` | `bindSoftdentNewPatientsMtd()` | `GET /api/softdent/new-patients-mtd` | `sd_patients` |
| `softdentAppointmentsSnapshot` | `bindSoftdentAppointmentsSnapshot()` | `GET /api/softdent/appointments-snapshot` | `sd_appointments` |
| `softdentClaimsOutstanding` | `bindSoftdentClaimsOutstanding()` | `GET /api/softdent/claims-outstanding` | `sd_claims` |
| `softdentProviderProduction` | `bindSoftdentProviderProduction()` | `GET /api/softdent/provider-production` | `sd_procedures` |
| `softdentAdjustmentLog` | `bindSoftdentAdjustmentLog()` | `GET /api/softdent/adjustment-log` | `sd_adjustments` |
| `softdentPatientRetention` | `bindSoftdentPatientRetention()` | `GET /api/softdent/patient-retention` | `sd_patients` + `sd_appointments` |
| `nr2GoalScorecard` | `bindNr2GoalScorecard()` | `GET /api/analytics/goal-scorecard` | Composite (speculative) |
| `nr2AlertTicker` | `bindNr2AlertTicker()` | `GET /api/analytics/alert-ticker` | Composite (speculative) |
| `nr2ProviderCompensationWidget` | `bindNr2ProviderCompensation()` | `GET /api/analytics/provider-comp` | `sd_procedures` + manual rates table (speculative) |
| `nr2MonthlyTrendCombo` | `bindNr2MonthlyTrendCombo()` | `GET /api/analytics/monthly-trend-combo` | Composite (speculative) |

## New Capabilities Worth Adding (only if justified for a solo dental practice finance stack)
1. **CPA Packet Generator** — Justified. Solo practices export to CPA quarterly. One-button ZIP from Tier 4 removes manual copy/paste.
2. **Collections Lag Forecaster** — Speculative. Extends `nr2CollectionLag` with a 30-day projection. Only if `sd_payments` history > 12 months.
3. **Hygiene Recall Revenue-at-Risk** — Justified. Extend existing `hygieneRecall` widget with dollar value of overdue recall patients using fee schedule lookup.
4. **Equipment Depreciation Tracker** — Speculative. Manual entry table `assets` with simple straight-line depreciation shown in EBITDA normalization. Only if operator actively buys equipment.

## Implementation Phases (numbered hal-10069+ with acceptance criteria)
### hal-10069 — Tier 1 Live Binds
- **Scope**: `nr2ProductionReconciliation`, `nr2CollectionLag`, `quickbooksMonthlyRevenue`, `softdentProductionDaily`, `nr2KpiRibbon`.
- **Files**: `page-canvas-data.js`, `nr2_http_server.py`, `page-schema.js` (remove stub flags).
- **Acceptance**: 
  - 5 widgets render numeric data on Financial & HAL pages.
  - `validate-pages.mjs` PASS.
  - Stale badges appear if source tables > 24h old.

### hal-10070 — SoftDent ODBC Extract Foundation
- **Scope**: pyodbc lane, `sd_*` tables, upserts, `ensure_softdent_odbc_fresh()`.
- **Files**: `softdent_practice_exports.py`, `import_sync.py`, `nr2_http_server.py` (admin route), env vars.
- **Acceptance**: 
  - `test_softdent_practice_exports.py` passes with ODBC or skips gracefully.
  - At least 3 `sd_*` tables populated with >0 rows after extract.
  - JSON fallback still works when ODBC absent.

### hal-10071 — QB Completeness + SoftDent Daily Binds
- **Scope**: New QB routes + binds; daily SoftDent widget binds.
- **Files**: `qb_connector.py`, `quickbooks_monthly_sync.py`, `nr2_http_server.py`, `page-canvas-data.js`, `page-schema.js`.
- **Acceptance**: 
  - 4+ new QB widgets render live.
  - 4+ SoftDent daily widgets render live.
  - `validate-hal.mjs` still PASS.

### hal-10072 — HAL Synthesis & Proactive Briefings
- **Scope**: `cross_reconcile_skill`, morning briefing, consent-gated actuator proposal.
- **Files**: `hal-skills.js`, `hal-proactive.js`, `hal-agent-loop.js`, `hal-hub-client.js`.
- **Acceptance**: 
  - HAL hub auto-generates a briefing card on first page load if >18h old.
  - Briefing references at least two domains (e.g., production + expenses).
  - No autonomous POST executes without operator click.

### hal-10073 — Workstation Parity + Hardening
- **Scope**: 8766 sync triggers, sidenotes bridge, backup, audit, health endpoint.
- **Files**: `workstation/index.html`, `app.js`, `nr2_http_server.py`, new `backup_db.py` (or function in `import_sync.py`).
- **Acceptance**: 
  - Workstation can trigger QB sync and see confirmation.
  - `/api/health` returns valid JSON.
  - Backup script produces a `.db` file in `backups/` within 5 seconds.

### hal-10074 — Print + CPA Export + Accessibility
- **Scope**: Print-safe CSS, CPA packet zip export, focus-visible toolbar, reduced-motion, mosaic aria-labels.
- **Files**: `nr2-moonshot-glow.css`, `hal-mockup-overrides.css`, `cpa_packet_export.py`, `nr2_http_server.py`, `nr2-moonshot-mockup-chrome.js`, `app.js`, `services.js`.
- **Acceptance**:
  - `@media print` in glow CSS; Financial page CPA export downloads zip with 4 widget JSON files.
  - `validate-hal.mjs` 103+ suites PASS; `test_cpa_packet_export.py` PASS.
  - Moonshot completion doc at `docs/MOONSHOT_FULLEST_EXTENT_COMPLETE_2026-07-09.md`.

**End of Moonshot fullest-extent plan (hal-10069 → hal-10074).**
