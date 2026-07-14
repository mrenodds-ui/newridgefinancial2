# HAL-10585 — Unified InsCo×ADA spine + treatment-planning fallback (applied)

**Date:** 2026-07-12  
**Prior consult:** `MOONSHOT_WHATS_NEXT_UNIFORM_ADA_TREATMENT_PLANNING_2026-07-13.md`  
**Operator:** proceed after Moonshot recommended unify spine + TP fallback.

## What shipped

| Piece | Location |
|-------|----------|
| Shared spine | `softdent_insco_ada_spine.py` |
| $ estimates (consume spine) | `softdent_insco_ada_probabilistic.py` |
| % +/- variance (consume spine) | `softdent_insco_ada_pct_variance.py` |
| Treatment planning fallback | `softdent_treatment_planning.py` → `lookup_treatment_estimate` |
| Tests | `test_insco_ada_spine_hal10585.py` (+ existing 10582–84 still green) |

## Uniform ADA analysis (same way)

1. **Window:** 5 years for both $ and %  
2. **Normalize:** `normalize_cdt` → D#### only; SoftDent internals (12, 61, 8888, decimals) excluded from matrix  
3. **Episode:** production CDT cluster → SoftDent **2** / **51** within 60 days  
4. **Tier:** exact (1 ADA) / inferred (2–3) / low (4+)  
5. **Metrics:** same episode set feeds dollar medians and pay%/WO% +/- 1 SD  
6. **Credibility:** shared floors (exact usable n≥10, high n≥30)

## Treatment planning

When `treatment_planning_estimates` / gold payment lines miss:

- `lookup_treatment_estimate` returns spine-backed payload with  
  `source=ledger_episode_5yr`, credibility badge, pay $, WO $, pay%/WO% +/-  
- Gold path still wins when payment lines exist  
- empty ≠ $0

## Honesty

Not SoftDent contractual fee schedule; no SoftDent write-back; inferred remains opt-in for direct InsCo APIs.
