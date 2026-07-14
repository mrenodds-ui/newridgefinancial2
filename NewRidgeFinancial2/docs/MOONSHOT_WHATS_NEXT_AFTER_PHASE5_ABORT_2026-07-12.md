# Moonshot AI — What's Next After Phase 5 Abort (CONSULT ONLY)

**Date:** 2026-07-12  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10561 + hal-local:32b  
**Prior:** Phase 4 (`39cf104`); Phase 5 aborted at ~11/190 (empty_response)  
**Script:** `scripts/run_moonshot_whats_next_after_phase5_abort_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> next

---

# Verdict
Repair the aborted Phase 5 evaluation by hardening the test harness against `reason21b` lane timeouts and diagnosing the Ollama empty-response failure, then complete the full 190Q measurement to validate Phase 1–4 safety boundaries before proceeding to data-export features.

## 0. Operator Intent (verbatim: next)

## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)

**Name:** HAL 190Q Phase 5 — Diagnostic Repair & Completion Run  
**Why now:** Phase 4 safety hardening (CARC whitelist) is applied but unvalidated. The Phase 5 run aborted at query 11/190 due to `empty_response` failures in the `reason21b` lane (42–56s timeouts), preventing measurement against the ≥85% quality / 100% read-only / ≤15s latency targets. Without completing this evaluation, we cannot distinguish between "local-policy lane is fast and correct" (confirmed Q1–7, 11) and "analytical lane is broken," leaving the go/no-go decision for production blocked.  
**Effort:** Medium (4–6 hours) — debug Ollama/hal-local:32b timeout behavior, add eval harness resilience, complete 179 remaining queries.  
**REAL files:**  
- `scripts/run_moonshot_hal_190q_phase5_eval.py` — add try/except around `evaluate_query` to prevent exit 1 on empty_response; log raw Ollama response for diagnosis  
- `NewRidgeFinancial2/nr2_hal_gateway.py` — audit `evaluate_query` timeout handling for `hal-local:32b` lane; verify `request_timeout` vs Ollama’s default 60s ceiling  
- `NewRidgeFinancial2/apex_hal_cache_warm_pack.py` — confirm cache warming does not pin the model into a bad state that causes subsequent analytical queries to fail  
- `scripts/hal_eval_scoring.py` — ensure `empty_response` is scored as `qualityPass: false` but does not halt the runner  
**Validation gate:**  
1. Resume eval from Q12 or restart; complete 190/190 queries without process exit 1  
2. Zero unhandled exceptions; all `empty_response` events captured in log with full HTTP trace  
3. Generate final `HAL_190Q_EVAL_POST_PHASE4_2026-07-13.json` and `MOONSHOT_HAL_190Q_PHASE5_REPORT_2026-07-13.md`  
4. Confirm metrics: Quality ≥85%, Read-only OK = 100%, Avg latency ≤15s, CARC halluc 0%  
5. Deliver go/no-go recommendation; if `reason21b` remains unstable, recommend forcing analytical queries to local-policy lane with refusal note rather than allowing Ollama timeouts

## 2. Runner-ups (2–3, why not now)

- **Collections/Daysheet export gap → empty revenue-composition**  
  *Why not now:* This is a data-export feature enhancement. It is premature to build revenue-composition exports until we validate that the HAL gateway meets safety and latency targets (Phase 5). Adding data features on top of an unmeasured/unstable analytical lane risks exporting incorrect interpretations.

- **SoftDent write-back / automated posting**  
  *Why not now:* Explicitly out of scope per operator constraints ("do not invent SoftDent write-back / dollars"). Additionally, write-back requires 100% read-only validation (Phase 5 gate) to ensure no hallucinated dollars reach the practice management system.

## 3. What NOT to redo

- **Phases 1–4** (`325d24a`, `f225b2b`, `faa3113`, `39cf104`) — already applied; local-policy routing, streaming TTFT, and CARC whitelist are live.  
- **WHY-ERRORS** (`2cbef60`) — error taxonomy and logging already shipped.  
- **New CARC/CAS briefs** — the 25/10 whitelist is sufficient for evaluation; do not expand the dictionary until metrics confirm the current boundary works.

## 4. Acceptance criteria

- [ ] `scripts/run_moonshot_hal_190q_phase5_eval.py` runs to completion (190 queries) without `SystemExit` or unhandled `EmptyResponseError`  
- [ ] All `reason21b` lane failures (Q8–10 pattern) are logged with: raw HTTP status, response headers, timing breakdown (TTFT vs total), and Ollama server logs if available  
- [ ] If `hal-local:32b` returns empty after 45s, harness marks `qualityPass: false`, `error: "empty_response_timeout"`, and continues to next query  
- [ ] Final report includes: aggregate quality %, read-only compliance %, latency histogram (p50/p95), CARC hallucination rate (must be 0%), and root-cause note on reason21b instability  
- [ ] Report contains explicit **GO** (meets targets) or **NO-GO** (requires lane fallback or timeout tuning) recommendation

## 5. Executive Summary (5 bullets)

- **Phase 5 aborted at Q11/190** due to `reason21b` lane returning `empty_response` after 42–56s, causing the eval script to exit 1 prematurely  
- **Local-policy lane validated** — Q1–7 and Q11 processed in <1ms with correct refusals/answers, confirming Phases 1–4 local routing works  
- **Measurement blocker** — cannot confirm ≥85% quality or ≤15s latency targets with 94% of queries unmeasured; safety ROI of Phase 4 whitelist remains unquantified  
- **Root cause hypothesis** — Ollama `hal-local:32b` (Qwen3-32b Q4_K_M) timing out on analytical/insurance_ops prompts; may require timeout extension, context window management, or lane fallback  
- **Next action** — harden harness to survive empty responses, diagnose Ollama logs, complete 179 remaining queries, and deliver go/no-go report before addressing Collections/Daysheet data gaps

## 6. Approval checklist

- [ ] Operator confirms: Do not proceed to Collections/Daysheet until Phase 5 metrics are complete  
- [ ] Operator confirms: Acceptable to modify `run_moonshot_hal_190q_phase5_eval.py` to add exception handling (no production code changes, only test harness)  
- [ ] Operator confirms: If `reason21b` continues to fail, fallback to local-policy refusal ("I cannot answer analytical questions at this time; escalate to supervisor") is preferred over allowing timeouts  
- [ ] Resource check: R9700 GPU available for extended 190Q run without interrupting production Apex HAL  
- [ ] Log retention: `.local_logs/` directory has disk space for full 190Q JSON artifacts