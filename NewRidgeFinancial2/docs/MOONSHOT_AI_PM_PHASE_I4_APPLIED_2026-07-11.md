# Phase I4 Applied — MUST-wave closeout (integration gates + feature-flag smoke)

**Date:** 2026-07-11  
**Build:** hal-10475  
**Plan:** AI Program Manager Upgrade  
**Prior:** I0 orchestrator · I1 structured insights · I2 Collections honesty · I3 unified SQLite  
**Status:** MUST wave **complete** (I0–I4)

## Shipped

| Item | Detail |
|------|--------|
| Gates | `test_apex_ai_pm_i4_gates.py` — cross-phase contracts, no Ollama |
| Status | Orchestrator `phase=I4`, `mustWaveComplete=true` |
| Flag doc | See **Feature-flag smoke** below |
| Closeout | This doc — MUST wave locked; SHOULD deferred |

## Feature-flag smoke

| Flag | Default | Effect |
|------|---------|--------|
| `NR2_AI_ORCHESTRATOR` | **OFF** | When `1`/`true`/`on`: Apex HAL chat uses `/api/apex/hal/orchestrate` after board-actions (8B fast / 30B deep). When off: prior evaluate-query + chat8b path unchanged. |

Enable (PowerShell):

```text
$env:NR2_AI_ORCHESTRATOR = "1"
```

Then restart NR2. Smoke checklist:

1. `GET /api/apex/hal/orchestrator` → `enabled: true`, `phase: "I4"`, `mustWaveComplete: true`
2. `POST /api/apex/hal/orchestrate` with `{"query":"Forecast next month","classifyOnly":true}` → `lane: escalate30b`
3. SoftDent Collections empty → DEF-001 / `softdent-collections-gap` (not $0)
4. Sync → `GET /api/apex/unified/snapshot` returns periods (additive `nr2_unified.db`)
5. Insight JSON with SSN → `POST /api/apex/hal/insight-validate` rejects PHI

## Validation

```text
python -m pytest NewRidgeFinancial2/test_apex_ai_pm_i4_gates.py NewRidgeFinancial2/test_apex_unified_db_i3.py NewRidgeFinancial2/test_apex_softdent_hardening_i2.py NewRidgeFinancial2/test_apex_structured_insight_i1.py NewRidgeFinancial2/test_apex_orchestrator_i0.py -q
```

## MUST wave map (done)

| Phase | Build | Deliverable |
|-------|-------|-------------|
| I0 | hal-10471 | Orchestrator shell + flag |
| I1 | hal-10472 | Structured JSON insights |
| I2 | hal-10473 | SoftDent Collections honesty (DEF-001) |
| I3 | hal-10474 | Additive `nr2_unified.db` |
| I4 | hal-10475 | Integration gates + closeout |

## Not in MUST (SHOULD later)

- ERA 835 harden  
- QB payroll / AP automation  
- Proactive background health monitor  

**Honesty invariants (locked):** never invent dollars; Collections empty ≠ $0; no SoftDent write-back; orchestrator off until flagged.
