# Phase T0–T5 Applied — Moonshot REAUDIT2 data plane + GA flip

**Date:** 2026-07-11  
**Build:** hal-10481  
**Consult:** `MOONSHOT_AI_PROGRAM_MANAGER_UPGRADE_REAUDIT2_2026-07-11.md`  
**Status:** T0–T5 applied per Moonshot (operator: proceed as directed)

## Shipped

| Phase | Deliverable |
|-------|-------------|
| **T0** | `apex_softdent_production_pack.py` → `softdent_production` + `softdent_case_acceptance` |
| **T1** | `apex_softdent_aging_schedule_pack.py` → aging buckets (summary only) + scheduling |
| **T2** | `apex_qb_net_profit_pack.py` → `qb_net_profit` |
| **T3** | `apex_import_watcher_pack.py` + `scripts/run_nr2_import_poll.py`; APIs `GET …/import-watcher-status`, `POST …/import-poll` |
| **T4** | Views `v_production_vs_payroll`, `v_collection_vs_ap` + widgets; `hal-ai-insight` attaches ratios on `efficiency_audit` |
| **T5** | `NR2_AI_ORCHESTRATOR` **defaults ON** (`=0`/`false`/`off` to disable) |

## Honesty

- Gap codes when missing: `PRODUCTION_PENDING`, `AGING_PENDING`, `NET_PROFIT_PENDING`, etc.
- Empty ≠ $0; no SoftDent write-back; aging = bucket totals only (no patient names)

## Validation

```text
python -m pytest NewRidgeFinancial2/test_apex_t_wave_moonshot.py -q
```

## Ops

```text
python scripts/run_nr2_import_poll.py
# disable orchestrator: set NR2_AI_ORCHESTRATOR=0
```
