# Moonshot AI — Financial Pro Presentation + Program/HAL Review (CONSULT ONLY)

**Date:** 2026-07-10  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Build reviewed:** hal-10420  
**Script:** `scripts/run_moonshot_financial_pro_presentation_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> ask moonshot ai to look at my financial page.  i have 3 large widgets with nothgin in them. can he recommend a better more professional design and have him look over the program and hal.  the widgets are not being importated with data.

---

# Verdict

## 0. Operator Intent (quote; consult-only)

> "ask moonshot ai to look at my financial page. i have 3 large widgets with nothgin in them. can he recommend a better more professional design and have him look over the program and hal. the widgets are not being importated with data."

**Confirmed:** Consult-only professional Financial redesign. No code will be generated or applied until operator explicitly approves a specific option.

---

## 1. Critique of Current Financial Page Layout

**The Problem with "Warehouse of Large Instruments"**

The current Financial page (hal-10420) stacks **nine large-or-full-width instruments** vertically, creating severe visual obesity:

*   **Import/Scrubber Duopoly:** Two `size: "full"` shelves (`import-freshness`, `financial-period-scrubber`) consume 160px+ height before any financial data appears.
*   **The Empty Monument Problem:** `payer-donut` (l), `ins-patient-split` (l), and `collections-mtd` (default but visually dominant) render as large empty vessels with "No data" tombstones. This signals "broken system" to an executive user rather than "awaiting import."
*   **EBITDA Sprawl:** Three separate large widgets (`ebitda-waterfall` xl, `ebitda-scrubber` full, `ebitda-trend` l) scatter the valuation story across excessive vertical real estate.
*   **Low Information Density:** `provider-hbar` (l) renders as a thinly populated horizontal bar chart with excessive padding; `liquidity-pulse` (l) stands alone when it should contextualize production.

**Why this feels unprofessional:** It resembles a developer dashboard ("widget dump") rather than a curated financial command center. Large empty containers dominate the viewport, suggesting data pipeline failure rather than honest transient states.

---

## 2. Why Widgets Are Empty — Import / Data Root Cause

Map each empty LARGE widget to missing SoftDent/QB field or honesty gate:

| Widget ID | Size | Empty Root Cause | Specific Missing Import | HAL Diagnostic |
|-----------|------|------------------|------------------------|----------------|
| **collections-mtd** | default (appears large when empty) | SoftDent latest period has `collectionsPending: true` | **SoftDent Collections/Daysheet export** for the MTD period not promoted to NR2 inbox. Register export alone shows production but not collections split. | "Collections pending for latest SoftDent period — not reported as $0. Sync SoftDent collections/daysheet export." |
| **payer-donut** | l | No payer classification | **SoftDent Claims export** lacks `Payer`/`Carrier`/`Insurance` field population, OR claims import contains only one carrier (monopoly). OR Register shows all charges under single "Insurance Plan" bucket. | "Need SoftDent claims with Payer, or a real insurance/patient split (both sides > 0). Register Ins Plan $0 / all-patient dumps stay empty." |
| **ins-patient-split** | l | Collections pending = no real split | Same as collections-mtd: **Collections/Daysheet export** missing. SoftDent Register exports show insurance vs patient as $0 / all-patient when collections are not yet reported. Honesty gate prevents displaying misleading 0%/100% splits. | "SoftDent latest period has collectionsPending — insurance/patient stay empty until collections export reports a real split." |
| **prod-trend** | default | Sparse historical data | **SoftDent Dashboard exports** for multiple periods not loaded. Single period import cannot render trend. | "Last periods from SoftDent dashboard import." |

**Ground Truth:** The Financial page is import-healthy for Production and A/R (17/21 widgets populated), but the **Collections/Daysheet export pipeline is stalled** (July 2026 period gap identified in previous consult). Until `C:\SoftDentReportExports` contains the Collections report (not just Register) for the current period, the three "split" widgets (collections-mtd, ins-patient-split) and payer-mix derivatives will remain empty per the honesty architecture.

---

## 3. Recommended Professional Financial Presentation (primary design)

**Pattern: Financial Executive Console** (analogous to Claims Executive RCM Console)

**Design Principles:**
1.  **Strip Architecture:** Replace full-width warehouse shelves with **60-80px high command strips** that composite multiple instruments.
2.  **Conditional Density:** Large widgets (`l`, `xl`) collapse to **compact "awaiting data" chips** when empty, rather than rendering 300px empty containers.
3.  **Contextual Grouping:** Merge related metrics (Production/Collections/A/R) into **mosaic pairs** rather than isolated monoliths.
4.  **EBITDA Integration:** Consolidate waterfall, scrubber, and trend into a single **collapsible EBITDA Command Station**.

**Layout Hierarchy:**

*   **Strip 1: Command Status (Full, 60px)** — Composite of Import Health + Period Selector + Morning Brief.
*   **Strip 2: Vital Signs (3-column, medium)** — Production MTD | Collections MTD (with "Pending" chip if empty) | A/R Outstanding.
*   **Strip 3: Velocity & Provider (Large, split)** — Production Trend (sparkline) + Provider Production (horizontal bars) side-by-side. Provider panel collapses if <2 providers.
*   **Strip 4: Revenue Composition (Large, conditional)** — Insurance vs Patient split (stacked bar) + Payer Mix (mini-donut or list). When empty, renders as compact HAL action card: "Import Collections/Daysheet to reveal payer mix."
*   **Strip 5: A/R Analysis (Full, compact)** — A/R Aging horizontal bar chart + Collection Efficiency bullet (small) inline.
*   **Strip 6: EBITDA Command Station (Full, collapsible)** — Waterfall (primary) with scrubber controls docked below; trend as mini-sparkline header. Shows compact "Import QB P&L" prompt if `netIncome` missing.

---

## 4. Wireframe (text) — first viewport + below-fold

```
[FINANCIAL PAGE — Executive Console Layout]

VIEWPORT 1 (0-900px)
┌─────────────────────────────────────────────────────────────────┐
│ 🔵 SoftDent+QB sync 19m ago  ▼ Period: 2026-07  [Refresh]  ⚡ Brief: Imports ready · 1 missing │  <-- Strip 1 (Composite)
├──────────────┬──────────────┬──────────────┬────────────────────┤
│ Production   │ Collections  │ A/R Outstanding │ Efficiency    │
│ $47,200      │ ⏳ Pending   │ $12,400      │ 89% ▰▰▰▰▱     │  <-- Strip 2 (Vital Signs)
│ ▃▃▅▇▃▃▃      │ (sync SD)    │ 90+: 12%     │ vs target 85%  │
├──────────────────────────────┬──────────────────────────────────┤
│ Production Trend (6mo)       │ Provider Production              │
│ ▁▃▅▇▆▃  [avg $44k]           │ Dr. Smith  ████████████ $32k     │  <-- Strip 3 (Velocity)
│                              │ Dr. Jones  ██████ $18k           │
│                              │ [collapses to 40px if 0-1 prov]  │
├──────────────────────────────┴──────────────────────────────────┤
│ Revenue Composition                                             │
│ [Insurance ████████████████████ $28k]  [Payer Mix]              │  <-- Strip 4 (Conditional)
│ [Patient   ████████████ $19k]         Delta Dental ████ 45%     │
│                                        Cigna      ██ 23%        │
│ [If empty: "Awaiting Collections Export ▶ Sync Now" (compact)] │
├─────────────────────────────────────────────────────────────────┤
│ A/R Aging                    │ Collection Efficiency Bullet      │  <-- Strip 5 (A/R)
│ Current  ████████ $8k        │ Actual ▰▰▰▰▰▰▰▱▱ 89%             │
│ 31-60    ███ $3k             │ Target ▰▰▰▰▰▰▰▰▱ 85%             │
│ 61-90    ██ $1.2k            │                                   │
│ 90+      █ $0.8k             │                                   │
└─────────────────────────────────────────────────────────────────┘

BELOW FOLD (scroll)
┌─────────────────────────────────────────────────────────────────┐
│ EBITDA Management (Management Calculation — CPA Review Advised) │  <-- Strip 6 (EBITDA Station)
│ ┌─────────────────────────────────────────────────────────┐    │
│ │ Net Income ██████████████████████████████████████ $X    │    │
│ │ + Interest  ███████ $X                                  │    │
│ │ + Tax       ██████ $X                                   │    │
│ │ + Deprec    ░░░░░░ [enter QB data]                      │    │
│ │ = EBITDA    █████████████████████████████████████████ $X│    │
│ └─────────────────────────────────────────────────────────┘    │
│ [Scrubber: Interest ▓▓▓▓▓▓▓▓░░ Tax ▓▓▓▓▓▓░░░░ Deprec ░░░░░░] │
│ Trend: ▃▃▅▇▆▃ (6mo)                                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Widget / Instrument Spec (CONSULT ONLY)

**Composite Strip 1: Financial Command Status**
```json
{
  "id": "financial-command-strip",
  "type": "composite-strip",
  "size": "full",
  "height": "compact",
  "components": [
    {"type": "import-health-chip", "source": "diagnostics.summary"},
    {"type": "period-selector", "source": "financial_reports.periods"},
    {"type": "morning-brief-text", "source": "bundle.diagnostics"}
  ],
  "replaces": ["import-freshness", "financial-period-scrubber", "morning-brief"]
}
```

**Vital Signs Mosaic (3-up)**
```json
{
  "id": "vital-signs-row",
  "type": "mosaic-row",
  "size": "full",
  "children": [
    {"id": "prod-mtd", "type": "kpi-spark", "size": "m", "source": "softdent.dashboard.production"},
    {"id": "collections-mtd", "type": "kpi-spark", "size": "m", "source": "softdent.dashboard.collections", "emptyBehavior": "chip-pending"},
    {"id": "ar-outstanding", "type": "kpi-badge", "size": "m", "source": "softdent.arAging"}
  ]
}
```

**Conditional Revenue Composition (Large)**
```json
{
  "id": "revenue-composition",
  "type": "conditional-split",
  "size": "l",
  "condition": "hasRealSplit(bundle)",
  "ifTrue": {
    "layout": "side-by-side",
    "left": {"type": "stacked-bar", "id": "ins-patient-split"},
    "right": {"type": "mini-donut", "id": "payer-donut"}
  },
  "ifFalse": {
    "layout": "compact-action-card",
    "message": "Collections/Daysheet export needed for revenue split",
    "halAction": "refresh_softdent_period",
    "height": "80px"
  }
}
```

**EBITDA Command Station (Collapsible)**
```json
{
  "id": "ebitda-station",
  "type": "composite-full",
  "size": "full",
  "primary": {"id": "ebitda-waterfall", "type": "waterfall", "size": "xl"},
  "controls": {"id": "ebitda-scrubber", "type": "scrubber-bar", "dock": "bottom"},
  "header": {"id": "ebitda-trend", "type": "mini-sparkline", "context": "6mo"}
}
```

---

## 6. Program + HAL Review

**Strengths (maintain):**
- **Data Honesty Architecture:** Empty widgets correctly refuse to invent dollars; hints accurately point to missing SoftDent exports.
- **Tax/EBITDA Engine:** `tax_engine.compute_ebitda_walk` provides management EBITDA with proper add-backs; citation system links to QB line items.
- **HAL Board Actions:** Existing actions (`sync_imports`, `refresh_softdent_period`, `focus_widget`) provide deterministic control.
- **Provider Horizontal Bars:** Correctly aggregates SoftDent procedure production by provider when export contains breakdown.

**Gaps / Ranked Improvements:**

| ID | Rank | Area | Gap | HAL/Program Action |
|----|------|------|-----|-------------------|
| **FIN-001** | **MUST** | Import Pipeline | **Collections/Daysheet export gap** blocking 4 widgets. SoftDent CLI auto-export disabled; July 2026 period missing collections data. | HAL proactive alert: "Collections export >7 days stale. Action: Export SoftDent Collections/Daysheet for [current period]." |
| **FIN-002** | **MUST** | Widget Architecture | Large empty containers (`payer-donut`, `ins-patient-split`) render as 300px tombstones. | Implement **conditional collapse**: when `status: "empty"` and `size: "l"`, render compact 60px action card instead of full container. |
| **FIN-003** | **MUST** | Layout | Duplicate full-width strips (`import-freshness` + `financial-period-scrubber`) create header obesity. | Merge into **Composite Strip** (see spec above); reduce vertical chrome by 60%. |
| **FIN-004** | **SHOULD** | HAL Proactivity | HAL currently reactive; does not surface financial data gaps until operator asks. | **Morning Financial Brief**: HAL-generated summary on page load: "Production reported. Collections pending. A/R $12k (90+ $800). Action: Sync Collections export." |
| **FIN-005** | **SHOULD** | EBITDA | Depreciation add-back requires manual entry; QB import may not capture fixed assets. | HAL suggestion: "Import QB Fixed Asset Report for depreciation add-back" when `missing: ["Depreciation"]` detected. |
| **FIN-006** | **NICE** | Visualization | `liquidity-pulse` and `prod-trend` are separate large widgets. | Merge into **Dual-Axis Trend Strip**: production line (solid) vs collections line (dashed) in single canvas. |
| **FIN-007** | **NICE** | SoftDent Integration | No real-time SoftDent status check; operator only knows export failed when widgets stay empty. | HAL **Import Health Ping**: Verify `C:\SoftDentReportExports` timestamp <24h on app launch; warn if stale. |

---

## 7. Alternatives (2 options) ranked

**Option A: "Executive Console" (Recommended)**
- **Approach:** Composite strips, conditional collapse for empty large widgets, dense mosaic layout.
- **Pros:** Solves visual obesity immediately; honest empty states don't dominate; scales gracefully when imports arrive.
- **Cons:** Requires refactoring widget container logic to support conditional sizing.
- **Effort:** Medium (3-4 days).

**Option B: "Minimalist Single Column"**
- **Approach:** Keep large widgets but stack them in strict priority order (Production → Collections → A/R → EBITDA), with aggressive height reduction (max 150px per widget).
- **Pros:** Minimal code change; simply reorder and cap heights.
- **Cons:** Still wastes viewport on empty containers; does not solve the "3 large empty widgets" pain point, merely pushes them down.
- **Effort:** Low (1 day).

**Ranking:** Option A is **MUST** for professional presentation; Option B is **NICE** as temporary band-aid.

---

## 8. Phases + Validation Gate

**Phase 1: Import Diagnosis (T0)**
- Verify `C:\SoftDentReportExports` contains Collections/Daysheet for 2026-07.
- Confirm SoftDent Claims export includes `Payer` field population.
- **Gate:** Operator confirms files present and promoted; widgets populate or remain empty per honesty rules.

**Phase 2: Layout Redesign (T1) — CONSULT APPROVAL REQUIRED**
- Implement Composite Strip 1 (merge import-freshness + period-scrubber + morning-brief).
- Implement conditional collapse for `payer-donut` and `ins-patient-split` (compact 60px card when empty).
- Reorder Vital Signs row to top of viewport.
- **Gate:** Operator approves wireframe; no code written until explicit "proceed."

**Phase 3: HAL Proactivity (T2)**
- Add HAL "Morning Financial Brief" generation.
- Add proactive alert for stale Collections export.
- **Gate:** HAL responses validated against actual import states.

**Phase 4: EBITDA Consolidation (T3)**
- Merge waterfall/scrubber/trend into Command Station.
- **Gate:** EBITDA calculations verified against QB P&L.

---

## 9. Risks & Rollback

| Risk | Mitigation | Rollback |
|------|-----------|----------|
| **Conditional collapse hides critical empty states** | Maintain hint text and HAL action button in compact mode; never hide completely. | Revert to full-size empty containers via feature flag. |
| **Composite strip loses granularity** | Retain individual widget IDs in background for HAL targeting; composite is presentation-only. | Split back to separate widgets if HAL focus commands fail. |
| **SoftDent export format changes** | Maintain existing parsers; new layout is presentation layer only. | Rollback to hal-10420 widget definitions; data layer unchanged. |
| **Operator prefers large widgets when data arrives** | Conditional expansion: when data present, large widgets render at full size. | Static sizing config in `nr2-config.json`. |

**DO NOT APPLY until operator approves.**