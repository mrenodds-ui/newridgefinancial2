# HAL-10603 — Honesty CI gate null→$0 regression prevention (applied)

**Date:** 2026-07-13  
**Consult:** `MOONSHOT_CONFIRM_HAL10601_2026-07-13.md`  
**Operator:** proceed  
**BUILD_ID:** `hal-10603`

## Verdict applied

Honesty CI gate so builds fail if treatment-planning / financial widgets regress **null → $0.00**. No change to `lookup_treatment_estimate` logic (Moonshot constraint).

## What shipped

| Piece | Location |
|-------|----------|
| Core suite | `NewRidgeFinancial2/test_hal10603_honesty_ci.py` |
| Integration (Moonshot paths) | `tests/integration/test_tp_null_handling.py` |
| | `tests/integration/test_widget_regression.py` |
| Runner | `scripts/run_honesty_ci_gate.py` |
| CI | `.github/workflows/validate-nr2.yml` — honesty step + `rapidfuzz` install |
| Helper | `assert_no_fake_zero_dollars()` |

## Gates enforced

- `emptyIsNotZero` must not flip to `false`
- `showDollars=false` must not display `$0.00`
- Pending alias / via-alias null paid → `paidAmountAvg is None` (not `0.0`)
- Fixture probes: Aetna Healthcare × D2391 shows dollars; ANTHEM - 188 pending does not
- HON-001 + UI honesty audit remain green

## Honesty

empty ≠ $0 · no SoftDent write-back · no invented gold · TP lookup logic unchanged
