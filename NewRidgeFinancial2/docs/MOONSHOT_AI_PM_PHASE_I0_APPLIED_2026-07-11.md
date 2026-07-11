# Phase I0 Applied — AI Orchestrator Shell

**Date:** 2026-07-11  
**Build:** hal-10471 (I0)  
**Plan:** AI Program Manager Upgrade  
**Consult:** `MOONSHOT_AI_PROGRAM_MANAGER_UPGRADE_CONSULT_2026-07-11.md`  
**Status:** Phase I0 only — validated; **stop for I1 approval**

## Shipped

| Item | Detail |
|------|--------|
| Orchestrator pack | `apex_orchestrator_pack.py` — `classify_intent`, `orchestrate`, feature flag |
| Flag | `NR2_AI_ORCHESTRATOR=1` (default **OFF**) |
| APIs | `GET /api/apex/hal/orchestrator`, `POST /api/apex/hal/orchestrate` (+ `classifyOnly`) |
| HAL status | Includes `orchestrator` block |
| Apex chat | When flag on, uses `/hal/orchestrate` after board-actions (no forced chat8b) |
| Tests | `test_apex_orchestrator_i0.py` |

## Lane contracts (I0)

- **Deep → escalate30b:** forecast, monthly health audit, SoftDent×QB cross-ref, why-trend, second opinion
- **Fast → chat8b:** summarize, focus, show, parse (short)
- **Else:** existing `route_by_complexity` (keeps reason21b financial math)

## Validation

```text
python -m pytest NewRidgeFinancial2/test_apex_orchestrator_i0.py -q
```

Expect: all passed (no Ollama required for classify tests).

## Enable on workstation

```text
set NR2_AI_ORCHESTRATOR=1
```

Restart NR2. With flag off, behavior unchanged (evaluate-query + forced chat8b path).

## Not in I0 (next phases)

- I1 Structured JSON insight schemas  
- I2 SoftDent Collections gap  
- I3 Unified SQLite  
- I4 Closeout gates  

**Await:** approve I1 to continue.
