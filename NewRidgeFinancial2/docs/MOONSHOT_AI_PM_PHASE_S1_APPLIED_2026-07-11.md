# Phase S1 Applied — ERA harden into unified DB

**Date:** 2026-07-11  
**Build:** hal-10479 (SHOULD wave ship)  
**Prior:** S0 QB payroll/AP  
**Status:** Phase S1 validated

## Shipped

| Item | Detail |
|------|--------|
| Pack | `apex_softdent_era_pack.py` |
| Hook | `ingest_era_835` → `attach_era_to_ingest` (aggregates only) |
| DB | `softdent_era_aggregates` in `nr2_unified.db` |
| Gap | `ERA_835_AVAILABLE` when collections pending + ERA totals exist |
| Honesty | Never copies ERA $ into SoftDent collections; proposal only |

## Validation

```text
python -m pytest NewRidgeFinancial2/test_apex_softdent_era_s1.py -q
```
