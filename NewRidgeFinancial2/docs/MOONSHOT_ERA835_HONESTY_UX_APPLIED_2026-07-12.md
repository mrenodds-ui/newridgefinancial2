# Moonshot ERA-835 Collections Honesty UX Bridge — APPLIED (hal-10571)

**Date:** 2026-07-12  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_INSPLAN_OPS_2026-07-12.md`  
**Operator:** proceed  
**Build:** **hal-10571**  
**Status:** Applied (read-only; SoftDent Register Ins Plan $0 = truth; no invented dollars)

## What shipped

| Item | Detail |
|------|--------|
| Gap code | `collectionsGapCode=ERA_835_REQUIRED` when Register collections reported + `collectionsFormatRequired` + Ins Plan ≤ 0 |
| HAL phrase | “SoftDent Register reports Ins Plan Collections $0.00; proceed with ERA-835 for insurance detail.” |
| Fix hint | Do **not** re-export Register hoping Ins Plan > 0 |
| ERA stub | `softdent_practice_exports.stub_era835_ingestion_path()` (read-only) |
| ERA enrich | Preserves `ERA_835_REQUIRED` on `collectionsGapCode` when Register Ins Plan is zero |

## Validation

| Gate | Result |
|------|--------|
| Unit `test_era_fallback_when_register_zero_insurance` | **PASS** |
| HAL July insurance collections policy | **PASS** |
| No invented insurance/patient $ | **PASS** |
| Wrong-period inbox still `COLLECTIONS_FORMAT_REQUIRED` | **PASS** (not hijacked) |

```text
cd NewRidgeFinancial2
python -m unittest test_era_835_honesty_ux_hal10571 -v
```

## Files

| File | Change |
|------|--------|
| `apex_softdent_hardening_pack.py` | `GAP_ERA_835_REQUIRED` + honesty branch + reply |
| `apex_softdent_era_pack.py` | Preserve ERA_835_REQUIRED when Register Ins Plan zero |
| `nr2_hal_gateway.py` | Local policy for July Ins Plan / ERA asks |
| `softdent_practice_exports.py` | `stub_era835_ingestion_path` |
| `apex_backend.py` + site assets | BUILD_ID **hal-10571** |
| `test_era_835_honesty_ux_hal10571.py` | NEW |

## Not done (runner-ups — do not deviate)

- Collections Summary Excel-temp reliability  
- Browser smoke of widgets NICE  
- Re-export July Register for Ins Plan > 0  
- Inventing Ins/Patient split from Regular Collections  
