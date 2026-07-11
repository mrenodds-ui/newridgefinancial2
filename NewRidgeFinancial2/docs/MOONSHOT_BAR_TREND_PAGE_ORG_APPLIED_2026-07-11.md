# Moonshot Bar/Trend + Page Org — APPLIED

**Date:** 2026-07-11  
**Consult:** `MOONSHOT_BAR_TREND_PAGE_ORG_CONSULT_2026-07-11.md`  
**Build:** `hal-10450`  
**Operator:** proceed with all

## Shipped

| Phase | What |
|-------|------|
| **1** | Financial console already strip-based; added **EBITDA / Net Income Variance** bar (`ebitda-variance-bar`) on Financial + Taxes; empty large instruments keep collapse-to-strip. |
| **2** | **Claims Status Distribution** bar (`claims-status-bar`) + **Claims 90+ Aging Trend** line (`claims-aging-mini-trend`, daily snapshots). |
| **3** | SoftDent **Import Health Timeline** + **stale-import-alert** chip (≥7 days). |
| **4** | Office Manager + SoftDent **Operatory Slot Load** bars; daily huddle now reads `operatoryChairs[].slots`. |
| **5** | **A/R Forecast (ERA Velocity)** honest blocked stub (`ar-forecast-trend`) — no illustrative decay $. Awaits IMP-004 ERA 835. |
| **6** | QB **expense horizontal bars** confirmed on QuickBooks page; empty collapses to strip; size `m` when populated. |

## Files

- `NewRidgeFinancial2/apex_bar_trend_page_org_pack.py` (new)
- `NewRidgeFinancial2/apex_backend.py` (wire pages + `BUILD_ID=hal-10450`)
- `NewRidgeFinancial2/apex_program_improve_pack.py` (huddle operatory chairs)

## Honesty

- No invented dollars.
- Timeline/trend charts need 2+ daily page opens before a line appears (first visit records snapshot only).
- Phase 5 forecast remains blocked until ERA 835 payer velocity exists.

## Validate

1. Restart NR2 / hard-refresh `https://127.0.0.1:8765/`
2. Claims → status bar matches kanban column counts
3. SoftDent → import timeline / stale chip
4. A/R → forecast shows “Blocked — needs ERA 835” strip
5. QuickBooks → expense bars (or collapsed empty chip)
6. Office Manager → operatory slot load + huddle
