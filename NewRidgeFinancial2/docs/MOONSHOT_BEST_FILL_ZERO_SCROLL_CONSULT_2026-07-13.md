# Moonshot AI — Best widgets to fill page (zero-scroll) CONSULT ONLY

**Date:** 2026-07-13
**Model:** `kimi-k2.5`
**Key:** OPENROUTER_API_KEY
**Build:** hal-10611
**Script:** `scripts/run_moonshot_best_fill_zero_scroll_consult.py`
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> ok without scrolling and using the best widgets that fill the page ask moonshoot ai how and what would he use

---

# Verdict
**Fibonacci Mosaic** — A fixed 4-band vertical stack (80/240/320/240px) using existing `apex-core.js` primitives, tiling secondary widgets horizontally to fill 1920px width, with HAL chat occupying the primary 320px band when present, and all overflow demoted to right-drawer subpages.

## 0. Operator Intent (verbatim; consult-only)
> "ok without scrolling and using the best widgets that fill the page ask moonshoot ai how and what would he use"

## 1. How I would fill the page (composition model)
**"2×2 Fibonacci Mosaic"** — Two secondary bands (240px) sandwiching one primary band (320px), capped by a micro executive strip (80px), leaving 60px for chrome/borders within 1080px viewport.

- **Band 0 (Micro/Executive):** 80px × 1920px. Single full-width `executive-strip` containing exactly 4 KPI pills (no scroll, no wrap).
- **Band 1 (Secondary):** 240px × 1920px. **Tiled horizontally**: two widgets side-by-side (960px each) or three (640px each). Uses `dual-axis-trend`, `horizontal-bar`, `status-matrix`, or `radial-gauge`.
- **Band 2 (Primary):** 320px × 1920px. **Single wide widget** or 50/50 split (960px each). Reserved for `hal-ask` (chat), `claims-open-kanban`, `om-daily-huddle`, or `patient-dossier-card`.
- **Band 3 (Secondary):** 240px × 1920px. **Tiled horizontally**: `data-table` (5-row) + `action-list`, or `timeline-lanes` + `bullet`.

**Filling logic:** Bands 1 and 3 must tile edge-to-edge (no center gaps). If a page lacks HAL chat, Band 2 becomes a composed secondary zone (two 480px tiles). Empty states collapse to 0px (authentic emptiness), redistributing height to remaining bands to avoid sparse padding.

## 2. The best widgets I would USE (shared kit — ranked, why each)
1. **`financial-command-strip` (Micro)** — Densest signal-to-pixel ratio. Shows Production | Collections | AR | Import Health in 80px. Reuses existing `renderKpiStrip()`.
2. **`dual-axis-trend` (Secondary)** — Single widget, two data series (e.g., Production vs Payroll). Fills 960px width in Band 1. Practice-truthful trend without D3 bloat.
3. **`status-matrix` (Secondary)** — 4×4 grid of import/sync health (Bridge Errors, Cache KPI, Reconciliation, Unified DB). Critical for safety; fits 640px or 960px tile.
4. **`claims-open-kanban` (Primary)** — Only kanban allowed above fold. Compact 3-column layout (To-Do → In-Progress → Review) at 320px height. Prevents scroll by capping lanes to 4 cards each with "+%n" overflow button.
5. **`data-table` (5-row) (Secondary)** — Specific 5-row hard limit. Shows top 5 quarantine items, bridge errors, or collection tasks. Scrollable internally (virtual), but container fixed at 240px.
6. **`radial-gauge` (Secondary)** — Collections to Goal or ERA Match %. Single metric, high visual impact, 240px × 640px tile aspect. No animation (performance).
7. **`horizontal-bar` (Secondary)** — Provider ranking or AR Aging buckets. Fits 960px width cleanly. Uses existing `apex-core.js` `renderMicroBar()`.
8. **`timeline-lanes` (Secondary)** — Pre-auth aging or Tax period scrubber. Horizontal swimlanes, no vertical scroll, 240px height.
9. **`action-list` (Secondary)** — Compact 3-item list with "Execute" buttons. Fits 640px tile in Band 3.
10. **`hal-ask` (Primary)** — The HAL chat interface. Mandatory 320px height for transcript readability. Positioned Band 2 when on HAL page; if HAL is auxiliary on another page, demoted to drawer.

## 3. Per-page first-viewport lineup (exact widgets + layout budget)

### Financial (36 → 6 visible)
- **B0:** `financial-command-strip` (80px) — 4 pills: Production, Collections, AR, Import Health
- **B1:** Left: `dual-axis-trend` (Production vs Payroll), Right: `horizontal-bar` (Top 5 Providers) — 240px
- **B2:** Left: `status-matrix` (Bridge Errors | Recon | Cache | Quarantine), Right: `radial-gauge` (Collections to Goal) — 320px
- **B3:** `data-table` (5-row) (Gold CSV Tickets + Quarantine items) — 240px full width
- **Drawer:** All EBITDA widgets, treemaps, deep audit statuses, waterfall charts.

### SoftDent (31 → 6 visible)
- **B0:** `sd-vitals-strip` (80px) — 4 pills: Collections Gap, Production Gap, Aging Gap, ERA835 Status
- **B1:** Left: `softdent-visual-ledger-recon` (Secondary), Right: `collections-gauge` (Radial, Goal %) — 240px
- **B2:** `softdent-gold-csv-drop-ops` (Primary, 320px) — **Critical OPS zone**: Drop target + validation preview (preserves Excel/Print Preview authenticity via iframe container)
- **B3:** Left: `sd-prod-trend` (Spark), Right: `softdent-tp-estimate-chips` (Status) — 240px
- **Drawer:** All "gap" detail widgets (PWImages, Eligibility, Catalogs), Stale Import deep dive.

### Claims (17 → 6 visible)
- **B0:** `claims-executive-strip` (80px) — 4 pills: Open Claims, >90 Aging, Denial Rate, ERA Match
- **B1:** Left: `claims-aging-exposure` (Horizontal bar), Right: `denial-pareto` (Micro bars) — 240px
- **B2:** `claims-open-kanban` (Primary, 320px) — 3 lanes, max 4 cards each
- **B3:** Left: `verification-matrix` (Status grid), Right: `claims-era-gauge` (Radial) — 240px
- **Drawer:** Risk analytics, EOB posting backlog, Clinical signoff queue, Attachment deep dive.

### AR (13 → 6 visible)
- **B0:** `ar-vitals-strip` (80px) — 4 pills: Total AR, >90 Bucket, Follow-up Queue, Unapplied Credits
- **B1:** Left: `ar-aging-chart` (Horizontal bar), Right: `collection-bullet` (Bullet chart) — 240px
- **B2:** `ar-heatmap-grid` (Primary, 320px) — Patient/Provider heatmap (high signal density)
- **B3:** `ar-collection-task-list` (Action list 5-row) + `ar-forecast-trend` (Spark) side-by-side — 240px
- **Drawer:** Waterfall, Variance bars, Pareto charts, Credit float details.

### Taxes (8 → 5 visible)
- **B0:** `tax-core-strip` (80px) — 4 pills: Year Status, C0 Import, Planning Open, Disclaimer
- **B1:** `tax-bridge-waterfall` (Secondary, full width 1920px) — Compact 5-step waterfall — 240px
- **B2:** `tax-open-planning` (Primary, 320px) — Actionable planning list
- **B3:** `taxes-period-scrubber` (Timeline lanes, full width) — 240px
- **Drawer:** Variance bar details, C0 import guidance deep dive.

### Office-Manager (34 → 6 visible)
- **B0:** `om-vitals-strip` (80px) — 4 pills: Huddle Status, Import Freshness, Operatory Util, Open Op Count
- **B1:** Left: `operatory-util-board` (Secondary), Right: `om-priorities` (Action list) — 240px
- **B2:** `om-daily-huddle` (Primary, 320px) — The main huddle interface
- **B3:** Left: `patient-responsibility-calc` (Mini), Right: `payer-donut` (Compact) — 240px
- **Drawer:** Payer contact admin, Policy changelog, Eligibility cards, Weekly schedule list.

### HAL (18 → 5 visible)
- **B0:** `hal-import-health` (80px) — 4 pills: Cache KPI, Bridge Errors, Recon Status, Unified DB
- **B1:** Left: `hal-mosaic-prod` (Spark), Right: `hal-mosaic-coll` (Spark) — 240px
- **B2:** `hal-ask` (Primary, 320px) — Chat interface (transcript + input)
- **B3:** Left: `hal-recommended-actions` (Action list), Right: `hal-ai-insight` (Compact) — 240px
- **Drawer:** Full logs, Categorize assist, Structured remember deep view.

## 4. Demotion map (what leaves the first viewport)
**Universal Drawer Route:** `#/page/drawer/ops` (right-side 640px drawer, slides over, no page scroll)

- **Financial:** `deep-audit-status`, `reconciliation-status` (duplicate of strip), `production-vs-payroll` (moved to trend), `unified-db-snapshot` (in strip), `import-quarantine-panel` (details only), `gold-csv-ticket-ops` (moved to table), `ebitda-station`, `ebitda-variance-bar`, `expense-treemap`, `revenue-composition`.
- **SoftDent:** `softdent-outstanding-claims-bridge`, `softdent-insco-ada-estimates`, `softdent-insco-ada-catalog`, `softdent-gold-payment-pipeline`, `softdent-pwimages-eligibility`, `softdent-gold-era-settlement`, `softdent-print-preview-audit` (preserved via B2 OPS zone, but detail view in drawer), `stale-import-alert` (demoted to drawer badge).
- **Claims:** `claims-risk-analytics`, `claims-risk-bars`, `eob-posting-backlog`, `clinical-signoff-queue`, `claim-status-lanes` (redundant to kanban), `ins-patient-split`.
- **AR:** `ar-waterfall`, `ar-aging-pareto`, `unapplied-credit-float` (summary in strip, detail in drawer), `ar-aging-outlook` (redundant to chart).
- **Taxes:** `c0-import-guidance` (drawer), `ebitda-variance-bar` (drawer).
- **Office-Manager:** `import-health-monitor` (in strip), `payer-change-alerts`, `policy-changelog`, `payer-contact-admin`, `hal-structured-remember`, `weekly-schedule-list`, `patient-dossier-card` (demoted unless actively viewing patient).

## 5. Visual density rules (fill without scroll or sparseness)
1. **Fibonacci Heights Only:** 80 | 240 | 320. No 120px "mini" orphans that leave 40px padding.
2. **Tile Math:** Band 1 and 3 must sum to 1920px width exactly. Preferred splits: 960/960 (2×) or 640/640/640 (3×). No 1200/720 asymmetry.
3. **Empty Collapse:** If a widget reports `empty: true`, its tile collapses to 0px and sibling tiles expand proportionally (e.g., 960+960 becomes 1920 single width) to prevent "gray dead zones."
4. **HAL Chat Minimum:** If `hal-ask` present, Band 2 must be 320px minimum. If viewport <900px (tablet), degrade to drawer (breakpoint 10611-C).
5. **KPI Pill Limit:** Exactly 4 pills in Band 0. If >4 metrics, rotate visibility based on alert severity (highest variance shows).
6. **Font Scale:** 12px/14px compact (existing `apex-compact.css`). No 16px headers in micro strips.

## 6. Coding package if approved (MUST / SHOULD; real files)
**MUST (Critical path for zero-scroll):**
- `site/apex-core.js` — Add `APEX_COMPACT` height enforcement and `renderMosaicTile()` wrapper.
- `site/apex_compact_pages_pack/mosaic_layout.html` — Master template with B0-B3 bands.
- `pages/financial/compact_controller.js` — Maps specific widgets to bands per Section 3.
- `pages/softdent/compact_controller.js` — Preserves `softdent-gold-csv-drop-ops` DOM integrity for Excel/Print Preview.
- `css/apex-zero-scroll.css` — `.band-micro {height:80px}`, `.band-secondary {height:240px}`, `.band-primary {height:320px}`, `.tile-50 {width:50%}`, `.tile-33 {width:33.33%}`.

**SHOULD (Polish/Overflow):**
- `components/drawer_right_ops.html` — Right-side drawer (640px) for demoted widgets.
- `scripts/compact_resize_guard.js` — Monitors `document.body.scrollHeight`; warns if >1085px.
- `pages/hal/chat_min_height_guard.js` — Ensures `hal-ask` textarea never compresses below 120px within its 320px band.

**File paths (existing to modify):**
- `site/apex-core.js` (lines 400-450 approximate) — Insert compact rendering switch.
- `pages/financial/index.html` — Replace grid with mosaic bands.
- `pages/softdent/index.html` — Protect Gold CSV drop zone height.

## 7. Breakage risks
1. **SoftDent Print Preview:** If `softdent-gold-csv-drop-ops` container height <320px, Excel ActiveX/iframe rendering may clip or fail. **Mitigation:** Band 2 reserved 320px minimum; no collapse allowed even if empty.
2. **HAL Chat Usability:** Transcript history below 240px becomes unreadable. **Mitigation:** Band 2 fixed at 320px; if operator resizes window below 900px, force drawer mode for secondary widgets.
3. **Import Sync Safety:** Demoting `import-health-monitor` to drawer (out of Band 0) risks missing real-time bridge errors. **Mitigation:** `financial-command-strip` and `sd-vitals-strip` MUST include Import Health as one of the 4 pills (non-negotiable).
4. **Tax Waterfall Aspect Ratio:** `tax-bridge-waterfall` at 240px height may distort if forced to 1920px width. **Mitigation:** Constrain to 960px tile (50% width) in Band 1, pair with `ebitda-variance-bar`.

## 8. What NOT to invent / redo
- **No new chart libraries:** Do not import D3, Chart.js, or Recharts. Use existing `renderSpark()`, `renderMicroBar()` from `apex-core.js`.
- **No SoftDent dollars:** Never invent currency or financial figures. Use import-backed data only.
- **No "smart" resizing:** Do not use ` ResizeObserver` to dynamically reflow bands; use fixed CSS grid to prevent scroll jank.
- **No radial gauges >120px:** If gauge doesn't fit in 240px band tile, demote it.
- **No waterfall in primary:** Waterfall charts stay in 240px secondary band; they are too sparse for 320px primary real estate.

## 9. Acceptance criteria
- [ ] `document.body.scrollHeight` ≤ 1085px on 1920×1080 resolution (Chrome/Edge) for all 7 pages.
- [ ] Band 0 displays exactly 4 KPI pills without wrapping or overflow.
- [ ] HAL chat textarea (Band 2 on HAL page) visible and accepts keyboard input without page scroll.
- [ ] SoftDent Gold CSV drop zone (Band 2 on SoftDent page) renders Print Preview correctly without internal scrollbars.
- [ ] Empty widgets collapse to 0px; remaining widgets in same band expand to fill width (no dead gray zones).
- [ ] No D3 or external chart libraries loaded; only `apex-core.js` primitives used.
- [ ] All "demoted" widgets accessible within 1 click (drawer button visible in Band 3 or nav).

## 10. Executive Summary (5 bullets)
- **Physics wins:** 36 widgets cannot fit; 6 carefully chosen widgets in a 4-band mosaic (80/240/320/240px) fills 1080px without scroll.
- **HAL preserved:** Chat gets the 320px primary band; readability protected by hard height floor.
- **OPS protected:** SoftDent Gold CSV drop zone and Print Preview occupy protected primary band; no demotion of critical operational surfaces.
- **Safety first:** Import Health and Bridge Errors always visible in Band 0 (4-pill limit), even if all else demoted.
- **Zero invention:** Reuses only `apex-core.js` primitives (`strip`, `spark`, `gauge`, `matrix`, `table-5row`); no new dependencies.

## 11. Approval checklist
- [ ] Confirm SoftDent Print Preview compatibility with 320px fixed height.
- [ ] Confirm 4 KPI pills sufficient for executive oversight (can rotate which 4 display).
- [ ] Approve demotion of EBITDA/Waterfall charts to drawer on Financial/Taxes pages.
- [ ] Verify `apex-core.js` compact primitives exist in current build (hal-10611).
- [ ] Acknowledge consult-only status; await explicit "APPLY" command before modifying `site/apex-core.js`.
