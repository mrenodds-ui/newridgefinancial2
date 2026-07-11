# Moonshot AI — Missing Widgets + How They Look (CONSULT ONLY)

**Date:** 2026-07-11  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Build reviewed:** hal-10441+  
**Script:** `scripts/run_moonshot_missing_widgets_look_consult.py`  
**Apply:** DO NOT APPLY until operator validates.

## Operator request (verbatim)

> ask moonshot ai what widgets i dont have woul be great for the program and show wha they look like, report

---

# Verdict

## 0. Operator Intent (quote; confirm consult-only)

> *"ask moonshot ai what widgets i dont have woul be great for the program and show wha they look like, report"*

**Confirmed CONSULT-ONLY.** No code will be generated, committed, or applied to build `hal-10441` until the operator explicitly approves a specific phase. This report identifies high-value missing mosaic instruments for the Kansas dental S-corp (SoftDent + QuickBooks), describes their appearance in the Apex starship palette (cyan/amber/magenta), and provides ASCII wireframes using only placeholder data ($—, Patient A, D—, etc.).

---

## 1. Already Have (skip list — brief)

Per `hal-10441` LIVE FACTS, the following instrument types are already shipped and are **not** recommended again:
- **Core:** kpi, status, pulse, remainder, funnel, countdown, heatmap, calculator, categorize, hal-chat, tax-library/narratives.
- **Charts:** horizontal-bar, donut, stacked-bar, waterfall, bullet, dual-axis-trend, revenue-composition, scrubber.
- **Financial/CPA:** ebitda-scrubber, ebitda-station, scenario-manager, filing-workflow, workpaper, financial-command-strip, executive-strip.
- **Claims:** claim-shelf, claims-kanban/workbench, claims-header-stats, claims-executive-strip, claims-aging-exposure, claims-critical-actions, claims-risk-bars, claims-era-gauge, claim-attachments, daily-huddle.
- **Chrome:** phosphor glow, holographic hover, corner brackets, scan sweep, nav LEDs, stage glitch, grid floor, dual tickers, HAL neural core.

---

## 2. Missing Widgets That Would Be Great (ranked)

### W-01 — Expense Category Treemap (SHOULD · Effort M)
- **Why great:** Reveals spending concentration instantly; surfaces “death by a thousand small vendors.”  
  **Page(s):** Financial, QuickBooks.  
  **Data source:** QuickBooks P&L expense accounts (hierarchical).  
  **Honesty:** Renders flat gray rectangles labeled “Expense hierarchy unavailable” if QB import lacks nesting; amounts display as `$—`.
- **Look:** A space-filling rectangular treemap. Parent categories bordered in cyan; children nested with area proportional to spend. Large blocks show amber text labels; small outliers glow magenta on hover. Phosphor glow highlights the active block; corner brackets frame the container.
- **Wireframe:**
```
┌─────────────────────────────────────┐
│  EXPENSE TREEMAP                [?] │
├─────────────────────────────────────┤
│  ┌──────────┬─────────┬─────────┐  │
│  │          │  SUPPLIES       │  │
│  │  PAYROLL │  ┌───┐  │  TAXES   │
│  │   $—     │  │LAB│  │   $—     │
│  │          │  └───┘  │          │
│  │          │   $—    │          │
│  └──────────┴─────────┴─────────┘  │
└─────────────────────────────────────┘
```
- **SVG sketch:** (Implicit in layout—nested rectangles with 1px cyan borders, fill opacity 0.2–0.8 based on relative spend.)

### W-02 — Procedure Profitability Scatter (SHOULD · Effort M)
- **Why great:** Identifies high-volume/low-margin traps (e.g., D4341 scaling that pays less than chair cost).  
  **Page(s):** Financial.  
  **Data source:** SoftDent procedure log (fee, net collection) + QB cost allocation by code (optional).  
  **Honesty:** Dots cluster at origin (0,0) with overlay “Cost data unavailable” when QB unlinked; axes labeled `$—`.
- **Look:** Canvas scatter plot inside corner brackets. X-axis “Billed Fee,” Y-axis “Net Collection.” Quadrant lines at median splits. Cyan dots = profitable & high volume; amber = underpaid; magenta = high fee/low collect. Crosshair laser cursor snaps to nearest dot on hover.
- **Wireframe:**
```
┌─────────────────────────────────────┐
│  PROCEDURE PROFITABILITY        [?] │
├─────────────────────────────────────┤
│  $— ↑      ● D2740      ○ D0220     │
│     │           ● D1110             │
│     ├──────────┼──────────          │
│     │  ○ D4341      ● D0120         │
│  $— └──────────┴──────────→ Fee     │
│           $—           $—           │
└─────────────────────────────────────┘
```

### W-03 — Denial Reason Pareto (MUST · Effort S)
- **Why great:** Focuses cleanup efforts on the “vital few” denial codes causing 80 % of leakage.  
  **Page(s):** Claims.  
  **Data source:** Claims workbench denial codes + ERA 835 remittance.  
  **Honesty:** “No denials recorded” when empty; cumulative line hugs 0 % baseline.
- **Look:** Horizontal bars (cyan fill) sorted descending by impact. Overlay amber line tracks cumulative percentage of total denials. Magenta dashed vertical line marks 80 % threshold. Dark navy background with faint scan-grid lines.
- **Wireframe:**
```
┌─────────────────────────────────────┐
│  DENIAL PARETO                  [!] │
├─────────────────────────────────────┤
│  CO-45 ████████████░░  $—    45%    │
│  PR-2  ████████░░░░░░  $—    72%    │
│  CO-16 ███░░░░░░░░░░░  $—    85% ──┤│
│  CO-29 ██░░░░░░░░░░░░  $—    92%    │
│        └─────────────────────       │
│        0%   50%   80%   100%        │
└─────────────────────────────────────┘
```

### W-04 — Treatment Plan Conversion Pipeline (MUST · Effort M)
- **Why great:** Case acceptance is production’s bottleneck; this exposes where patients drop off (Presented → Accepted → Scheduled → Completed).  
  **Page(s):** Financial, Office Manager.  
  **Data source:** SoftDent treatment plan export (status, value).  
  **Honesty:** Single gray trapezoid “No treatment plan data” when missing; counts show `—` and values `$—`.
- **Look:** Vertical funnel narrowing downward. Four trapezoid stages with cyan outlines; fill intensity reflects conversion health (amber gradient). Between stages, small magenta percentages display conversion rate. Bottom shows total completed value in large cyan numerals.
- **Wireframe:**
```
┌─────────────────────────────────────┐
│  TREATMENT CONVERSION           [+] │
├─────────────────────────────────────┤
│  ┌─────────────────────────────┐    │
│  │  PRESENTED      24  $—      │    │
│  │      ↓ 75%                    │    │
│  │   ACCEPTED       18  $—      │    │
│  │      ↓ 89%                    │    │
│  │   SCHEDULED      16  $—      │    │
│  │      ↓ 94%                    │    │
│  │   COMPLETED      15  $—      │    │
│  └─────────────────────────────┘    │
└─────────────────────────────────────┘
```

### W-05 — Pre-Authorization Aging Lanes (SHOULD · Effort S)
- **Why great:** Pre-auths block high-value treatment (implants, crowns); aging lanes prevent them from getting lost.  
  **Page(s):** Claims.  
  **Data source:** SoftDent pre-authorization export (procedure code, request date, status).  
  **Honesty:** “No pending pre-auths” collapses lanes to single line; segments show `0` counts.
- **Look:** Horizontal timeline bars for each procedure code (D—). Segmented by age: cyan (0–30 d), amber (31–60 d), magenta (61–90 d), red-alert (90+ d). Small caps counters inside each segment. Subtle scan-sweep animation across the strip.
- **Wireframe:**
```
┌─────────────────────────────────────┐
│  PRE-AUTH LANES                 [?] │
├─────────────────────────────────────┤
│  D0150 [████░░░░░░░░]  4 total      │
│  D0220 [░░░░░░]  0                  │
│  D4341 [██░░░░░░░░░░]  2            │
│  D2740 [░░░░░░░░░░░░]  0            │
│  D1110 [████████░░░░]  6            │
└─────────────────────────────────────┘
```

### W-06 — Unapplied Credit Float Strip (MUST · Effort XS)
- **Why great:** Unallocated payments hide real A/R; this exposes floating money that should be applied or refunded.  
  **Page(s):** A/R.  
  **Data source:** SoftDent payment export (unapplied amount, patient ID).  
  **Honesty:** Hides completely when zero unapplied; shows amber “No unapplied credits” pill when import missing.
- **Look:** Full-width short strip (~80 px). Left: cyan label “UNAPPLIED CREDITS.” Center: flowing row of amber pills, each containing anonymized “Patient A: $—.” Right: cyan total sum. Horizontal scroll on overflow. Corner brackets at ends; phosphor glow on pills.
- **Wireframe:**
```
┌─────────────────────────────────────────────────────────────┐
│  UNAPPLIED FLOAT  [Patient A: $—] [Patient B: $—] [Pat...]  │
│  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓  │
│                                        Total: $—            │
└─────────────────────────────────────────────────────────────┘
```

### W-07 — Cash Flow Bridge Waterfall (SHOULD · Effort M)
- **Why great:** Distinct from EBITDA waterfall—this tracks *liquidity* (operating cash + expected collections − overhead − debt service = projected cash). Critical for payroll timing.  
  **Page(s):** Financial.  
  **Data source:** QB cash balance + A/R aging projection + QB payables.  
  **Honesty:** “Cash projection unavailable” grays out intermediate bars; shows starting balance only.
- **Look:** Vertical waterfall. Starting bar (cyan) full height. Floating bars: cyan upward (collections), magenta downward (payroll, overhead, loans). Connector lines between bars. Ending bar (amber) shows projected cash. Faint horizontal grid lines.
- **Wireframe:**
```
┌─────────────────────────────────────┐
│  CASH FLOW BRIDGE — 30 DAY        ↗ │
├─────────────────────────────────────┤
│         ┌───┐                       │
│  Start  │███│ $—                    │
│    +    │ ↑ │                       │
│  Coll   │███│ $—                    │
│    -    │ ↓ │                       │
│  OH     │███│ $—                    │
│    -    │ ↓ │                       │
│  Loan   │███│ $—                    │
│    =    │   │                       │
│  Project│███│ $—                    │
└─────────────────────────────────────┘
```

### W-08 — Insurance Verification Matrix (SHOULD · Effort S)
- **Why great:** Prevents front-desk surprises and eligibility-related denials.  
  **Page(s):** Claims, Office Manager.  
  **Data source:** SoftDent appointment export + verification status flags (eligibility, benefits, breakdown).  
  **Honesty:** “Verification tracking disabled” when field missing; matrix shows all gray dots.
- **Look:** Compact grid (6 rows × 3 columns). Rows: anonymized “Patient A,” “Patient B,” etc. Columns: Elig, Ben, Breakdown. Status dots: cyan (verified), amber (pending), magenta (failed), gray (unknown). “View All” expansion button in cyan.
- **Wireframe:**
```
┌─────────────────────────────────────┐
│  VERIFICATION MATRIX — NEXT 3D    ↻ │
├─────────────────────────────────────┤
│  Patient    Elig  Ben  Breakdown    │
│  ─────────────────────────────────  │
│  Patient A   ●     ●      ○         │
│  Patient B   ●     ○      ○         │
│  Patient C   ●     ●      ●         │
│  Patient D   ○     ○      ○         │
│                                   │
│  ●Verified ○Pending ◉Failed         │
└─────────────────────────────────────┘
```

### W-09 — Operatory Status Board (MUST · Effort M)
- **Why great:** Real-time command center for chair turnover and hygiene coordination; reduces “where is the patient?” friction.  
  **Page(s):** Office Manager.  
  **Data source:** SoftDent schedule (operatory, appointment time, status, procedure).  
  **Honesty:** “Schedule sync stale [timestamp]” when import old; cards fade to gray with last known state.
- **Look:** Grid of cards (2×2 or 3×2). Each card: header (HYG1, OP1, etc.), status bar (cyan=available, magenta=occupied, amber=turnover), anonymized initials “P.A.,” procedure code “D—,” countdown “— min.” Active cards pulse with phosphor glow.
- **Wireframe:**
```
┌─────────────────────────────────────┐
│  OPERATORY STATUS BOARD           ↻ │
├─────────────────────────────────────┤
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐  │
│  │HYG1 │ │ OP1 │ │ OP2 │ │ OP3 │  │
│  │ ●   │ │ █   │ │ ▲   │ │ ●   │  │
│  │P.A. │ │P.B. │ │P.C. │ │     │  │
│  │D—   │ │D—   │ │D—   │ │     │  │
│  │25min│ │10min│ │DONE │ │     │  │
│  └─────┘ └─────┘ └─────┘ └─────┘  │
│  ●Avail █Occ ▲Turnover              │
└─────────────────────────────────────┘
```

### W-10 — Recall Compliance Gauge (MUST · Effort S)
- **Why great:** Hygiene reactivation drives 70 % of dental revenue; this gamifies the recall chase.  
  **Page(s):** Office Manager.  
  **Data source:** SoftDent recall report (due patients, contacted, scheduled).  
  **Honesty:** Gray empty arc with “Recall data unavailable” when missing; center shows `—%`.
- **Look:** Radial gauge (270° arc). Background track navy; fill gradient shifts cyan→magenta as percentage rises. Large amber numerals “—%” in center. Ticks at 25/50/75/90. Below: mini KPIs “Due: — | Scheduled: —” in cyan.
- **Wireframe:**
```
┌─────────────────────────────────────┐
│  RECALL COMPLIANCE GAUGE        [?] │
├─────────────────────────────────────┤
│         ╭──────────╮                │
│        ╱    —%     ╲               │
│       │    ░░░░     │              │
│       │    ░░░░     │              │
│        ╲    ▓▓▓▓   ╱               │
│         ╰────┬─────╯                │
│    Due: —   Target: 80%  Sch: —     │
└─────────────────────────────────────┘
```

---

## 3. Gallery Summary (one-line look per widget)

| Widget | One-Line Visual |
|--------|-----------------|
| **W-01 Expense Treemap** | Nested cyan-bordered rectangles sized by spend, amber labels, magenta outliers. |
| **W-02 Procedure Scatter** | Canvas X-Y plot with cyan/amber/magenta dots, quadrant lines, laser crosshair. |
| **W-03 Denial Pareto** | Descending cyan bars with amber cumulative line, magenta 80 % threshold. |
| **W-04 Treatment Pipeline** | Vertical narrowing funnel with trapezoid stages and magenta conversion % badges. |
| **W-05 Pre-Auth Lanes** | Horizontal segmented bars cyan→amber→magenta showing pre-auth age buckets. |
| **W-06 Unapplied Float Strip** | Full-width strip with flowing amber patient pills and cyan total. |
| **W-07 Cash Bridge** | Vertical waterfall cyan/magenta floating bars with amber projected endpoint. |
| **W-08 Verification Matrix** | Dot-grid status board: cyan verified, amber pending, magenta failed. |
| **W-09 Operatory Board** | Card grid with phosphor-glow occupancy indicators and countdown timers. |
| **W-10 Recall Gauge** | 270° radial arc gradient fill with large amber center percentage. |

---

## 4. Implementation Phases (DO NOT APPLY until approve)

**Phase 1 (XS/S — Quick Wins):**  
- W-06 Unapplied Credit Float Strip (XS)  
- W-03 Denial Pareto (S)  
- W-05 Pre-Auth Aging Lanes (S)  
- W-08 Verification Matrix (S)  
- W-10 Recall Compliance Gauge (S)  

**Phase 2 (M — Core Value):**  
- W-04 Treatment Plan Conversion Pipeline (M)  
- W-09 Operatory Status Board (M)  
- W-01 Expense Category Treemap (M)  
- W-02 Procedure Profitability Scatter (M)  
- W-07 Cash Flow Bridge Waterfall (M)  

**Approval required for:** Export schema confirmation (pre-auth, recall, verification flags) from SoftDent before Phase 2 widgets can populate honestly.

---

## 5. Risks & Rollback

- **Data Dependency Risk:** W-04, W-05, W-08, W-09, W-10 require specific SoftDent exports (treatment plan status, pre-auth dates, verification flags, recall due dates) that may not be in current `hal-10441` import bundles. If exports are missing, widgets will render honest empty states but may consume layout space.  
- **PHI Leakage Risk:** W-06 and W-08 display patient identifiers (anonymized in mocks, but real implementation must hash IDs). Ensure pills in W-06 show only first initial/last initial or patient ID hash, not full names.  
- **Performance Risk:** W-02 (scatter) and W-01 (treemap) can be heavy on large SoftDent/QB extracts — cap point/node counts and virtualize or aggregate beyond ~500 rows.
- **Layout Risk:** New instruments can push Financial / Office Manager toward vertical warehouse obesity — prefer strip/s slots and collapsible empty states.
- **Rollback:** Feature-flag each new `type` in page packs; remove from mosaic specs to hide instantly without schema migration. No invented dollars if imports are incomplete.

**Status:** CONSULT ONLY — awaiting operator approve / proceed before any coding.