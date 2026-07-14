# Moonshot HAL 190Q Phase 5 Report — Full Re-run After Phase 1–4

**Date:** 2026-07-12  
**Operator:** proceed (Phase 5 full 190Q after abort / think-flag fix)  
**Build:** Phase 1–4 + `hal-local` think-flag fix (`9b7d4eb`)  
**Script:** `scripts/run_moonshot_hal_190q_phase5_eval.py`  
**Artifact:** `HAL_190Q_EVAL_POST_PHASE4_2026-07-12.json`

## Scorecard

| Metric | Baseline n=190 | Subset50 | Phase 5 n=190 | Target |
|--------|----------------|----------|---------------|--------|
| Success | 100.0% | 100.0% | **100.0%** | 100% |
| Quality | 26.3% | 98.0% | **98.4%** | ≥85% |
| Read-only OK | 25.0% | 100.0% | **100.0%** | 100% |
| Consent OK | 75.0% | 100.0% | **100.0%** | — |
| Deliverable | 27.9% | 100.0% | **100.0%** | ≥70% |
| Avg latency | 52830.7 ms | 10397.8 ms | **14076.9 ms** | ≤15s |
| CoT leak | 0.0% | 0.0% | **0.0%** | 0% |
| Empty fails | — | — | **0** | 0 |

## Lane mix

```json
{
  "chat8b": 88,
  "escalate30b": 7,
  "local": 30,
  "reason21b": 65
}
```

## Gates

- Quality ≥85%: **PASS**
- Read-only 100%: **PASS**
- Avg latency ≤15s: **PASS**
- Zero empty_response: **PASS**

## Go / no-go

**GO** — Phase 1–4 safety/latency targets met on full 190Q.
