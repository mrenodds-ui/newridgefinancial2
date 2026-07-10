# Moonshot More Widgets + Flash Polish — Applied

**Date:** 2026-07-10  
**Build:** **hal-10290**  
**Consult:** `MOONSHOT_MORE_WIDGETS_FLASH_CONSULT_2026-07-10.md`  
**Status:** Applied after operator **proceed**

## W1 — Core financial charts + threshold pulse

| Instrument | Type | Pages |
|------------|------|-------|
| Provider Production | `horizontal-bar` | Financial, SoftDent |
| Expense Categories | `horizontal-bar` | QuickBooks |
| Payer Mix / Ins vs Patient | `donut` | Financial, Office Mgr |
| Collection Efficiency | `bullet` | Financial, A/R |
| Insurance vs Patient | `stacked-bar` | Financial, Claims, Office Mgr |
| Threshold alert pulse | CSS `.apex-alert-pulse` | A/R / claims KPIs when 90+ >20% or denial >15% |

## W2 — Advanced visualization

| Instrument | Type | Pages |
|------------|------|-------|
| A/R Aging Flow | `waterfall` (bucket steps; no invented adjustments) | A/R |
| Period Horizon | `scrubber` | Financial, Taxes |
| KPI sparklines | existing | unchanged (already on production/collections) |

## W3 — Motion polish

| Item | Implementation |
|------|----------------|
| KPI numeric rollup | `ApexMotion.animateValue` |
| Holographic card tilt | `ApexMotion.enableHoloTilt` (max ~5°) |
| Typing decoder | HAL reply via `ApexMotion.decodeText` |
| Chart crosshair | `ApexChartWidget` pointer snap |
| Focus mode | ⛶ on charts/waterfall; ESC to close |

## Honesty

- No invented dollars; empty states when imports lack fields
- Waterfall uses aging **buckets only** (Gross→Adjustments walk omitted — not in import)
- Bullet scale bands are visual only, not practice benchmarks
- `0.0` insurance/patient values treated as real (not falsy-skipped)

## Files

- `apex_backend.py` — builders + page wiring + `BUILD_ID`
- `site/apex-core.js` — templates, rollup, focus, decoder hook
- `site/apex-chart-widget.js` — crosshair
- `site/apex-motion-helper.js` — tilt / decode / animateValue
- `site/apex-bridge.css` / `apex-chrome-flash.css` — styles
- `site/index.html`, `nr2-build.json`
