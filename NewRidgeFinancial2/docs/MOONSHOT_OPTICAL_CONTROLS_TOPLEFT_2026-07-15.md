# Moonshot AI — Controls Top-Left under NR2-12009 (CONSULT ONLY)

**Date:** 2026-07-15
**Model:** `kimi-k2.5`
**Key:** OPENROUTER_API_KEY
**Script:** `scripts/run_moonshot_controls_topleft_consult.py`
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> Master Pulse SYNC SoftDent+QB+HAL · sync Period Wheel 306090120 REFRESH-PERIOD SoftDent · refresh-period Phase Comp RECONCILE now tell moonshot ai to place this widget in the top left under the n2r-12009

---

# Verdict (nr2-12012-controls-tl)

## 0. Operator Intent (verbatim)
> Master Pulse SYNC SoftDent+QB+HAL · sync Period Wheel 306090120 REFRESH-PERIOD SoftDent · refresh-period Phase Comp RECONCILE now tell moonshot ai to place this widget in the top left under the n2r-12009

## 1. Control strip → top-left under NR2-12009 (coords / layout)
- **Anchor**: Viewport-relative fixed positioning (`position: fixed`) or absolute within `#nr2-12009-landing-container`.
- **Coordinates**: `top: 64px` (immediately below the 56 px NR2-12009 mode-strip), `left: 24px`, `right: auto`, `bottom: auto`.
- **Dimensions**: `width: fit-content` (max‑width 420 px), `height: 72–88 px` (single‑row compact strip), `z-index: 900` (below mode‑strip 1000, above HAL 500).
- **Layout flow**: Horizontal flex container (LTR): `[Master Pulse SYNC] [Period Wheel 30|60|90|120] [REFRESH-PERIOD SoftDent] [Phase Comp RECONCILE]`.
- **Responsive guard**: On viewports < 1280 px, auto‑stack vertically with `gap: 8px` to prevent viewport overflow.

## 2. SoftDent emitter collision avoidance
- **SoftDent Zone**: Left‑bottom quadrant, bounding box approximately `x: 0–320 px`, `y: calc(100vh - 200px) – 100vh` (white pulse emitter).
- **Control Strip Zone**: Top‑left bounding box `x: 0–420 px`, `y: 56–152 px`.
- **Separation**: Vertical gap ≥ 600 px on 1080 p displays ensures zero geometric intersection.
- **Enforcement**: Add CSS `margin-bottom: 20px` to control strip and reserve `min-height: 180px` bottom padding on the landing canvas to guarantee SoftDent’s emitter remains unobstructed in all scroll states.

## 3. Bind map unchanged
| Widget Element | Event/Binding | Target | Action |
|---|---|---|---|
| Master Pulse SYNC | `click` / `sync:master-pulse` | SoftDent+QB+HAL | Trigger tri‑system sync pulse |
| Period Wheel (30/60/90/120) | `change` / `change:period` | Global refresh‑period | Set reconciliation interval (minutes) |
| REFRESH-PERIOD SoftDent | `click` / `refresh:softdent` | SoftDent adapter only | Force immediate SoftDent ledger refresh |
| Phase Comp RECONCILE | `click` / `reconcile:phase` | Tax Prism + HAL | Execute phase‑compensation reconciliation |
- **Data semantics**: `empty` remains non‑zero sentinel; no write‑back to SoftDent accounting fields (read‑only trigger semantics preserved).

## 4. Mockup change list
1. **HTML Structure**: Move `<section id="control-strip" class="nr2-widget">` to be the first child immediately following `<header id="nr2-12009">` (DOM order for accessibility).
2. **CSS Positioning**: Replace `.control-strip { bottom: 24px; left: 50%; transform: translateX(-50%); }` with `.controls-tl { top: 64px; left: 24px; transform: none; }`.
3. **Z‑Index Layering**: Ensure `#nr2-12009 { z-index: 1000; }` > `#control-strip { z-index: 900; }` > `#softdent-emitter { z-index: 800; }`.
4. **Visual Regression**: Update mockup snapshot `nr2-optical-qb-right-sd-left-mockup.html` to reflect top‑left placement; remove bottom‑center drop‑shadow to match header adjacency styling.

## 5. Schema bump justification
- **Current**: `nr2-12009` / `nr2-12011-landing` (bottom‑center docking).
- **New**: `nr2-12012-controls-tl` (top‑left docking).
- **Rationale**: Layout topology change constitutes a **breaking change** for coordinate‑dependent automation scripts (e.g., Selenium/WebDriver selectors using `//div[@class='control-strip'][contains(@style,'bottom')]`). Version bump isolates regression surface and preserves rollback capability for legacy bench configurations.

## 6. Executive Summary (4 bullets)
- **Relocate** the Master Pulse / Period Wheel / Phase Comp control strip to the top‑left quadrant directly beneath the NR2‑12009 mode‑strip to align with natural left‑to‑right, top‑to‑bottom operator eye‑path.
- **Preserve** all data bindings and trigger semantics; zero functional regression—relocation is purely presentational.
- **Isolate** SoftDent’s left‑bottom white‑pulse emitter via strict vertical zoning (top 152 px vs bottom 200 px), ensuring no collision or overlap on standard 1080 p and 1366×768 viewports.
- **Bump** schema to `nr2-12012-controls-tl` to mark the topology change and maintain backward compatibility for automated test suites referencing legacy bottom‑center coordinates.

## 7. Approval checklist
- [ ] Control strip DOM order immediately follows NR2‑12009 header in accessibility tree (screen‑reader tab order logical).
- [ ] SoftDent emitter bounding box (left‑bottom 320 px × 200 px) has zero intersection with control strip bounding box (top‑left 420 px × 88 px).
- [ ] Z‑index hierarchy enforced: Mode‑strip (1000) > Control‑strip (900) > SoftDent pulse (800) > HAL center (500) > background.
- [ ] Period Wheel 30/60/90/120 retains keyboard navigation (arrow‑key rotation, Enter to select) and focus indicators.
- [ ] Master Pulse SYNC button maintains `aria-label="Synchronize SoftDent QuickBooks HAL"` and focus state.
- [ ] No JavaScript event‑listener re‑registration required (delegated events on `#nr2-landing` root).
- [ ] Visual regression tests passed for 1920×1080 and 1366×768 viewports; no clipping at 100 % zoom.
