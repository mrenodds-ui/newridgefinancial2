# Phase U1 Applied — ERA 835 Ingestion (Moonshot REAUDIT3 SHOULD)

**Date:** 2026-07-11  
**Build:** hal-10483  
**Consult:** `MOONSHOT_AI_PROGRAM_MANAGER_UPGRADE_REAUDIT3_2026-07-11.md`  
**Status:** U1 applied and validated

## Shipped

| Item | Detail |
|------|--------|
| Pack | `apex_era835_pack.py` — X12 835 + remittance CSV |
| Table | `era_835_payments` (payer / proc / CAS codes only) |
| Mirror | Still updates `softdent_era_aggregates` for S1 `ERA_835_AVAILABLE` |
| Hook | `ingest_era_835` → `attach_u1_to_era_ingest` |
| APIs | `era835-status`, `era835-payments`, `era835-ingest` |
| Widget | `era835-ingest-gap` on SoftDent |
| Flag | `NR2_ERA835` default **ON** |

## PHI / Honesty

- Discard `NM1*QC` patient names; CSV patient/account/DOB/SSN columns dropped
- Gap `ERA835_PENDING` when missing/unreadable — never invent $0
- **No SoftDent write-back** (proposal / aggregate only)

## Validation

```text
python -m pytest NewRidgeFinancial2/test_apex_era835_u1.py -q
```

## Rollback

```text
set NR2_ERA835=0
```
