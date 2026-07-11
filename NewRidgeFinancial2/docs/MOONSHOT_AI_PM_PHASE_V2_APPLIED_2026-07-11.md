# Phase V2 Applied — 30B Explain Cache + Mobile Polish (Moonshot REAUDIT4 NICE)

**Date:** 2026-07-11  
**Build:** hal-10489  
**Consult:** `MOONSHOT_AI_PROGRAM_MANAGER_UPGRADE_REAUDIT4_2026-07-11.md`  
**Status:** V2 applied and validated (explain cache default **OFF** until burn-in)

## Shipped

| Item | Detail |
|------|--------|
| Explain cache | `explain_variance()` + LRU (max 128) keyed by `(period, delta_hash)` |
| Invalidation | `invalidate_explain_cache()` on import refresh in `apex_backend` |
| Mobile CSS | `site/apex-mobile-polish.css` — mosaic single column & insight type @ ≤768px |
| Tests | `test_apex_phase_v2_polish.py` |

## Flags (default OFF)

```text
set NR2_EXPLAIN_CACHE=1
```

## Honesty / consistency

- Cache stores orchestrator result metadata only for mirrored variance hashes — no PHI in keys
- Import completion always clears the cache to avoid stale explanations
- SoftDent remains read-only (no write-back)

## Validation

```text
python -m pytest NewRidgeFinancial2/test_apex_phase_v2_polish.py -q
```
