# Phase V0 Applied — Burn-in Observability (Moonshot REAUDIT4)

**Date:** 2026-07-11  
**Build:** hal-10487  
**Consult:** `MOONSHOT_AI_PROGRAM_MANAGER_UPGRADE_REAUDIT4_2026-07-11.md`  
**Status:** V0 applied and validated (flags default **OFF** until burn-in)

## Shipped

| Item | Detail |
|------|--------|
| Telemetry | `apex_ai_telemetry_pack.py` + orchestrator hook |
| API | `GET /api/apex/hal/ai-lane-health` |
| Scheduled audit | `scripts/run_nr2_scheduled_audit.py` → `audit_cron_log.jsonl` |
| Freshness | `apex_sync_status_pack.py` + `nr2-data-freshness.js` |
| API | `GET /api/apex/hal/sync-status` |
| Widgets | `ai-lane-health`, `data-freshness-status` |

## Flags (default OFF)

```text
set NR2_AI_TELEMETRY=1
set NR2_AUDIT_CRON=1
set NR2_DATA_FRESHNESS=1
```

## Ops — monthly audit (1st of month)

```text
set NR2_AUDIT_CRON=1
python scripts/run_nr2_scheduled_audit.py --classify-only
# production: omit --classify-only; use --force for off-schedule tests
```

## Honesty / PHI

- Telemetry stores lane/latency/error codes + query fingerprint only (no text, no $)
- Freshness chips are timestamps only — empty ≠ $0

## Validation

```text
python -m pytest NewRidgeFinancial2/test_apex_phase_v0_burnin.py -q
```
