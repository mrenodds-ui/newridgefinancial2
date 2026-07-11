# Phase N0 Applied — Insight SSE / live widget binding (NICE)

**Date:** 2026-07-11  
**Build:** hal-10480  
**Prior:** SHOULD S0–S3 (hal-10479)  
**Status:** N0 validated

## Shipped

| Item | Detail |
|------|--------|
| Pack | `apex_insight_sse_pack.py` |
| SSE | `GET /api/apex/hal/insight-stream` (`text/event-stream`) |
| Latest | `GET /api/apex/hal/insight-latest` (5s poll fallback) |
| Status | `GET /api/apex/hal/insight-sse-status` |
| Client | `site/nr2-insight-sse.js` — EventSource + 5s poll; patches `hal-ai-insight` |
| Flag | Orchestrator still default **OFF** |

## Honesty

- Stream only emits schema-validated last insight (no invented $)
- Empty insight → empty widget status

## Validation

```text
python -m pytest NewRidgeFinancial2/test_apex_insight_sse_n0.py NewRidgeFinancial2/test_apex_should_wave_s3_gates.py -q
```

## Smoke

1. Open HAL page in Chrome  
2. DevTools → Network → `insight-stream` → type `event-stream`  
3. Ask HAL for a structured insight (with orchestrator on) → widget updates without full reload  

## Next

Orchestrator default ON remains **opt-in only** until you explicitly approve GA flip.
