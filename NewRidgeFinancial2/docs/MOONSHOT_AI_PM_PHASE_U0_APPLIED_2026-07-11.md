# Phase U0 Applied — Deep Audit & Forecast (Moonshot REAUDIT3 MUST)

**Date:** 2026-07-11  
**Build:** hal-10482  
**Consult:** `MOONSHOT_AI_PROGRAM_MANAGER_UPGRADE_REAUDIT3_2026-07-11.md`  
**Status:** U0 applied and validated (classify-only gates; no Ollama required)

## Shipped

| Item | Detail |
|------|--------|
| Pack | `apex_deep_audit_pack.py` |
| CLI | `scripts/run_nr2_deep_audit.py` (`--classify-only`, `--forecast`, `--period`) |
| APIs | `GET …/deep-audit-status`, `POST …/deep-audit`, `POST …/deep-forecast` |
| Widget | `deep-audit-status` on Financial |
| Flag | `NR2_DEEP_AUDIT` default **ON** (`=0` to disable) |
| SSE | Gap/trend insights → `save_last_insight` (N0 stream picks up) |

## Honesty

- Empty unified views → `AUDIT_DATA_PENDING` / gap alert (value `null`) — never invent $
- Forecast asterisk months are **null** placeholders until 30B returns validated JSON
- No SoftDent write-back; no PHI in snapshot

## Ops

```text
python scripts/run_nr2_deep_audit.py --classify-only
python scripts/run_nr2_deep_audit.py --forecast --classify-only
# full 30B (orchestrator default ON): omit --classify-only
```

On-demand via HAL APIs or Task Scheduler (same pattern as S2 health monitor).

## Validation

```text
python -m pytest NewRidgeFinancial2/test_apex_deep_audit_u0.py -q
```

## Rollback

```text
set NR2_DEEP_AUDIT=0
```
