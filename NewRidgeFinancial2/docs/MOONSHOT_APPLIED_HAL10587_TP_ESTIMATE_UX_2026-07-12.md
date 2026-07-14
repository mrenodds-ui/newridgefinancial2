# HAL-10587 — Treatment Plan Estimate UX Surface (applied)

**Date:** 2026-07-12  
**Prior consult:** `MOONSHOT_WHATS_NEXT_AFTER_HAL10586_2026-07-13.md`  
**Operator:** `proceed`

## What shipped

| Piece | Location |
|-------|----------|
| TP chip builder | `build_tp_estimate_chip()` in `softdent_treatment_planning.py` |
| Enriched lookup/reply | `lookup_treatment_estimate` + `format_treatment_estimate_reply` |
| SoftDent widget | `softdent-tp-estimate-chips` via `treatment_plan_estimate_widget()` |
| API | `GET /api/apex/treatment-planning/estimate` returns `chip` + audit |
| HAL board-action | Uses chip badge/tone/display for Tx plan asks |
| Tests | `test_treatment_planning_hal10587.py` |
| Audit | `C:\SoftDentFinancialExports\tp_estimate_audit_*.jsonl` |

## Behavior

- Fallback chain: gold payment lines → ledger spine exact usable+ → catalog insufficient (no dollars)  
- Chip badges: Exact high/usable, Inferred, Insufficient, Payment lines (gold)  
- Insufficient never shows `$0.00` (`showDollars=false`, empty != $0)  
- Widget lists top exact usable chips from catalog for SoftDent page  

## Honesty

No SoftDent write-back; not a benefits guarantee; gold path still preferred when present.
