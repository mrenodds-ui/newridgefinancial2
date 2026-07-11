# Phase W0 Applied — SoftDent Extended Metrics (Moonshot REAUDIT5 MUST)

**Date:** 2026-07-11  
**Build:** hal-10490  
**Consult:** `MOONSHOT_AI_PROGRAM_MANAGER_UPGRADE_REAUDIT5_2026-07-11.md`  
**Status:** W0 applied and validated

## Shipped

| Item | Detail |
|------|--------|
| Views | `v_case_acceptance`, `v_patient_aging`, `v_scheduling_efficiency` |
| Pack | `apex_softdent_extended_pack.py` + widgets on Financial / SoftDent |
| T1 enhance | `operatoryChairs[]` → scheduling when row table empty; `InsPending`; `ScheduledProduction` |
| API | `GET /api/apex/hal/extended-metrics-status` |
| Tests | `test_apex_softdent_extended_w0.py` |

## Flag

```text
set NR2_EXTENDED_METRICS=1
```

Default **ON**. Set `0` to hide W0 widgets (rollback).

## Honesty

- Empty ≠ $0; gap codes `CASE_ACCEPT_DATA_PENDING` / `AGING_DATA_PENDING` / `SCHEDULE_DATA_PENDING`
- Aging = summary buckets only (no patient names)
- Chairs-only schedule leaves `fill_rate` null when capacity unknown
- No SoftDent write-back

## Validation

```text
python -m pytest NewRidgeFinancial2/test_apex_softdent_extended_w0.py -q
```
