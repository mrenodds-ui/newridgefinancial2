# Moonshot Cache Coherence & Stub Survivability — APPLIED

**Date:** 2026-07-12  
**Consult:** `MOONSHOT_CACHE_PROBLEM_CONSULT_2026-07-12.md`  
**Build:** **hal-10563**  
**Operator:** approve  

## Approval checklist (operator)

- [x] IDB invalidation on BUILD_ID mismatch (one-time clear of stale mosaics)  
- [x] Stub fill failure surface (exit infinite warming)  
- [x] Client warming poll timeout (~5 × 750ms → hard reload)  
- [x] REC-007 HAL model warm untouched  
- [x] SoftDent read-only (no write-back)  

## What changed

| Phase | Area | Change |
|-------|------|--------|
| **1 MUST** | `indexeddb-store.js` | `clearWidgets`, `loadWidgetsIfBuild` — drop entries when `payload.buildId ≠` live build |
| **1 MUST** | `apex-core.js` | Paint IDB only after BUILD_ID gate; skip cache write for `warming` / `fillFailed` |
| **2 SHOULD** | `apex_backend.py` | Fill-thread failure → traceback + `fillFailed` payload in `_WIDGETS_CACHE` (not endless stub); `_WIDGETS_FILL_FAILURES` counter |
| **3 SHOULD** | `apex-core.js` | `warmingPollStreak` ≥ 5 → clear page IDB + `location.reload()` |
| Build | assets / tests | **hal-10563** |

## Validation

```text
python -m unittest test_cache_coherence_hal10563 test_expert_se_phase3 -v
```

Browser (optional):
1. Hard-refresh once → pre-10562 IDB mosaics should not flash crowded KPIs  
2. `__nr2AssertKpiBudget(4)` still holds after network paint  
3. Stuck warming clears within ~4s (reload)  

## Honesty

- Empty ≠ `$0`  
- Fail surface message does not invent dollars  
- HAL keep_alive / REC-007 unchanged  

## Rollback

Revert to **hal-10562** assets + prior stub fill `print`-only handler if needed.
