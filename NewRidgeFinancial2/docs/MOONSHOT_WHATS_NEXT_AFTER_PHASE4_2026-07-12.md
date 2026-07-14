# Moonshot AI — What's Next After HAL 190Q Phase 4 (CONSULT ONLY)

**Date:** 2026-07-12  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10561 + hal-local:32b  
**Prior applied:** Phase 4 (`39cf104`) + WHY-ERRORS (`2cbef60`) + Phase 1–3 (`325d24a`/`f225b2b`/`faa3113`)  
**Script:** `scripts/run_moonshot_whats_next_after_phase4_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> next

---

# Verdict
Execute the deferred **Live 190Q Full Re-run** to measure Phase 1–4 aggregate lift against the baseline (26.3% quality, 25% read-only OK, 52s latency) and validate that CARC whitelist hardening + constraint enforcement materially moved the safety and brevity metrics before proceeding to data-gap remediation.

## 0. Operator Intent (verbatim: next)

## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)

**Name:** HAL 190Q Phase 5 — Live Full Re-run & Metric Validation  
**Why now:** Phase 4 (CARC whitelist) closed the last major hallucination vector. The evaluation was explicitly deferred until Phase 4 landed to capture the complete safety boundary. Measurement is now the highest ROI action: it determines whether Phases 1–4 achieved the target >85% quality / 100% read-only compliance or if additional gateway tuning is required before addressing data-export gaps.  
**Effort:** Low (1 day execution + 1 day analysis) — purely evaluative; no production code changes; uses existing harness.  
**REAL files:**  
- `scripts/run_moonshot_hal_190q_eval.py` — execute full 190-query suite against current `hal-10561 + hal-local:32b`  
- `scripts/hal_eval_scoring.py` — verify updated regex for read-only detection (Phase 1 fix) captures local-policy refusals correctly  
- `NewRidgeFinancial2/nr2_hal_gateway.py` — audit target for measuring latency improvement from streaming (Phase 3) and constraint enforcement (Phase 1)  
**Validation gate:**  
1. Generate `HAL_190Q_EVAL_POST_PHASE4_2026-07-13.json`  
2. Quality pass rate ≥85% (up from 26.3%) and Read-only OK = 100% (up from 25%)  
3. Avg latency ≤15s (down from 52s) confirming TTFT streaming impact  
4. CARC hallucination rate = 0% (new metric verified via `test_carc_whitelist.py` integration in eval)  
5. Report delivered: `MOONSHOT_HAL_190Q_PHASE5_REPORT_2026-07-13.md` with go/no-go recommendation for production release

## 2. Runner-ups (2–3, why not now)

- **Collections/Daysheet export gap → empty revenue-composition** — High data-honesty ROI, but fixing empty aggregates requires SoftDent schema mapping and new CSV parsers; defer until Phase 5 confirms HAL responses are trustworthy (quality >85%) so staff aren’t acting on bad AI summaries while we fix data pipelines.  
- **Expand CARC whitelist beyond 25/10 codes** — Additive but lower leverage; current whitelist covers 90%+ of NR2’s observed ERA volume per `apex_era835_pack.py` ingest logs; expand only if Phase 5 eval shows remaining hallucinations cluster on specific uncovered codes.  
- **QB Payroll/AP atomic CSV polish** — Already shipped (REC-005/007/008/009); no further work required unless Phase 5 reveals new edge cases.

## 3. What NOT to redo

- **HAL 190Q Phases 1–4** — Constraint enforcement, structured deliverables, streaming TTFT, and CARC whitelist are applied and committed (39cf104, 325d24a, f225b2b, faa3113).  
- **WHY-ERRORS** — SQLite lock timeout/busy_timeout fixes (2cbef60) are in production.  
- **SoftDent write-back** — Explicitly prohibited; do not invent patient ledger updates or dollar amounts.  
- **GitHub/PR process** — Keep work local to `scripts/` and `NewRidgeFinancial2/`; no repository ceremony.

## 4. Acceptance criteria

- [ ] Full 190Q suite completes with 0% crash/hang rate  
- [ ] Quality pass rate ≥85% (brevity constraints honored)  
- [ ] Read-only OK = 100% (local-policy refusals scored correctly)  
- [ ] CARC/CAS hallucination rate = 0% (unknown codes hard-refuse)  
- [ ] Latency p50 ≤15s, p95 ≤30s (streaming TTFT validated)  
- [ ] Report issued with go/no-go verdict for staff production use  
- [ ] If criteria fail, rollback plan to Phase 1–4 tuning documented (do not proceed to Collections gap)

## 5. Executive Summary (5 bullets)

- Phase 4 CARC whitelist is now live, closing the final hallucination vector for ERA 835 codes.  
- We deferred the full evaluation specifically to measure the complete Phase 1–4 safety boundary; that boundary is now sealed.  
- A live re-run is the only way to verify that constraint enforcement (Phase 1), streaming (Phase 3), and CARC hardening (Phase 4) moved the baseline metrics (26.3% quality, 52s latency) to production-ready thresholds.  
- If validation passes, the next package will address the Collections/Daysheet export gap; if it fails, we tune the existing gateway logic rather than adding new surface area.  
- Zero code changes required—this is pure measurement using existing real paths (`scripts/run_moonshot_hal_190q_eval.py`).

## 6. Approval checklist

- [ ] Operator confirms `scripts/run_moonshot_hal_190q_eval.py` is latest version (post-Phase 4)  
- [ ] `hal-local:32b` model file confirmed on disk (R9700)  
- [ ] Baseline metrics (26.3% quality, 25% read-only, 52s latency) acknowledged as comparison point  
- [ ] Output report path `MOONSHOT_HAL_190Q_PHASE5_REPORT_2026-07-13.md` approved  
- [ ] Commit to abide by go/no-go criteria (do not skip to Collections gap if metrics fail)