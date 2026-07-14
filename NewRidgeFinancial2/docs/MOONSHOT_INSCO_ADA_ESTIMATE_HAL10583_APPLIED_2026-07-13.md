# InsCo × ADA Estimate HAL Surfacing — APPLIED (HAL-10583)

**Date:** 2026-07-13  
**Consult:** `MOONSHOT_WHATS_NEXT_INSCO_ADA_ESTIMATES_RELIABILITY_2026-07-13.md`  
**Operator:** proceed  
**Status:** Applied (presentation / HAL only; no SoftDent write-back; empty ≠ $0)  
**Prior:** HAL-10582 probabilistic engine (`d028527`)  
**Build stamp:** kept `hal-10576` (package HAL-10583)

## Verdict shipped

HAL + SoftDent widget surface **exact usable+** InsCo×ADA ledger estimates with credibility badges. **Inferred** estimates stay hidden unless staff opts in (“show uncertain estimates”), which writes an audit line.

## Display rules

| Badge | Meaning | Default visible |
|-------|---------|-----------------|
| **high** (green/ok) | exact n≥30 | Yes |
| **usable** (amber/warn) | exact n≥10 | Yes |
| **inferred** (danger) | proportional multi-ADA split | Opt-in only |
| insufficient | n below floor | Returns insufficient_data / not $0 |

## What shipped

| Item | Detail |
|------|--------|
| Lookup default | `include_inferred=False` → exact tier only |
| HAL board-actions | Status + payer×ADA lookup with badges |
| HAL gateway policy | `policy:insco-ada-estimates` |
| SoftDent widget | `softdent-insco-ada-estimates` |
| APIs | `GET /api/apex/insco-ada-estimates/status`, `.../estimate?payer=&ada=&includeInferred=` |
| Chips | InsCo×ADA status · Delta KS × D1110 |
| Audit | `C:\SoftDentFinancialExports\insco_ada_inferred_view_audit.jsonl` on inferred opt-in |
| Tests | `test_insco_ada_estimate_hal10583.py` |

## Validation

```text
cd NewRidgeFinancial2
python -m unittest test_insco_ada_estimate_hal10583 test_insco_ada_probabilistic_hal10582 -v
```

Live: Delta KS × D1110 returns exact high/usable with badge (not $0 on miss).

## Honesty

- Ledger estimate ≠ contractual benefit / ≠ gold payment-line path (hal-10400 still empty)
- empty ≠ $0
- No SoftDent write-back
- Inferred = invented proportional splits — never quote to patients by default
