# Moonshot AI — Compact Professional Pages (CONSULT ONLY)

**Date:** 2026-07-11  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Build reviewed:** hal-10502  
**Script:** `scripts/run_moonshot_compact_professional_pages_consult.py`  
**Apply:** DO NOT APPLY / DO NOT CODE until operator approves.

## Operator request (verbatim)

> as an expert software enginer ask moonshot ai all pages are unorganized, huge widgets that wobble, how wold he compact the pages so that we shouldn't have to scroll  down and make all the pages look compact, highly profressional

---

# Verdict  
Your Apex Bridge suffers from "warehouse obesity"—pages still default to legacy `l/xl/full` instrument stacks (300px+ monuments) while motion CSS (`apexBreathe`, hover `translateY(-3px) scale(1.015)`, enter stagger) creates optical wobble on large surfaces. The Financial page already uses the strip-console pattern (hal-10450); the remaining nine pages do not, leaving empty widgets as towering voids and viable data buried below the fold. Remediation requires global motion suppression, aggressive widget-size discipline (xs→m for first viewport), and extending the Financial empty-collapse pattern to Taxes, SoftDent, QuickBooks, A/R, Claims, Narratives, Documents, Library, Office Manager, and HAL.

## 0. Operator Intent (quote; confirm consult-only)

> "as an expert software enginer ask moonshot ai all pages are unorganized, huge widgets that wobble, how wold he compact the pages so that we shouldn't have to scroll down and make all the pages look compact, highly profressional"

**Confirmed CONSULT-ONLY.** No CSS, JS, or Python will be generated, committed, or applied to build `hal-10502` until you explicitly respond with "approve," "proceed," or "do it" for a specific phase. This is a design-system prescription only.

## 1. Diagnosis — Why Pages Feel Huge / Unorganized / Wobbly

**Evidence from tokens and bridge CSS:**

| Symptom | Root Cause | Location in Code |
|---------|------------|------------------|
| **Huge widgets** | Default instrument size classes (`l`, `xl`, `full`) with `min-height: 180px`+ and `minmax(300px, 1fr)` mosaic columns create 300px+ monuments. | `apex-bridge.css` `--mosaic-col: 300px`; inline instrument defs |
| **Vertical warehouse** | Full-width shelves (`import-freshness`, `financial-period-scrubber`, `page-title-block`) stack 160px+ before first KPI. | Page JSON layout arrays |
| **Empty monuments** | Non-Financial pages lack the "empty-collapse" strip logic; empty `payer-donut`-like widgets render as 300px "No data" tombstones. | `apex_backend.py` page builders (Taxes, QB, etc.) |
| **Wobble / motion noise** | `apexBreathe` (infinite opacity 0.75→1) runs on static text; hover `translateY(-3px) scale(1.015)` lifts large cards dramatically; `apexEnter` staggers `translateY(10px)` across 10+ widgets; ambient `apexSweep` and `halPulse` compete for attention. | `apex-tokens.css` `@keyframes apexBreathe`; `apex-chrome-flash.css` `.apex-inst:hover` transform; `apexEnter` stagger delays |
| **Unorganized hierarchy** | No consistent "command surface" contract: some pages open with a chart, others with a scrubber, others with a wall of text. | Ad-hoc page construction pre-hal-10450 |

**Why this feels unprofessional:** Large empty containers signal broken data pipelines rather than honest transient states; excessive motion suggests instability; lack of a consistent first-viewport "cockpit" forces operators to hunt below the fold for primary actions.

## 2. Compact Professional Design System (target density rules)

**Instrument Size Discipline (strict):**

| Size | Height | Use Case | First Viewport Limit |
|------|--------|----------|---------------------|
| **xs** | 60px | Chips, status LEDs, KPI micro-cards | Unlimited in strips |
| **s** | 100px | Sparklines, mini-donuts, alert summaries | Max 4 |
| **m** | 140px | Standard charts, tables (5–7 rows) | Max 2 |
| **l** | 200px | Dense charts, tall tables | Max 1 (below fold only) |
| **xl** | 280px | Waterfalls, multi-series trends | **Forbidden** in first viewport |
| **full** | 60–80px | **Strips only** (composite rows, never tall shelves) | Max 1 (top) |

**Grid & Spacing:**
- **Gap:** Reduce `--mosaic-gap` from `10px` → `6px` (dense but not cramped).
- **Min column:** Enforce `--apex-widget-min: 140px` universally; override `300px` legacy in `apex-bridge.css`.
- **First viewport contract:**  
  1. **Strip 1 (60px):** Import health + Period/Brief composite.  
  2. **Strip 2 (60–80px):** 3–4 KPI micro-cards (production, collections, A/R, alerts).  
  3. **Primary (m/l, 140–200px):** One dominant chart or table.  
  4. **Action row (40px):** Buttons/links.  
  **Total ≤ 380px**, fitting 1080p minus ticker/header (~100px).

**Empty-State Honesty:**
- Empty `l/xl` instruments **must** collapse to `xs` chips (height 60px) with text:  
  *"{Widget Name} — awaiting [Specific Import]"*  
  Never render 300px placeholder graphics.

**Typography Scale (tighten):**
- Page titles: 16px (currently 18–20px).
- Widget headers: 11px uppercase (keep).
- KPI values: 24px (keep) but line-height 1.1.
- Body: 12px (reduce from 13px for density).

## 3. Page-by-Page Compaction Map

| Page | Current Problem | Target First Viewport | Move/Collapse | Effort |
|------|----------------|----------------------|---------------|--------|
| **Financial** | Already strip-based; may still have `xl` EBITDA waterfall visible | Keep: Strip 1 (status) + KPI row + `m` trend | Move EBITDA waterfall to collapsible "Station" below fold; ensure empty payer/collections collapse to chips | XS |
| **Taxes** | Likely full-width entity list + large calendar widget | Strip: Entity selector (xs) + Filing status chips + Tax year scrubber (xs) | Move `workpapers` table to subpage `/taxes/workpapers`; calendar collapses to `s` mini-month | S |
| **SoftDent** | Import freshness shelf (full) + large register preview | Strip: Import health (xs) + Last sync chip + Action buttons | Move `register` detail to `/softdent/register`; schedule preview → `s` timeline strip | S |
| **QuickBooks** | Large P&L waterfall (xl) + COA table (l) | Strip: Connection status + Last import chip + Chart type toggle | Move P&L to `m` sparkline; full COA behind `/quickbooks/coa`; expense bars `s` | S |
| **A/R** | A/R aging chart (l) + large scrubber | Strip: Aging summary (3 chips: 0-30, 31-60, 90+) + Efficiency bullet | Aging detail table → `/ar/aging-detail`; chart stays as `m` horizontal bar | S |
| **Claims** | Kanban board (full height) + status counts | Strip: Volume KPI + Match rate + Aging alert | Kanban remains but constrained to `l` max height; status distribution bar `s` above it | M |
| **Narratives** | Large template list (l) + editor (xl) | Strip: Template count + Last edited + New button | Template grid → `m` cards; editor full-screen modal or below fold | M |
| **Documents** | File tree (xl) + preview pane | Strip: Storage used + Upload button + Filter chips | Tree → `m` compact list; preview → modal | S |
| **Library** | Code reference tables (l) | Strip: Search + Category chips | Tables → `m` density (12px font, 6px padding) | XS |
| **Office Manager** | Operatory chairs (l) + task list (l) | Strip: Chair utilization sparklines (xs × 4) + Task count | Detailed chair view → `/office-manager/operatory`; tasks collapsible `s` | S |
| **HAL** | Chat rail (narrowed) + large history table | Strip: Model status + Context tokens + Clear button | History → `/hal/history`; logs → `/hal/system-logs`; chat remains dominant `m` | XS |

## 4. Kill the Wobble — Motion Remediation

**Disable / Soften:**

| Animation | Current | Remediation | Rationale |
|-----------|---------|-------------|-----------|
| `apexBreathe` | Infinite 0.75→1 opacity ease-in-out | **Remove** from static widgets; reserve for **loading skeletons only** (3s max). | Breathing large surfaces feels like instability. |
| Hover lift | `translateY(-3px) scale(1.015)` | Reduce to `translateY(-1px)` **or** remove transform, use `border-color: var(--apex-cyan)` only. | Large cards "floating" induce seasickness. |
| `apexEnter` | `translateY(10px)` + stagger 50ms×N | Reduce to `translateY(4px)`, stagger max 3 items, total duration ≤200ms; respect `prefers-reduced-motion`. | Staggered waterfall entrance feels wobbly on reload. |
| `apexSweep` (background) | 8s linear infinite | **Gate behind** `body.apex-ambient-enabled` class; default off. | Chrome sweep distracts from data. |
| `halPulse` | 2s infinite | Keep for HAL orb only; **remove** from alert LEDs (use static color). | Pulsing alerts create anxiety. |
| `apexGlitch` | 0.15s on `.active` | Keep for rare error states only; **remove** from page titles on load. | Glitch on every nav feels like broken render. |

**Preserve (Intentional Presence):**
- Subtle border glow on hover (static, no motion).
- Ticker scroll (inherent to function).
- Toast enter/exit (short, purposeful).

**Implementation:** Add comprehensive `@media (prefers-reduced-motion: reduce)` blocks that zero all transforms and opacities for users who need it.

## 5. Recommendations — MUST / SHOULD / NICE

| ID | Rank | Recommendation | Why | Effort | Depends on |
|----|------|----------------|-----|--------|------------|
| **M-1** | **MUST** | **Global motion suppression:** Remove `apexBreathe` from widgets, reduce hover lift to 1px or border-only, gate sweep/glitch. | Stops wobble immediately; pure CSS. | XS | None |
| **M-2** | **MUST** | **Extend empty-collapse pattern:** Apply Financial strip logic to Taxes, SoftDent, QB, A/R, Claims, etc. Empty `l/xl` → `xs` chip. | Eliminates empty monuments. | S | M-1 |
| **M-3** | **MUST** | **Enforce first-viewport contract:** No `xl` or `full` (tall) instruments above fold; max 1 `l` chart. | Guarantees no scroll for primary actions. | S | M-2 |
| **S-1** | **SHOULD** | **Tighten grid:** Reduce `--mosaic-gap` to 6px, enforce `--apex-widget-min: 140px`, reduce font to 12px. | Increases density without clutter. | XS | M-1 |
| **S-2** | **SHOULD** | **Subpage migration:** Move all tables >5 rows and config forms to drill-down subpages (see map). | Keeps primary surfaces command-oriented. | M | M-3 |
| **S-3** | **SHOULD** | **Strip composite components:** Build reusable `ApexStrip` container (60px) for KPI+status+actions. | Consistency across pages. | S | M-3 |
| **N-1** | **NICE** | **Density mode toggle:** "Compact / Comfortable" switch in header (persists to localStorage). | Operator preference without code changes. | M | S-1 |
| **N-2** | **NICE** | **Keyboard nav:** `j/k` or `↑/↓` to move between strips; `Enter` to expand. | Professional power-user feature. | M | S-2 |

## 6. Suggested Fix Order (phases) + Validation Gates

**Phase 1: Motion Kill (CSS-only, hal-10510)**
- Edit `apex-tokens.css`, `apex-chrome-flash.css`: disable breathe, soften hover, gate sweep/glitch.
- **Validation:** Load any page; widgets do not "breathe"; hover feels solid; no background sweep on default.

**Phase 2: Empty Collapse Extension (hal-10520)**
- Update page builders (Taxes, SoftDent, QB, A/R, Claims, Narratives, Documents, Library, Office Manager): empty `l/xl` → `xs` chip with specific import name.
- **Validation:** Open SoftDent page with no imports; observe 60px chip "Register — awaiting SoftDent export" instead of 300px void.

**Phase 3: Size Discipline & Grid Tighten (hal-10530)**
- Reduce `--mosaic-gap` to 6px; audit all instruments on all pages, downsize `xl→l`, `l→m` for first viewport; migrate tall shelves to strips.
- **Validation:** At 1920×1080, Financial/Taxes/SoftDent pages show KPI strip + primary chart + actions without scrolling.

**Phase 4: Subpage Migration (hal-10540)**
- Move large tables/forms to subpages per map; replace with compact `s` summary strips.
- **Validation:** Office Manager page shows 4 operatory sparklines + task count chip; detail opens in `/office-manager/operatory` subpage.

**Phase 5: Polish & Preference (hal-10550)**
- Add density toggle, keyboard nav, finalize reduced-motion media queries.
- **Validation:** Toggle "Comfortable" restores 10px gaps; "Compact" is default; reduced-motion OS setting disables all transforms.

**Stop gates:** If Phase 1 feels "dead" rather than "stable," we can re-enable subtle border glows. If Phase 3 breaks mobile (if ever deployed), we revert to 8px gaps.

## 7. Risks, Honesty, Rollback

- **Honesty violation risk:** Collapsing empty widgets to chips is safe; resizing populated widgets risks truncating data. We will use `overflow: auto` on `m` containers to prevent clipping.
- **Motion accessibility:** Phase 1 must include `prefers-reduced-motion` to avoid vestibular issues.
- **Rollback:** All changes are additive CSS/JSON; rolling back means reverting to `hal-10502` CSS files and page layouts. No database migration required.

**DO NOT APPLY until you explicitly approve a phase.** Confirm which phase to proceed with, or request adjustments to the density rules.