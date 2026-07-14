# Moonshot AI — What's Next After HAL 190Q Phase 1 (CONSULT ONLY)

**Date:** 2026-07-12  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10561 + hal-local:32b  
**Prior applied:** Phase 1 (`325d24a`) + Phase 2 (`f225b2b`) + Phase 3 (`faa3113`)  
**Script:** `scripts/run_moonshot_hal_190q_whats_next.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> next

---

# Verdict
Execute the live 190Q subset re-run (n≈50) to validate directional lift from Phases 1–3 before committing engineering cycles to Phase 4 hardening or the full n=190 eval.

## 0. Operator Intent (verbatim: next)

## 1. Recommended NEXT (Live 190Q Subset Validation n≈50)
**Why now:** Phases 1–3 are applied but unproven in live execution against real queries. The baseline (26.3% quality, 25% read‑only OK) is catastrophic; we need empirical proof of directional lift before investing in Phase 4 CARC whitelist hardening or the expensive full n=190 run.  
**Effort:** Medium — ~1–2 h compute on R9700 (Q4_K_M 32B) plus 30 min analysis.  
**REAL files:**  
- `scripts/run_moonshot_hal_190q_eval.py` (subset execution)  
- `scripts/hal_eval_scoring.py` (rubric validation)  
- `NewRidgeFinancial2/nr2_hal_gateway.py` (log telemetry only; no code change)  

**Validation gate:**  
- Subset completes without crash or timeout.  
- Quality ≥ 40 % (directional lift from 26.3 %).  
- Read‑only OK ≥ 60 % (lift from 25 %).  
- Deliverable format compliance (numbered steps) ≥ 50 %.  
- Median TTFT < 2 s (Phase 3 streaming efficacy).  
- Zero invented dollars/CARC/PHI.  
**Go/No‑Go:** If gates pass, approve Phase 4; if fail, debug Phase 1–3 implementation before any new features.

## 2. Runner-ups (why not now)
- **Phase 4: CARC Whitelist Hardening** — Adds strict briefs for known CARC codes and refusal templates for unknowns. *Defer* until subset proves the gateway logic is sound; hardening is wasted if base constraint enforcement is still broken.  
- **Full 190Q Re‑run (n=190)** — Complete statistical evaluation. *Defer* because running 190 queries is ~4 h on R9700; validate architecture with n≈50 first to avoid wasting time if fixes are ineffective.  
- **Orchestrator Path Streaming** — Extend Phase 3 SSE streaming to the non‑stream JSON orchestrator path. *Defer*; UX polish is secondary to confirming that answers are correct and compliant.

## 3. What NOT to redo
- **Phase 1:** Post‑generation sentence limits, write/CARC/empty≠$0 preflight, short‑ask `num_predict` caps, rubric recalibration.  
- **Phase 2:** Structured deliverables (JSON schema → numbered markdown), `is_deliverable_request` detection, client‑side step rendering.  
- **Phase 3:** Early SSE `typing`/`ttft` meta, `X-Accel-Buffering: no`, `onToken` accumulation, Apex `askHal` streaming, fake‑typewriter skip.  
Do not re‑apply code changes already marked **APPLIED** in the manifest.

## 4. Acceptance criteria
1. Command executes: `python scripts/run_moonshot_hal_190q_eval.py --subset 50 --model hal-local:32b --warm` (warm cache per REC‑007).  
2. Output `HAL_190Q_SUBSET_2026-07-12.json` generated with 50 scored responses.  
3. Aggregate quality score ≥ 40 % (up from 26.3 %).  
4. Read‑only OK rate ≥ 60 % (up from 25 %).  
5. Deliverable asks rendered as numbered steps ≥ 50 % of the time.  
6. Median TTFT < 2000 ms measured via SSE `ttft` meta events.  
7. Zero hallucinated dollar amounts, CARC code meanings, or PHI.  
8. Comparison report generated: pre‑fix baseline vs. post‑fix subset.

## 5. Executive Summary
- **Validation blocks waste:** The subset is the cheapest way to confirm that Phases 1–3 actually moved the metrics before building Phase 4.  
- **Hardware fit:** n≈50 on R9700 Q4_K_M finishes in under 2 hours; acceptable cost for a go/no‑go decision.  
- **Metric thresholds:** Quality > 40 % and read‑only > 60 % prove the rubric recalibration (Phase 1) and constraint enforcement (Phase 1) are functioning; lower numbers indicate implementation bugs, not model limits.  
- **Streaming sanity check:** TTFT < 2 s validates that Phase 3 SSE changes reduced perceived latency without breaking output correctness.  
- **CARC hardening queued:** Phase 4 (CARC whitelist) is ready to spec but gates on this subset proving the system refuses unknown codes correctly under live load.

## 6. Approval checklist
- [ ] Cache warmed via `apex_hal_cache_warm_pack.py` (REC‑007) to avoid cold‑start latency skew.  
- [ ] Subset size strictly capped at n=50 (operator can override, but 50 is the recommended minimum for directional signal).  
- [ ] Scoring script uses Phase 1 updated rubric (regex for read‑only, not literal match).  
- [ ] Output filenames timestamped to prevent collision with prior runs.  
- [ ] No GitHub PR required; this is local execution and analysis only.  
- [ ] Operator confirms “proceed” on subset results before any work on Phase 4 begins.