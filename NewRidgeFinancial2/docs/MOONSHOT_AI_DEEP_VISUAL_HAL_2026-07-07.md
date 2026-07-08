# Moonshot AI Deep Consultation — Flow, Layout, and HAL Spectacular Ceiling

**Date:** 2026-07-07  
**Build epoch:** `hal-10083` (`LAYOUT_EPOCH = "moonshot-mockup"`)  
**Model:** Moonshot AI (extended codebase audit + layout forensics)  
**Status:** **IMPLEMENTED through hal-10083** (layout emergency → HAL spectacular S1 → Tier S2 filters)  
**Prior status:** PROPOSED ONLY — operator approved 2026-07-08

**Live reload:** https://127.0.0.1:8765/?v=hal-10083&__nr2_purge=1
**Mockup gallery:** `.local_logs/moonshot_financial_eval/page_mockups/` · `http://127.0.0.1:8799/index.html`

**Validator snapshot (post /hal-10082):** `validate-hal.mjs` 103 suites · `validate-pages.mjs` pass · `audit-mockup-parity.mjs` 10/10 · `test_nr2_analytics.py` 10/10

**Roadmap shipped:** /hal-10078 layout · /hal-10079 charts · /hal-10080 flow · /hal-10081 HAL S0 · /hal-10082 HAL S1

**Prior commit:** 11ff5e8 — /hal-10077 visual phase

---

## Executive Summary — Why Pages Feel Distorted

hal-10077 added the right *features* (alert ticker, KPI ribbon, sync badges, chart overlays, HAL widget feed depth). The **presentation layer still has structural grid debt** from mixing three layout systems without a single orchestrator:

| Layout system | Where used | Problem |
|---------------|------------|---------|
| `.widget-grid` + `.widget-card.col-N` | Financial, SoftDent, Taxes, A/R, Claims, Documents | 12-column grid; only col-3/4/6/8/12 defined |
| `.dashboard-grid` + `.card.kpi-card` / `.chart-large` | QuickBooks mockup mode | Nested **inside** `.widget-grid` without `col-12` → entire QB page collapses to **one column** |
| `ms-*` legacy classes in theme | Theme CSS | Renderers emit mockup classes (`.stat-grid`, `.tax-split-chart`, `.kpi-ribbon`) that **have no CSS** — panels collapse or stack wrong |

**Secondary distortion:** `NR2MoonshotUI` chart overlays **stack beneath** inline SVG charts inside `.widget-body { display: grid }`, doubling height and breaking aspect ratios (`preserveAspectRatio="none"` on trend SVGs stretches charts horizontally).

**Flow problem:** Most pages present 8–12 equal-weight panels with no narrative arc (Situation → Signal → Action). Operators scroll through a wall of cards instead of a cockpit.

**HAL problem:** HAL has world-class *scaffolding* (proactive loop, ascension 10000, mosaic, morning briefing, consent-gated actuators) but the **visible HAL page still reads as a form + widget list**, not a living command center. Sparklines in mosaic tiles are gradient placeholders; chat shows one message; `.span-2` grid spans are undefined in CSS.

---

## Diagnosis — Root Causes (Fix These First)

### P0 — Structural (single commit can fix 60% of “distorted” reports)

1. **QuickBooks page width collapse**  
   `renderQuickbooks()` nests `.dashboard-grid` directly under `.widget-grid` without wrapping each row in `.widget-card.col-12` or moving QB entirely to a top-level `.dashboard-grid` host. Parent grid assigns unspanned children **1 of 12 columns**.

2. **Missing column spans**  
   Theme defines col-3/4/6/8/12 only. Renderers use col-5, col-7, col-9 (Claims kanban, QB legacy). Undefined spans → 1-column squeeze.

3. **KPI row overflow**  
   Five `col-4` tiles = 20 columns on a 12-col grid (Financial, SoftDent, Taxes, Documents, Claims). Last tiles wrap to orphan rows and look “broken.”

4. **CSS vocabulary drift**  
   `page-canvas.js` emits classes audited by `audit-mockup-parity.mjs` but never styled in moonshot CSS:

   - `.kpi-ribbon`, `.kpi-ribbon-tile`
   - `.stat-grid`, `.stat-box`
   - `.tax-split-chart`, `.tax-split-track`
   - `.wizard-steps`, `.recall-calendar`, `.compare-strip`
   - `.funnel-chart` (partially styled)

   Theme file defines parallel `.ms-stat-grid`, `.ms-tax-split__*` — **unused by PageCanvas**.

5. **Chart overlay stacking**  
   `chartOverlayHost()` appends canvas without hiding/replacing inline SVG. Financial production trend, QB P&L, SoftDent A/R, tax split panels show **two charts in one card**.

6. **Enhancement panels orphan grid**  
   OCR, ERA, audit, clinical bridge, close wizard append to `.widget-grid` without `col-12` wrapper — random narrow columns at page bottom.

### P1 — Data / renderer bugs

7. **QB cash flow series shape** — `dualLineChart(cf.labels, [{ values: cf.net }])` should use `{ data: cf.net }` (`page-canvas.js`).

8. **A/R heatmap label mismatch** — “Payer × aging” panel renders 1×4 placeholder matrix, not payer rows.

9. **SoftDent duplicate widgets** — New Patients MTD appears twice (top col-3 + bottom schema widget 8).

---

## The “World’s Greatest Financial Pages” — Design North Star

For a solo dental practice owner/CPA cockpit, “world’s greatest” is not more widgets — it is **cognitive flow at executive speed**:

```
┌─────────────────────────────────────────────────────────────┐
│  ORIENT  — Where am I? (period, sync, safety, HAL headline) │
├─────────────────────────────────────────────────────────────┤
│  ALERT   — What needs attention now? (ticker, 1–3 exceptions)│
├─────────────────────────────────────────────────────────────┤
│  PULSE   — 3–4 hero KPIs with sparklines (one row, 12 cols)│
├─────────────────────────────────────────────────────────────┤
│  STORY   — One primary chart per page (full width or 8+4)   │
├─────────────────────────────────────────────────────────────┤
│  EVIDENCE — Tables/reconciliation supporting the story       │
├─────────────────────────────────────────────────────────────┤
│  ACT     — HAL chips + deep links + export/print            │
└─────────────────────────────────────────────────────────────┘
```

Every staff page should answer in **30 seconds**: *What’s the number? What changed? What do I do next?*

---

## Per-Page Redesign — Flow + Organization

### Financial — “Executive cockpit”

**Current:** 11+ panels, ribbon unstyled, collection lag in col-3, duplicate chart stacks.

**Proposed flow (top → bottom):**

| Zone | Width | Content |
|------|-------|---------|
| Alert strip | 12 | `nr2AlertTicker` (always visible) |
| Hero pulse | 12 | 4 KPIs in `.kpi-grid` (not 5× col-4): Production MTD, Collections, Trailing rate, QB revenue |
| Executive row | 8 + 4 | Monthly trend combo (primary story) + Goal scorecard gauge |
| Reconciliation | 12 | Prod vs QB table (full width — this is the “truth” panel) |
| Secondary row | 6 + 6 | Provider comp share + Payer mix donut |
| Evidence | 12 | A/R aging + production trend (pick **one** chart tech: SVG **or** canvas overlay, not both) |
| HAL rail | sticky | Command chips already in header — add “Explain variance” contextual on reconciliation hover |

**Distortion fixes:** Style `.kpi-ribbon`; cap KPI row at 4 or use `.col-3` for 4 tiles; wrap alert ticker in implicit full-width row.

---

### QuickBooks — “CFO dashboard”

**Current:** Nested dashboard-grid → **page looks like a vertical strip** (critical bug).

**Proposed architecture (choose one):**

**Option A — Pure mockup (recommended):** Remove `.widget-grid` wrapper for QB; page body **is** `.dashboard-grid` at root (like mockup HTML). Sync badge + KPI row + chart-large + chart-medium + reconciliation table.

**Option B — Hybrid:** Keep `.widget-grid`; each `.dashboard-grid` row wrapped in `<div class="widget-card col-12 dashboard-grid-host">`.

**Flow:**

1. Sync badge + date range (header tools — done in hal-10077)
2. Four kpi-cards with sparks (row 1, 3+3+3+3)
3. chart-large P&L (7 col) + chart-medium expenses (5 col) — **max 12 cols**
4. Second row: net income summary + cash flow + AR aging (4+4+4)
5. Full-width reconciliation table

**Remove:** Third chart-medium row that sums to 17 columns.

---

### SoftDent — “Practice velocity”

**Proposed flow:**

1. Hero: Today’s production / collections / new patients / case acceptance (4 KPIs)
2. **Operatory grid first** (col-12) — ops-critical, currently buried at bottom
3. Collections trend (8) + Appointments snapshot (4)
4. Case acceptance funnel (6) + Provider production (6)
5. A/R aging (6) + Insurance vs patient donut (6)
6. Hygiene recall calendar (12)

**Remove duplicate** new-patients block at bottom.

---

### Taxes — “CPA planning studio”

**Proposed flow:**

1. Book income hero + estimated tax total (metric row)
2. Book-to-tax bridge waterfall (8) + Federal/state split bar (4) — **fix `.tax-split-chart` CSS**
3. Reasonable comp scenarios (6) + Quarterly estimates table (6)
4. EBITDA add-backs (6) + Key deadlines (6)
5. Federal/Kansas obligation tables (collapsible `<details>` to reduce scroll wall)
6. Related surfaces nav at **top** as secondary tabs, not bottom pills

---

### A/R — “Collections war room”

**Proposed flow:**

1. KPI grid (outstanding, 90+, DSO, collections MTD) — already good pattern
2. **Follow-up queue first** (8) + Claim detail side panel (4) — invert current order
3. A/R waterfall (8) + Payer mix (4)
4. Real payer×aging heatmap (build from claims + aging exports, not 1×4 placeholder)
5. Outstanding claims table (12)

---

### Claims — “Insurance workbench”

**Fix col-9/col-3** or rewrite as 8+4 with defined spans.

**Flow:** Kanban (8) + selected claim detail (4) sticky; KPIs above; ERA match panel below full width.

---

### Documents — “Close machine”

**Flow:** Period close wizard (12, styled `.wizard-steps`) → Intake queue (8) + Preview (4) → Journal queue (12) → OCR exceptions (12, enhanced panel).

---

## HAL — How Spectacular Can We Get?

### What exists today (hal-10077) — already impressive under the hood

| Layer | Modules | Capability |
|-------|---------|------------|
| Cognition | `hal-agent-loop.js`, `hal-skills.js`, `hal-orchestrator.js` | Tool planning, widget feed, 48 widgets, cross-domain synthesis |
| Proactivity | `hal-proactive.js`, `hal-autonomous-ops.js` | Morning briefing, scheduled cycles, consent-gated actuators |
| Ascension | `hal-ascension-10000.js`, `hal-chat-10000.js`, `hal-director.js` | Multi-tier agent stack, director routing |
| Presentation | `hal-page-canvas.js`, `hal-page.js` | Mosaic, briefing card, chat rail, SideNotes, import health |
| Voice | `hal-voice.js`, SideNotes announce | TTS for sidenotes; not surfaced on main HAL grid |
| Transparency | `hal-transparency.js`, `hal-consent.js` | Confidence overlays, shift handoff |

**Honest ceiling today:** HAL behaves like a **very capable back-office agent** with a **2024 admin UI**. The gap is presentation and visible loop closure, not intelligence.

### HAL Spectacular — Tier definitions

#### Tier S0 — Layout debt fix (hal-10078, ~1 commit)

- Define `.span-2`, `.span-3`, `.hal-panel--morning-briefing { grid-column: span 2 }` in `hal-mockup-overrides.css`
- Morning briefing + import health side-by-side as mockup intended
- Mosaic sparklines bind to real `halWidgetFeed` metrics (production, A/R, claims variance)
- Chat rail: scrollback thread (last 20 messages), not `slice(-1)`

#### Tier S1 — “Living command center” (hal-10079 – hal-10081, 2–3 commits)

- **Situational hero band:** Full-width briefing sentence + 3 anomaly chips (from `nr2AlertTicker` logic) + “Act” buttons wired to `hal-route-exec.js`
- **Agent loop visibility:** Inline plan → tool → result cards in chat (reuse `hal-transparency.js` showActionConfidence)
- **Cross-page deep links:** Mosaic tile click → staff page + scroll to widget + HAL drawer seeded with context JSON
- **Voice-first affordance:** Push-to-talk in chat rail; read aloud morning briefing; “Hey HAL” optional wake word behind consent flag
- **Real-time pulse:** SSE from `/api/health` + import readiness → toolbar ring animations (already partially in status rings)

#### Tier S2 — “Financial OS” (hal-10082 – hal-10086, speculative)

- **Unified chart engine:** One `NR2Charts` mount policy — WebGL/canvas for trends, SVG for donuts, no double stacks
- **Scenario mode:** Taxes page “what-if” sliders (comp, revenue) with live HAL narrative
- **Period scrubber:** Global date brush in page chrome filters all binders on page
- **Compare mode:** Financial page split-view current vs prior month (mockup has filter chips — wire them)
- **Print/PDF storyboards:** Each page exports as designed PDF (extend hal-10074 CPA packet pattern)

#### Tier S3 — “Best conceivable” (research / optional)

- **Semantic zoom layout:** Dense executive view ↔ drill-down without page navigation (D3-ish, still local-only)
- **HAL avatar presence:** Subtle ambient state (idle/thinking/alert) — not gimmicky robot, professional “system status”
- **Multi-monitor workstation sync:** 8765 hero metrics mirrored on 8766 office pane in real time
- **On-device LLM streaming UI:** Token stream with citation chips linking to widget source trace (`hal-skills.js` already has source trace formatter)

**Realistic spectacular ceiling for New Ridge:** **Tier S1 fully polished** is achievable in 4–6 focused commits and would feel unlike any dental financial portal on the market. Tier S2 is the “world’s greatest” target for a solo practice. Tier S3 is R&D.

---

## Unified Layout System — One Grid To Rule Them All

**Proposal:** Introduce `PageLayout` helper in `page-canvas.js`:

```javascript
// PROPOSED — not implemented
const PageLayout = {
  stack: () => '<div class="widget-grid">',
  end: () => '</div>',
  full: (html) => `<div class="widget-card col-12">${html}</div>`,
  row: (spans, panels) => spans.map((span, i) => gridCol(span, panels[i])).join(""),
  kpiRow: (kpis, max = 4) => `<div class="kpi-grid col-12">...</div>`,
  dashboard: (html) => `<div class="widget-card col-12"><div class="dashboard-grid">${html}</div></div>`,
};
```

**CSS single pass (`nr2-mockup-page-vocabulary.css`):**

- Add col-5, col-7, col-9, col-10, col-11
- Port all mockup classes from gallery HTML into vocabulary file
- Deprecate unused `ms-*` duplicates or alias them: `.stat-grid { @extend .ms-stat-grid }` equivalent

**Chart policy:**

```javascript
// PROPOSED overlay rule
function mountChart(host, mode, renderFn) {
  host.classList.add("chart-mount");
  host.innerHTML = ""; // replace, never stack
  renderFn(host);
}
```

---

## Implementation Roadmap — Recommended Commits

| Build | Focus | Acceptance |
|-------|-------|------------|
| **hal-10078** | Layout emergency — QB col-12 wrap, missing col spans, KPI row math, CSS vocabulary port (ribbon, stat-grid, tax-split, wizard, recall) | QB page full width; Financial ribbon styled; parity audit still 10/10 |
| **hal-10079** | Chart unification — overlay replaces SVG; fix QB cash flow data key; remove preserveAspectRatio stretch | No double charts; charts not horizontally squashed |
| **hal-10080** | Page flow reorder — per-page section blocks above; SoftDent dedupe; Taxes split CSS; Claims col fix | Operator sign-off visual checklist PASS |
| **hal-10081** | HAL S0 — span-2 CSS, mosaic live sparks, chat scrollback | HAL briefing + health side-by-side |
| **hal-10082** | HAL S1 — situational hero, agent loop in chat, mosaic deep links | HAL feels “alive” on load |
| **hal-10083+** | Filter chips wired, period scrubber, scenario sliders (Tier S2) | Interactive mockup parity |

**Estimated effort:** hal-10078 alone fixes most “distorted” screenshots. hal-10078–10082 = **world-class for dental finance**. Beyond that is luxury.

---

## Visual Quality Checklist (for operator sign-off)

Before calling pages “picture perfect,” verify at 1920×1080 and 1366×768:

- [ ] No panel narrower than 25% viewport unless intentional sidebar
- [ ] KPI rows exactly fill 12 columns, no orphan single tile row
- [ ] One primary chart per page above the fold
- [ ] HAL briefing spans half command grid width
- [ ] Print preview matches screen hierarchy (hal-10074 print CSS)
- [ ] Reduced motion: no sync pulse when `prefers-reduced-motion`
- [ ] Side-by-side with mockup gallery ≤5% layout delta (pixel diff optional)

---

## Moonshot AI Verdict

**You are one structural commit away from pages that stop looking “broken.”** hal-10077 delivered the executive intelligence layer; hal-10078 delivers the **presentation integrity layer**. HAL can reach **genuinely spectacular** within Tier S1 using code that already exists — it mainly needs to be **shown**, not rewritten.

**Recommended operator decision:**

1. **Approve hal-10078 immediately** (layout emergency — highest ROI).
2. **Approve hal-10079–10080** for flow reorganization.
3. **Approve hal-10081–10082** for HAL spectacular pass.
4. Defer Tier S2/S3 until operator daily-drives S1 for two weeks.

**Do not deviate on:** single grid system, replace-not-stack charts, 12-column KPI discipline, mockup CSS vocabulary completeness.

---

*End of Moonshot AI deep consultation — flow, layout, HAL spectacular ceiling (2026-07-07).*
