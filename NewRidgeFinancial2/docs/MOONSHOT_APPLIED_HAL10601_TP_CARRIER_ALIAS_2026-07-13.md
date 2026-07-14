# HAL-10601 — TP payer resolution via accepted carrier alias (applied)

**Date:** 2026-07-13  
**Consult:** `MOONSHOT_CONFIRM_HAL10600_TREATMENT_PLANNING_2026-07-13.md`  
**Operator:** proceed  
**BUILD_ID:** `hal-10601`

## Verdict applied

Wire `lookup_treatment_estimate` through **accepted** `carrier_alias` (`confidence=auto`, `review_status=accepted`) before ledger spine lookup. Pending manuals never auto-resolve.

## What shipped

| Piece | Detail |
|-------|--------|
| Resolver | `resolve_accepted_alias_for_tp` in `softdent_carrier_alias.py` |
| TP lookup | `softdent_treatment_planning.py` — alias → spine payer → existing $/% |
| Source tag | `ledger_episode_5yr_via_alias` when alias used |
| Pending | `carrier_alias_pending` → insufficient, null $, HAL confirm message |
| Status | `tpCodeUsesCarrierAlias=true` on `treatment_planning_status` |
| Tests | `test_hal10601_tp_carrier_alias.py` |

## Honesty

- No SoftDent write-back  
- No synthetic gold / payment lines  
- Pending manuals blocked until `--accept-pending`  
- empty ≠ $0  

## Live validation (2026-07-13)

| Probe | Result |
|-------|--------|
| `Aetna Healthcare` × `D2391` | `found` · `sufficient` · `viaAlias` · paid **$60.80** · source `ledger_episode_5yr_via_alias` → spine `AETNA` |
| `ANTHEM - 188` (pending manual) | `blockedPending` · insufficient · null $ · `carrier_alias_pending` |
| `tpCodeUsesCarrierAlias` | **true** |
| `emptyIsNotZero` | **true** |
