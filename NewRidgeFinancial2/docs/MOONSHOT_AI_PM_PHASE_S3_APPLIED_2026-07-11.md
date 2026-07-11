# Phase S3 Applied — Orchestrator opt-in GA / SHOULD closeout

**Date:** 2026-07-11  
**Build:** hal-10479  
**Prior:** S0–S2  
**Status:** SHOULD wave **complete**

## Shipped

| Item | Detail |
|------|--------|
| Pack | `apex_orchestrator_polish_pack.py` |
| Status | `phase=S3`, `shouldWaveComplete=true`, `orchestratorDefault=OFF` |
| Burn-in | Checklist on orchestrator status |
| SSE | Deferred (NICE) |
| Gates | `test_apex_should_wave_s3_gates.py` |

## Feature flag (unchanged default)

| Flag | Default | Effect |
|------|---------|--------|
| `NR2_AI_ORCHESTRATOR` | **OFF** | Opt-in only. Rollback: `=0` |

Enable for burn-in:

```text
$env:NR2_AI_ORCHESTRATOR = "1"
```

## SHOULD wave map

| Phase | Deliverable |
|-------|-------------|
| S0 | QB payroll/AP + unified tables |
| S1 | ERA aggregates + `ERA_835_AVAILABLE` |
| S2 | Proactive health monitor CLI |
| S3 | Opt-in GA docs + closeout gates |

## Validation

```text
python -m pytest NewRidgeFinancial2/test_apex_should_wave_s3_gates.py NewRidgeFinancial2/test_apex_qb_payroll_s0.py NewRidgeFinancial2/test_apex_softdent_era_s1.py NewRidgeFinancial2/test_apex_health_monitor_s2.py NewRidgeFinancial2/test_apex_ai_pm_i4_gates.py -q
```

**Honesty locked:** never invent $; empty ≠ $0; no SoftDent write-back; SSN redact on payroll; ERA proposals only.
