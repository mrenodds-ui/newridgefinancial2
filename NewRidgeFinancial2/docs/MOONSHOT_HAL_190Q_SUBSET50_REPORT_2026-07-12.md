# Moonshot HAL 190Q Subset Re-run (n=50) — Phase 1–3 Validation

**Date:** 2026-07-12  
**Operator:** proceed (live 190Q subset re-run after Phase 1–3)  
**Build:** hal-10561 + Phase 1–3 (`325d24a` / `f225b2b` / `faa3113`)  
**Script:** `scripts/run_moonshot_hal_190q_subset50.py`  
**Questions:** reused `HAL_190Q_QUESTIONS_2026-07-12.json` (seed=19050)  
**Artifact:** `HAL_190Q_SUBSET50_EVAL_2026-07-12.json`

## Scorecard vs baseline (full 190Q)

| Metric | Baseline (n=190) | Subset (n=50) | Target |
|--------|------------------|----------------|--------|
| Success rate | 100.0% | **100.0%** | 100% |
| Quality pass | 26.3% | **98.0%** | ≥75% |
| Read-only OK | 25.0% | **100.0%** | ≥90% |
| Consent OK | 75.0% | **100.0%** | ≥90% |
| Deliverable rate | 27.9% | **100.0%** | ≥70% |
| Avg latency | 52830.7 ms | **10397.8 ms** | <45s |
| CoT leak | 0.0% | **0.0%** | 0% |

## Lane mix (subset)

```json
{
  "chat8b": 27,
  "escalate30b": 3,
  "local": 11,
  "reason21b": 9
}
```

## Go / no-go for Phase 4

- Quality ≥75%: **PASS**
- Read-only ≥90%: **PASS**
- Avg latency <45s: **PASS**

If quality/read-only miss targets, Phase 4 CARC briefs + failure triage next.  
If targets hit, prefer full n=190 burn-in or Phase 4 as polish only.
