# Phase W1 Applied — Import Cron + DQ Gates (Moonshot REAUDIT5)

**Date:** 2026-07-11  
**Build:** hal-10491  
**Consult:** `MOONSHOT_AI_PROGRAM_MANAGER_UPGRADE_REAUDIT5_2026-07-11.md`  
**Status:** W1 applied and validated

## Shipped

| Item | Detail |
|------|--------|
| DQ pack | `apex_import_dq_pack.py` — reject-only rules before `ingest_from_bundle` |
| Cron pack | `apex_import_scheduler_pack.py` — Task Scheduler one-shot + optional loop |
| CLI | `scripts/run_nr2_import_cron.py` |
| API | `GET /import-cron-status`, `POST /import-cron-run`, `GET /import-dq-status` |
| Tests | `test_apex_phase_w1_import_cron_dq.py` |

## Flags

```text
set NR2_IMPORT_CRON=1
set NR2_IMPORT_CRON_SEC=300
rem NR2_IMPORT_DQ defaults ON (set 0 to bypass — not recommended)
```

## Ops

```text
set NR2_IMPORT_CRON=1
python scripts/run_nr2_import_cron.py
python scripts/run_nr2_import_cron.py --force
```

Schedule every 5 minutes via Windows Task Scheduler (preferred over `--loop`).

## Honesty

- DQ never imputes or auto-corrects — quarantine / block only
- No SoftDent write-back; violation logs omit PHI and dollar values where possible
- Empty ≠ $0

## Validation

```text
python -m pytest NewRidgeFinancial2/test_apex_phase_w1_import_cron_dq.py -q
```
