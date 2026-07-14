# Apex Viewport Zero-Scroll — Phase A Pixel Budget

**Date:** 2026-07-11  
**Consult:** `MOONSHOT_ZERO_SCROLL_WIDGETS_CONSULT_2026-07-11.md`  
**Target:** 1920×1080, 100% zoom, compact density  
**Usable stage height:** ≈920px (1080 − ~100px chrome/ticker − padding)  
**Build target:** hal-10561  

## Hard caps (Moonshot §2)

| Tier | Max height | Typical sizes |
|------|------------|---------------|
| Micro | 120px | strip, s KPI/status |
| Secondary | 240px | m |
| Primary | 320px | one l/chart/table |

## Per-page budget (Phase A)

| Page | Primary (≤320) | Secondary tiles (≤240) | Micro strips (≤120) | Move / subpage |
|------|----------------|------------------------|---------------------|----------------|
| Financial | dual-trend or AR chart | provider-hbar, composition | command + vital strips, KPIs | ebitda/full packs → capped internal scroll |
| Taxes | bridge waterfall | variance bar | KPI strip row | CPA tools → capped / collapsed |
| SoftDent | prod trend | util/timeline | KPI chips | full packs → max-height + internal scroll |
| QuickBooks | expense chart | expense-hbar | KPIs | categorize → secondary cap |
| AR | aging chart | outlook | KPI row | heatmap/waterfall → secondary/primary caps |
| Claims | top-5 critical list | risk/era gauges | pipeline summary + open kanban | **Kanban → `#claims/kanban` only** |
| Narratives | composer preview ≤320 | — | KPI chips | library → dropdown/filter density |
| Documents | thumb grid ≤200 | — | KPIs | PDF preview → modal path |
| Library | compact list ≤5 | — | KPIs | tree collapsed |
| Office Manager | day util ≤320 | task+alert tiles | huddle strip | gantt/full → caps; operatory subpage |
| HAL | chat tile ≤320 (no sole-l) | health gauges ≤120 | import KPI + posture | **Full audit → strip + Full Log** |

## Gate

`scrollHeight ≈ innerHeight` (±5px) on compact density at 1920×1080 for parent pages.  
Comfortable density may scroll (opt-in).
