# Moonshot Better Backend Widgets MUST — APPLIED (hal-10567)

**Date:** 2026-07-12  
**Consult:** `MOONSHOT_BETTER_BACKEND_WIDGETS_CONSULT_2026-07-12.md`  
**Coding:** `MOONSHOT_BETTER_BACKEND_WIDGETS_CODING_2026-07-12.md`  
**Build:** **hal-10567**  
**Operator:** continue with moonshot and do not deviate  

## What shipped (MUST only)

| Widget | Type | Pages | Notes |
|--------|------|-------|-------|
| Tax Planning Items | `data-table` | taxes | Dense planning rows from `tax_engine` (bridge / quarterly / W-2) |
| Collection Efficiency | `radial-gauge` | financial, ar | `data.mode=collections`, target 98%; SoftDent dashboard fallback |
| System Health | `status-matrix` | office-manager | SoftDent / QuickBooks / Claims / HAL rows; configurable headers |

## Files

| File | Change |
|------|--------|
| `apex_better_backend_widgets_pack.py` | NEW — three MUST builders |
| `apex_backend.py` | Wire taxes / financial / ar / office-manager; BUILD_ID **hal-10567** |
| `site/apex-core.js` | radial-gauge `mode`/`target`; status-matrix `data.headers` |
| `nr2-build.json` + site assets | Cache-bust **hal-10567** |
| `test_better_backend_widgets_hal10567.py` | Smoke tests |

## Adaptations (coding consult → live contracts)

- Collections gauge uses SoftDent dashboard rows (same honesty path as `build_collection_bullet`).
- Tax quarterly rows map live `federal`/`kansas`/`due`/`period` fields.
- System health prefers `diagnostics.datasets` tones; keeps live `patients[]` FE shape.
- FE patches keep W-10 recall gauge and W-08 verification matrix working (defaults unchanged).

## Not done (per Moonshot — do not deviate)

SHOULD/NICE: action-list, collection-task-list, ai-insight, patient-dossier, pareto, tax-calendar, timeline-lanes.

## Validation

```text
python -m unittest test_better_backend_widgets_hal10567 -v
```

Restart backend + hard-refresh browser, then confirm:

- Taxes → Tax Planning Items table  
- Financial / A/R → Collection Efficiency gauge (98% target)  
- Office Manager → System Health matrix  

## Honesty

- empty ≠ $0  
- No invented collections ratio when production/collections missing  
- No third-party embeds  
