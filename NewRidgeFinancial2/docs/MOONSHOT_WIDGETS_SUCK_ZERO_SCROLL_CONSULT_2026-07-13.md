# Moonshot AI — Widgets suck / zero-scroll swap (CONSULT ONLY)

**Date:** 2026-07-13
**Model:** `kimi-k2.5`
**Key:** OPENROUTER_API_KEY
**Build:** hal-10611
**Script:** `scripts/run_moonshot_widgets_suck_zero_scroll_consult.py`
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> tell moonshot these widgets suck and like poor - without breaking the program ask if all the widgets can be changed out and compacted so i do not have to scroll down the page

---

# Verdict
**PARTIAL** — We can zero-scroll the *interface* by compacting the widget *primitives* and collapsing empties, but we **cannot** fit 178 widgets above the fold; 70% must be demoted to subpages/drawers or the program breaks from information overload.

## 0. Operator Intent (verbatim; confirm consult-only)
> "tell moonshot these widgets suck and like poor - without breaking the program ask if all the widgets can be changed out and compacted so i do not have to scroll down the page"

**Confirm:** Consult-only. No code applied. No SoftDent dollars invented.

## 1. Why the widgets feel poor (blunt diagnosis)
- **Cognitive spam:** Financial page shows 36 tiles (33 populated). At 1920×1080 that's 3.3 viewports of noise before HAL chat.
- **Size inconsistency:** Mix of `l` (320px+), `m` (240px), and unclassified heights creates ragged vertical rhythm.
- **Empty arrogance:** 29 empty slots across the census still occupy DOM height even with `hal-10611` empty-omit (some exempt statuses leak padding).
- **Duplicate renderers:** 11 distinct chart engines when `apex-core.js` already has 3 compact ones (strip, spark, micro-bar).

## 2. Can we change ALL out? (partial — with reasons)
**NO** to keeping all 178 widgets visible; **YES** to swapping all widget *shells* for a shared compact contract.

**Physics:**
- 36 widgets × 120px (micro cap) = 4,320px > 1,080px viewport.
- HAL Chat requires ≥240px to remain conversational; compressing below breaks the program (unreadable transcript).
- Import Sync health must stay real-time visible; demoting it breaks the import safety contract.

**Therefore:** We replace every widget *renderer* with the compact set, but we **demote** ~70% of widgets to subpages/modals to achieve zero-scroll.

## 3. Zero-scroll compact contract (shared primitives for every page)
```javascript
// site/apex-core.js — enforce these caps
const APEX_COMPACT = {
  micro: { h: 60, type: 'strip', maxPerPage: 4 },      // KPI pills only
  secondary: { h: 120, type: 'spark-line', maxPerPage: 2 }, // Trends
  primary: { h: 240, type: 'chat|kanban-preview', maxPerPage: 1 }, // HAL or critical lane
  empty: { h: 0, display: 'none' },                     // hal-10611 already shipped; enforce universally
  overflow: { route: '/subpage', drawer: 'right' }      // Demotion target
};
```
- **Reuse only:** `renderSpark()`, `renderKpiStrip()`, `renderMicroBar()` from `apex-core.js`.
- **No new chart engines.** No D3 imports. No radial gauges >120px.

## 4. What MUST keep vs what to swap / demote / subpage
**MUST keep above fold (zero-scroll budget):**
1. **HAL Chat** (primary, 240px) — breaking conversational UX = breaking the program.
2. **Import Health Monitor** (micro, 60px) — import sync safety critical.
3. **Executive Strip** (micro, 60px) — max 4 pills (Revenue, Collections, AR, Claims).
4. **Critical Actions** (secondary, 120px) — max 2 items (e.g., "Bridge Errors", "Tax Open Planning").

**MUST demote to achieve zero-scroll:**
- **Financial:** Deep audit status, reconciliation status, production-vs-payroll, unified DB snapshot, quarantine panel, gold CSV ticket ops, dual-axis trends, revenue composition, EBITDA station → Move to `#financial/ops` drawer.
- **SoftDent:** All "gap" widgets except Collections/Production/Aging → Move to `#softdent/reconciliation`.
- **Office-Manager:** Daily huddle, operatory util, patient dossier cards → Move to `#office-manager/huddle` (subpage already exists).
- **Claims:** Kanban (already done), aging exposure, risk bars → Keep only "Critical Actions" strip.
- **Taxes:** Waterfall, variance bar → Move to `#taxes/planning` (already shipped).

## 5. Per-page remaps (tall → compact)
| Page | Current | Zero-Scroll Target | Action |
|------|---------|-------------------|---------|
| **financial** | 36 widgets (11 strips, 24m, 1l) | 4 micro + 2 secondary + drawer button | Demote 30 widgets to `#financial/ops-drawer`. Keep: `financial-command-strip`, `collections-gauge` (compact), `bridge-errors` (micro), `reconciliation-status` (micro). |
| **softdent** | 31 widgets (19 strips, 10m, 1l, 1?) | 4 micro + 1 secondary | Demote TP estimates, ADA catalog, PWImages eligibility to `#softdent/catalog`. Keep: Collections gap, Production gap, Aging gap (all micro). |
| **claims** | 17 widgets (5 strips, 10m, 1s, 1l) | 3 micro + 1 secondary | Already compact. Remove ERA gauge (demote to `#claims/era`). Keep: Executive strip, Critical actions, Risk micro-bar. |
| **taxes** | 8 widgets (5 strips, 2m, 1l) | 2 micro + 1 secondary | Already shipped `hal-10610` compact. Demote waterfall to `#taxes/planning`. Keep: Core strip, Period scrubber. |
| **ar** | 13 widgets (4 strips, 6m, 1l, 1?, 1s) | 3 micro + 2 secondary | Demote heatmap, waterfall, forecast trend to `#ar/analytics`. Keep: Vitals strip, Aging chart (compact), Collection bullet. |
| **quickbooks** | 9 widgets (4 strips, 3m, 1?, 1l) | 3 micro + 1 secondary | Demote expense treemap, AP aging to `#qb/details`. Keep: Net profit gap, Payroll gap, Vitals strip. |
| **office-manager** | 34 widgets (7 strips, 22m, 1l, 1s, 3?) | 3 micro + 1 primary (huddle) | Demote 30 widgets to `#office-manager/ops`. Keep: Vitals strip, Daily huddle (primary, 240px), Import freshness (micro). |
| **documents** | 5 widgets | 2 micro | Already compact. Queue + Intake status only. |
| **narratives** | 5 widgets | 2 micro | Already compact. |
| **hal** | 17 widgets | 1 primary (chat) + 4 micro | Demote mosaic grids to `#hal/mosaic`. Keep: Chat (primary), Import cache KPI, Bridge errors, Reconciliation status, Program posture (all micro strips). |

## 6. Coding package if approved (MUST / SHOULD; real files only; diffs only if short)
**MUST (breaks zero-scroll if omitted):**
1. `site/apex-layout-engine.js` — Enforce `APEX_COMPACT` height caps on resize.
2. `site/apex-core.js` — Add `collapseEmpty()` guard to prevent `$0` padding (extend `hal-10611` logic to all pages).
3. `pages/financial/controller.js` — Route `deep-audit-status`, `reconciliation-status`, `gold-csv-ticket-ops` to new `#financial/ops` drawer route.
4. `pages/softdent/controller.js` — Condense 19 strips to 4 micro pills; demote remainder to `#softdent/reconciliation` subpage.
5. `pages/office-manager/controller.js` — Move 22 `m` widgets to `#office-manager/ops` modal; retain only huddle + vitals.

**SHOULD (polish):**
- `site/apex-router.js` — Add deep-linking for `#/page/drawer` so demoted widgets are reachable via URL without full navigation.
- `site/apex-core.js` — Reuse `renderMicroBar()` for all horizontal-bar widgets instead of one-off D3 instances.

**Diff (short):**
```javascript
// site/apex-layout-engine.js
+ const MAX_ABOVE_FOLD = 1080 - 60; // minus header
+ function enforceCompact() {
+   document.querySelectorAll('.widget').forEach(w => {
+     if (w.dataset.priority !== 'critical' && w.offsetTop > MAX_ABOVE_FOLD) {
+       w.classList.add('demoted'); // moves to drawer
+     }
+   });
+ }
```

## 7. Breakage risks + how to not break the program
| Risk | Mitigation |
|------|------------|
| **HAL Chat unreadable** | Cap at `primary: 240px` minimum. Never collapse to micro. |
| **Import Sync hidden** | Exempt `import-health-monitor` from demotion logic; keep as micro strip. |
| **Empty states hide real zeros** | Use `null` vs `0` detection. `$0` still renders micro strip with "0" label; `null` collapses. |
| **Claims Kanban lost** | Already on `#claims/kanban`; ensure link in compact view opens drawer, not full reload. |
| **Taxes Planning inaccessible** | Already on `#taxes/planning`; keep deep link in compact waterfall micro-strip. |
| **Muscle memory (users expect deep audit)** | Add "Ops" button badge count showing demoted widget alerts. |

## 8. What NOT to redo / invent
- **No new chart engines.** Do not invent "nano-donut" or "spark-radial."
- **No SoftDent Excel/Print previews unless OPS explicitly opened.** Keep output options in modal, not widget.
- **No padding $0.** Empty means height 0, not "$0.00" placeholder.
- **No infinite scroll replacement.** Zero-scroll means above-fold or demoted, not "load more."

## 9. Acceptance criteria (scrollHeight gate)
```javascript
// Acceptance test (run on 1920×1080, 100% zoom)
const maxScroll = 1080 - 60; // header
const pages = ['financial','softdent','claims','taxes','ar','qb','office-manager','hal'];
pages.every(p => document.getElementById(p).scrollHeight <= maxScroll);
// AND
document.querySelectorAll('.widget[data-empty="true"]').forEach(w => w.clientHeight === 0);
```

## 10. Executive Summary (5 bullets)
- **Verdict:** We can compact the *shells*, but we must demote 70% of widgets to subpages to achieve zero-scroll without breaking HAL chat or import safety.
- **Budget:** 4 micro strips (60px) + 2 secondary (120px) + 1 primary (240px) = 720px total above fold.
- **Strategy:** Shared `APEX_COMPACT` contract in `apex-core.js`; reuse existing renderers; no new chart libraries.
- **Critical Keep:** HAL Chat (primary), Import Health (micro), Executive KPIs (micro), Critical Actions (secondary).
- **Demote:** Financial deep-audit, SoftDent catalogs, Office-Manager huddle details, AR heatmaps — all to right-drawer subpages.

## 11. Approval checklist
- [ ] Confirm demotion of 30 Financial widgets to `#financial/ops` drawer is acceptable UX.
- [ ] Confirm HAL Chat minimum 240px height is acceptable (cannot be smaller).
- [ ] Verify `hal-10611` empty-omit logic extends to SoftDent/AR (5 + 2 empties).
- [ ] Approve reuse of `apex-core.js` micro renderers vs. new D3 engines.
- [ ] Acknowledge scrollHeight gate test must pass on 1920×1080 before merge.
