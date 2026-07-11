# Moonshot AI — Financial Executive Console PRIMARY DESIGN APPLIED

**Date:** 2026-07-10  
**Build:** **hal-10430**  
**Consult:** `MOONSHOT_FINANCIAL_PRO_PRESENTATION_CONSULT_2026-07-10.md`  
**Operator:** “proceed with all recommendations and coding” (Option A)

## Layout (matches consult wireframe)

| Level | Widget | Notes |
|-------|--------|-------|
| 1 | Financial Command Strip (`size: strip`) | Import health + period chips + morning brief + Sync action |
| 2 | Vital Signs (`executive-strip`) | Production / Collections (Pending chip) / A/R / Efficiency |
| 3 | Dual-Axis Trend (`m`) + Provider Production (`m`) | Production solid + collections dashed; provider collapses when empty |
| 4 | Revenue Composition | Populated side-by-side OR **compact action card** when empty (FIN-002) |
| 5 | A/R Aging (`m`) + claims/treatment KPIs | Secondary density row |
| 6 | EBITDA Command Station (`full`) | Waterfall + Book/Planning scrubber + trend sparkline |

## FIN items shipped

| ID | Item | Status |
|----|------|--------|
| FIN-001 | Collections/Daysheet gap surfaced + Sync action | Done (honesty preserved; operator still exports SoftDent) |
| FIN-002 | Empty large widgets → strip/compact action cards | Done |
| FIN-003 | Merge import + period + morning brief | Done (`financial-command-strip`) |
| FIN-004 | HAL Morning Financial Brief | Done (`morning financial brief` / `why are my widgets empty`) |
| FIN-005 | Depreciation missing hint on EBITDA station | Done |
| FIN-006 | Dual-axis production/collections trend | Done |
| FIN-007 | Import health ping in command strip | Done |

## Honesty

- SoftDent read-only; no invented dollars  
- Collections Pending stays empty until Daysheet/Collections export reports a real split  
- Alias IDs preserve HAL focus for legacy widget names (`import-freshness`, `payer-donut`, `ebitda-scrubber`, …)

## Files

- `apex_financial_console_pack.py` — new console builders  
- `apex_backend.py` — `_financial_widgets_from_reports` + HAL + `BUILD_ID`  
- `site/apex-core.js` / `apex-bridge.css` / `index.html`  
- `nr2-build.json` → **hal-10430**

## Prior

- `hal-10420` Claims Executive RCM Console  
- This build applies the same density pattern to Financial  
