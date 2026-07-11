# Phase S2 Applied — Proactive health monitor

**Date:** 2026-07-11  
**Build:** hal-10479  
**Prior:** S1 ERA harden  
**Status:** Phase S2 validated

## Shipped

| Item | Detail |
|------|--------|
| Pack | `apex_health_monitor_pack.py` |
| CLI | `scripts/run_nr2_health_monitor.py` (`--classify-only` for dry-run) |
| Gate | Requires `NR2_AI_ORCHESTRATOR=1` else `orchestrator_disabled` |
| Persist | `import_health_log` row `proactive_audit` |

## Schedule (ops)

```text
set NR2_AI_ORCHESTRATOR=1
python scripts/run_nr2_health_monitor.py --classify-only
```

Wire full runs (no `--classify-only`) via Windows Task Scheduler daily after burn-in.

## Validation

```text
python -m pytest NewRidgeFinancial2/test_apex_health_monitor_s2.py -q
```
