# Moonshot July Production Max-Merge Honesty — APPLIED (hal-10579)

**Date:** 2026-07-13  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_HAL_NO_REEXPORT_2026-07-13.md`  
**Operator:** proceed  
**Status:** Applied (merge honesty only; no SoftDent write-back; Regular/ERA path unchanged)  
**Build stamp:** kept `hal-10576` (package name hal-10579)

## Verdict shipped

July dashboard production now matches SoftDent Register / daysheet truth **$44,735.00**. `provider_prod` ($45,684.25) no longer inflates period production via max-merge.

## Root cause

`_month_rows` max-merged `production_by_provider` (**45684.25**) over daysheet/bridge Register totals (**44735.00**).

## What shipped

| Item | Detail |
|------|--------|
| `_merge_production` | Prefer Register/daysheet/bridge/`inbox_export` over `provider_prod` |
| Source tags | `productionAuthority=register\|softdent_period` |
| Sync preserve | Keep Regular / Ins Plan honesty flags when analytics merge runs |
| Live refresh | `sync_dashboard_period_rows(force_reimport=True)` |

## Live validation

| Gate | Result |
|------|--------|
| July production | **44735.00** (was 45684.25) |
| Regular / patient | **30626.42** |
| Ins Plan | **0.00** |
| Gap / widget | `ERA_835_REQUIRED` · Regular Complete · ERA Required |
| Unit tests | **PASS** (`test_production_max_merge_honesty_hal10579` + related) |

```text
cd NewRidgeFinancial2
python -m unittest test_production_max_merge_honesty_hal10579 -v
```

## Files

| File | Change |
|------|--------|
| `softdent_dashboard_period_sync.py` | Register-authority production merge + sync preserve |
| `test_production_max_merge_honesty_hal10579.py` | NEW |
| `docs/MOONSHOT_WHATS_NEXT_AFTER_HAL_NO_REEXPORT_2026-07-13.md` | consult |
| `docs/MOONSHOT_PRODUCTION_MAX_MERGE_HONESTY_HAL10579_APPLIED_2026-07-13.md` | NEW (this file) |
| `scripts/run_moonshot_whats_next_after_hal_no_reexport_consult.py` | consult runner |

## Not done

- ERA-835 procurement  
- BUILD_ID bump  
- Commit/push (await operator)
