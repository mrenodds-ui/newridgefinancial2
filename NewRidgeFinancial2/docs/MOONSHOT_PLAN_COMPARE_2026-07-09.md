# Moonshot AI — Plan vs Consult Comparison
**Date:** 2026-07-09
**Model:** kimi-k2.5 via OPENROUTER_API_KEY
**Status:** REVIEW ONLY — update Cursor plan; do not apply code yet
**Script:** `scripts/run_moonshot_plan_compare.py`

---

# Verdict
**APPROVE WITH EDITS.** Cursor's plan correctly adapts Moonshot's Terminal Glass aesthetic to the live DOM reality (dual kanban classes, proper scoping, no CDN), but it dangerously compresses the per-page accent color system into generic validation notes rather than explicit CSS implementation. The plan must explicitly preserve Moonshot's page-specific accent mapping (financial=cyan, narratives=pink, taxes=amber, etc.) and severity border implementations before P0 is sound.

## Agreement Matrix

| Topic | Moonshot consult | Cursor plan | Match? | Winner / note |
|-------|------------------|-------------|--------|---------------|
| **CSS file strategy** | `@import` Google Fonts; scope `.ms-page.ms-mission-control` | No CDN (loopback constraint); scope `.ms-mission-control` descendants | Partial | Cursor wins on fonts (loopback reality), but scope loses `.ms-page` prefix which may orphan chrome styling |
| **Selector scoping** | Assumed `.ms-page.ms-mission-control` wrapper | Targets real DOM: `article.ms-page` outer, `div.widget-grid.{pageId}-moonshot` inner | No | Cursor (DOM reality wins) |
| **Class injection site** | Layout-engine inject `ms-mission-control` to all staff pages | Widget-grid + dashboard-grid shells; mirrors both deferred-live-wire paths | Yes | Cursor improved (explicit dual paths + dashboard-grid handling) |
| **Kanban class strategy** | `.kanban-lane-mission` (replace existing) | Dual classes: keep `.kanban-board`/`.kanban-column`/`.column-header`, add `.kanban-mission`/`.kanban-lane-mission` | No | Cursor (backward compatibility) |
| **KPI mono** | `.kpi-mono` on values | Wrap/add `kpi-mono` where `.kpi-value` emitted | Yes | Match |
| **Empty states** | `empty-terminal` class; "AWAITING IMPORT" badge | Add `empty-terminal` alongside `widget-empty`; preserve CTA text | Yes | Match |
| **Severity data honesty** | Severity-coded rows, red glow >90 days | Only add `severity-high/med/low` if `row.severity` exists; never invent | Yes | Cursor strengthened (explicit data honesty guard) |
| **Google Fonts** | CDN `@import` for JetBrains Mono + Inter | Local stack: `'JetBrains Mono', 'SF Mono', Consolas, ui-monospace` | No | Cursor (loopback HTTPS constraint) |
| **Apply order P0-P3** | P0 CSS, P1 layout, P2 canvas, P3 spot fixes | P0 CSS, P1 class injection, P2 canvas, P3 compressed into browser pass | Partial | Cursor weakened (P3 should be explicit commit for accent verification) |
| **Page-by-page accents** | Explicit table: financial/cyan, softdent/heatmap, quickbooks/blue, ar/red, taxes/amber, claims/cyan-gold, narratives/pink, documents/gold, library/cyan, office/command, hal/red | Mentioned in validation gate only; implementation steps generic | No | **Moonshot** — Cursor deferred critical accent mapping |
| **Dashboard-grid pages (QB/office-manager)** | Listed in page table | Explicitly handled in layout-engine dashboard-grid path (~L73) | Yes | Cursor improved (explicit dual grid system handling) |
| **HAL scope** | `.hal-interface` red glow, transcript glass panels | "HAL conversation redesign beyond CSS accent... out of scope" | No | Cursor weakened (reduced to CSS only, no transcript panels) |
| **Commit/build bump** | Context build ~hal-10164, max 4 commits | Specific hal-10165, 5 todos including verify/commit | Yes | Cursor improved (specificity) |

## Where Cursor Improved On Moonshot
1. **DOM scoping accuracy**: Correctly identifies live DOM uses `article.ms-page` (outer) and `div.widget-grid.{pageId}-moonshot` (inner) rather than Moonshot's assumed wrapper structure.
2. **Dual kanban classes**: Preserves existing `.kanban-column`/`.column-header` classes while adding mission classes, ensuring backward compatibility with existing kanban JS.
3. **No Google Fonts CDN**: Removes `@import` due to Loopback HTTPS constraints, substituting robust local font stack—critical for offline/air-gapped environments.
4. **Severity data honesty**: Explicitly guards against fabricating severity data ("do **not** invent severity when data lacks it"), preserving the "honest-empty" principle.
5. **Mirror path coverage**: Explicitly copies layout-engine edits to both `site/deferred-live-wire/` and root `deferred-live-wire/` directories.
6. **Dashboard-grid explicit handling**: Separates widget-grid from dashboard-grid injection paths for QuickBooks and Office-Manager pages.
7. **Build bump specificity**: Pins to exact hal-10165 across all touchpoints (meta tags, query strings, registry).

## Where Cursor Weakened Or Missed Moonshot
1. **Per-page accent CSS deferred**: Moonshot specified distinct accent colors per page (financial=cyan, narratives=pink, taxes=amber, documents=gold, etc.). Cursor mentions these only in validation, with no explicit CSS implementation plan for page-specific variable injection.
2. **HAL scope reduction**: Moonshot wanted `.hal-interface` transcript glass panels and full HAL 9000 logs aesthetic; Cursor limits HAL to "CSS accent if needed," dropping the transcript panel chrome.
3. **P3 spot fixes compressed**: Moonshot required P3 as explicit commit for per-page accent verification; Cursor collapses this into a "short browser pass," risking incomplete accent implementation.
4. **Scan-line animation details**: Moonshot specified 4 motion rules including chart scan-lines; Cursor mentions "keep Moonshot tokens" but doesn't explicitly commit to implementing the `@keyframes scan` overlay in the adapted CSS.
5. **Tabular-nums omission**: Moonshot hard-required `font-variant-numeric: tabular-nums` for currency; Cursor doesn't explicitly preserve this rule in the font stack adaptation.
6. **Emoji ban enforcement**: Moonshot explicitly banned emoji in titles; Cursor mentions it in validation but not in implementation constraints.

## Required Plan Edits (must-fix before apply)
- **Add per-page accent variable injection**: In `moonshot-layout-engine.js`, when injecting `ms-mission-control`, also inject page-specific accent class (e.g., `financial-mission`, `narratives-mission`) so CSS can target `--mc-accent` variables per page per Moonshot's table.
- **Preserve tabular-nums rule**: Explicitly add `font-variant-numeric: tabular-nums` to the `.kpi-mono` and table number selectors in the adapted CSS.
- **Explicit scan-line keyframes**: Confirm `@keyframes scan` and chart overlay animation are preserved in the adapted CSS, not just "tokens."
- **Severity border classes**: Ensure `.severity-high` includes `border-left: 2px solid var(--mc-red)` and `.glow-red` definitions in the CSS adaptation.
- **HAL transcript panels**: Either add `.hal-transcript-glass` class injection for HAL logs or explicitly document that HAL scope is reduced to header accent only.

## Optional Nice-to-Haves (defer)
- **Print icon CSS for narratives**: Moonshot mentioned print-ready styling; defer to HAL-10166 if print functionality already exists.
- **Heat-map cell severity**: Softdent operatory grid heat-map colors (hot/warm/cool) can be deferred to next visual pass.
- **EBITDA waterfall bars**: QuickBooks EBITDA visualization enhancements via stat-grid styling.

## Final Recommended Apply Order
1. **P0 — Adapted CSS**: Create `nr2-mission-control-glass.css` with local font stack, tabular-nums, scan-line keyframes, severity borders, and per-page accent variable hooks; link in `index.html` with `?v=hal-10165`.
2. **P1 — Layout Engine Injection**: Modify both `moonshot-layout-engine.js` paths (site/ and root deferred-live-wire/) to inject `ms-mission-control` and page-specific accent classes (`{pageId}-mission`) on widget-grid and dashboard-grid shells.
3. **P2 — Canvas Hooks**: Update `page-canvas.js` to add `kpi-mono`, `empty-terminal`, dual kanban classes (`kanban-mission`, `kanban-lane-mission`), and conditional severity row classes.
4. **P3 — Accent Verification**: Dedicated commit verifying per-page accents (financial=cyan glow, narratives=pink, taxes=amber, documents=gold, HAL=red) match Moonshot specification.
5. **P4 — Build Stamp & Commit**: Bump hal-10165, verify no 404 on CSS, operator validation gate, commit/push live-wire files only.

## Operator One-Liner
**"Approve with edits: add explicit per-page accent class injection and tabular-nums preservation to P0/P1, then proceed P0-P4; reject if per-page colors are deferred to unspecified future pass."**
