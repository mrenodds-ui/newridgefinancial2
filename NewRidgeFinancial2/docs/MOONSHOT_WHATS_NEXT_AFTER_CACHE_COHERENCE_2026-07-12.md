# Moonshot AI — What's Next After Cache Coherence (CONSULT ONLY)

**Date:** 2026-07-12  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10563 + hal-local:32b  
**Prior:** KPI density (`9d6d021`); cache coherence (`8388b9a`); Phase 5 aborted  
**Script:** `scripts/run_moonshot_whats_next_after_cache_coherence_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> next

---

# Verdict
Repair and complete the aborted HAL 190Q Phase 5 evaluation by hardening the test harness against `empty_response` timeouts in the analytical lane, then finish the full 190-question measurement to validate Phase 1–4 safety boundaries before any data-export work.

## 0. Operator Intent (verbatim: next)

## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)

**Name:** HAL 190Q Phase 5 — Harness Hardening & Completion Run  
**Why now:** Phase 4 CARC whitelist and read-only guarantees are applied but remain unvalidated. The Phase 5 run aborted at query ~11 due to `reason21b` lane `empty_response` (42–56s timeouts), causing the harness to exit early instead of scoring the failure and continuing. Without completing the full 190Q measurement, we cannot verify the ≥85% quality / 100% read-only / ≤15s latency targets, blocking the production go/no-go decision.  
**Effort:** Medium (4–6 hours) — instrument Ollama timeout behavior, add eval resilience, resume from partial state, complete remaining ~11–179 queries.  
**REAL files:**  
- `scripts/run_moonshot_hal_190q_phase5_eval.py` — wrap `evaluate_query` in try/except to catch `empty_response` and `reason21b` lane timeouts; continue run instead of `sys.exit(1)`; add `--resume-from` flag to consume `.local_logs/.../HAL_190Q_POST_PHASE4_PARTIAL_2026-07-12.json`  
- `NewRidgeFinancial2/nr2_hal_gateway.py` — audit `request_timeout` handling for `hal-local:32b` lane; ensure Ollama 60s ceiling is respected or extend client timeout; add `empty_response` detection vs. `None` content  
- `NewRidgeFinancial2/apex_hal_cache_warm_pack.py` — verify cache warming does not leave `hal-local:32b` in a locked/broken state that causes subsequent analytical queries to fail  
- `scripts/hal_eval_scoring.py` — ensure `empty_response` and `reason21b` timeouts score as `qualityPass: false` and `latency: null` without halting the batch  
- `.local_logs/.../HAL_190Q_POST_PHASE4_PARTIAL_2026-07-12.json` — baseline for resume/comparison  

**Validation gate:**  
- Full `HAL_190Q_PHASE5_COMPLETE_2026-07-12.json` with 190/190 queries measured  
- Metrics: quality ≥85%, read-only 100%, avg latency ≤15s, CARC halluc 0%  
- Harness log shows `empty_response` handled gracefully (counted as failure, not abort)

## 2. Runner-ups (2–3, why not now)

- **Collections/Daysheet Export Gap:** Empty revenue-composition data is a data completeness issue, but fixing it before validating safety boundaries risks building on unverified read-only guarantees. Do after Phase 5 confirms CARC whitelist holds.  
- **SoftDent SQLite Lock Residual:** Connect timeout fixes shipped; remaining locks are lower severity than analytical lane timeouts blocking evaluation. Can wait for Phase 5 completion.  
- **Browser Smoke of hal-10562/10563:** KPI density and cache coherence already have manual validation steps in their shipped docs; automated smoke is nice-to-have but does not unblock production decisions.

## 3. What NOT to redo

- KPI density (hal-10562) — already applied  
- Cache coherence (hal-10563) — already applied  
- Phases 1–4 evaluation harnesses — baseline is set  
- WHY-ERRORS connect timeout logic — shipped  
- REC-007 model warming — untouched and working  
- Do not invent SoftDent write-back or dollar amounts where data is empty

## 4. Acceptance criteria

1. `run_moonshot_hal_190q_phase5_eval.py` runs to completion (190/190) without exiting on `empty_response`  
2. `reason21b` lane timeouts are diagnosed (Ollama log correlation) and either fixed (timeout config) or isolated (fallback to `hal-10563` base model)  
3. Final JSON contains `quality_score`, `read_only_violations`, `avg_latency_ms`, `carc_hallucinations` for all 190 queries  
4. Quality ≥85%, read-only 100%, avg latency ≤15s, CARC halluc 0%  
5. Partial JSON from abort is preserved for comparison but superseded by complete run

## 5. Executive Summary (5 bullets)

- Phase 5 aborted due to fragile harness behavior on `empty_response`, not model policy failure  
- Analytical lane (`reason21b` / `hal-local:32b`) experiencing 42–56s timeouts suggests Ollama client default timeout mismatch or model state corruption  
- Phase 1–4 safety guarantees (CARC whitelist, read-only) are code-complete but measurement-incomplete; production go/no-go is blocked  
- Next package hardens harness resilience, diagnoses timeout root cause, and completes the 190Q validation run  
- Data-export features (Collections/Daysheet) queue behind safety validation to avoid building on unverified foundations

## 6. Approval checklist

- [ ] Harness catches `empty_response` and continues (does not `exit 1`)  
- [ ] Ollama/`hal-local:32b` timeout audited and aligned (≥60s or explicit client override)  
- [ ] Resume-from-partial logic consumes existing 179-record JSON without double-counting  
- [ ] Scoring logic treats timeouts as quality failures, not crashes  
- [ ] Full 190Q run completes with metrics meeting quality/latency/read-only targets  
- [ ] Operator approves proceeding to Collections/Daysheet export only after Phase 5 validation passes