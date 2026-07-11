# Phase U2 Applied — Reconciliation Engine (Moonshot REAUDIT3 SHOULD)

**Date:** 2026-07-11  
**Build:** hal-10484  
**Consult:** `MOONSHOT_AI_PROGRAM_MANAGER_UPGRADE_REAUDIT3_2026-07-11.md`  
**Status:** U2 applied and validated

## Shipped

| Item | Detail |
|------|--------|
| Pack | `apex_reconciliation_pack.py` |
| Views | `v_production_vs_payroll`, `v_collection_vs_ap` MoM variance |
| Thresholds | **5%** / **$500** (`NR2_VARIANCE_PCT`, `NR2_VARIANCE_ABS`) |
| CLI | `scripts/run_nr2_reconciliation.py` |
| APIs | `GET …/reconciliation-status`, `POST …/reconciliation` |
| Widget | `reconciliation-status` on Financial |
| Flag | `NR2_RECONCILIATION` default **ON** |

## Honesty

- Gap codes: `RECON_DATA_PENDING`, `RECON_PAYROLL_PENDING`, `RECON_COLLECTIONS_PENDING`, `RECON_VARIANCE`
- Alert values use mirrored deltas only; otherwise `null` — never invent $
- Optional 30B explainer (`classifyOnly` for dry-run); no SoftDent write-back

## Validation

```text
python -m pytest NewRidgeFinancial2/test_apex_reconciliation_u2.py -q
```

## Rollback

```text
set NR2_RECONCILIATION=0
```
