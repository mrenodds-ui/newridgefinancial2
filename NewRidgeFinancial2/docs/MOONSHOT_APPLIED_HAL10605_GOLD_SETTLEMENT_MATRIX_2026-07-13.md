# HAL-10605 — Gold settlement_matrix + industry NEW HIGH aliases (applied)

**Date:** 2026-07-13  
**Consult:** `MOONSHOT_DENTAL_INSURANCE_INDUSTRY_KNOWLEDGE_2026-07-13.md`  
**Operator:** proceed with all moonshot recommendations and do not deviate  
**BUILD_ID:** `hal-10605`

## Verdict applied (exact)

1. **NEW HIGH aliases** (only): `Great-west` → `CIGNA DENTAL`; `Kanawha Benefit Solutions, Inc` → `HUMANA DENTAL`
2. **HAL-10605 Gold package:** `settlement_matrix` schema + hydrate from `sd_insurance_payment_lines` via accepted aliases; TP prefers **viaGold > viaAlias > viaLedger**
3. **Coventry** remains **MEDIUM pending** (not auto-accepted)
4. **77 rejected** remain NONE (no force-match)
5. **No invented gold** — live gap stays `GOLD_CSV_MISSING` until SoftDent Insurance Payment Analysis CSV lands
6. Runner-ups (address mining / COB / KS defaults) **not** implemented — consult said why-not-now

## What shipped

| Piece | Location |
|-------|----------|
| Settlement matrix | `softdent_settlement_matrix.py` |
| Hydrate on ingest/repair | `softdent_treatment_planning.py`, `softdent_gold_payment_pipeline.py` |
| TP prefer viaGold | `lookup_treatment_estimate` |
| NEW HIGH constants | `MOONSHOT_INDUSTRY_HIGH` in `softdent_carrier_alias.py` |
| Package runner | `run_hal10605_gold_settlement_package()` |
| Tests | `test_hal10605_gold_settlement_matrix.py` |

## Acceptance vs Moonshot §10 (honest)

| Criterion | Status |
|-----------|--------|
| NEW HIGH aliases accepted | Done |
| Coventry pending | Done |
| 77 rejected untouched | Done |
| `settlement_matrix` created | Done |
| Gold CSV ≥1000 rows / ≥200 cells n≥10 | **Blocked** — `GOLD_CSV_MISSING` (empty ≠ $0) |
| Honesty CI / no zero-fill | Preserved |
| SoftDent write-back | None |

## SoftDent playbook (unchanged)

Reports → Insurance → Insurance Payment Analysis → CSV →  
`C:\SoftDentFinancialExports\insurance_payments_YYYYMMDD.csv` → Sync
