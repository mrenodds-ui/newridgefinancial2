# Moonshot AI — What's Next After WHY-ERRORS + HAL 190Q Phase 1–3 (CONSULT ONLY)

**Date:** 2026-07-12  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10561 + hal-local:32b  
**Prior applied:** WHY-ERRORS (`2cbef60`) + Phase 1 (`325d24a`) + Phase 2 (`f225b2b`) + Phase 3 (`faa3113`)  
**Script:** `scripts/run_moonshot_whats_next_after_why_errors_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> next

---

# Verdict
**Phase 4: CARC whitelist hardening** — complete the ERA 835 safety story by curating authoritative briefs for known CARC/CAS codes so HAL references fact rather than generating speculative interpretations.

## 0. Operator Intent (verbatim: next)

## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)

**Name:** HAL 190Q Phase 4 — CARC/CAS Whitelist Hardening  
**Why now:** Phase 1 blocked unknown-code hallucinations; however, the evaluation showed sparse, inconsistent explanations for *known* codes (e.g., CO-45, PR-2, OA-23). Staff asking “What does CARC 45 mean?” receive varying answers depending on model temperature. Completing the whitelist closes the last major hallucination vector in ERA 835 workflows before the next eval run.  
**Effort:** Medium (2–3 days) — curate top 25 CARC + 10 CAS briefs from CMS X12 835 spec, wire lookup, gate on `apex_era835_pack.py` context.  
**REAL files:**  
- `NewRidgeFinancial2/era835_parser.py` — add `CARC_BRIEFS` constant/map (code → one-sentence plain-language brief + action hint)  
- `NewRidgeFinancial2/apex_era835_pack.py` — inject briefs into HAL context when packing ERA lines; skip if code not in whitelist (falls back to Phase 1 refusal)  
- `NewRidgeFinancial2/nr2_hal_gateway.py` — `try_local_policy_reply` consults whitelist for “explain CARC X” queries before hitting LLM  
- `NewRidgeFinancial2/site/hal-core.js` — render CARC briefs in monospace/code styled blocks to distinguish from narrative  
**Validation gate:**  
1. Unit test `test_carc_whitelist.py`: Known code CO-45 returns “Contractual obligation; do not bill patient” from map, not model generation.  
2. Unknown code XX-99 still triggers Phase 1 refusal (“I cannot interpret this code; escalate to posting supervisor”).  
3. 190Q subset re-run shows 0% CARC hallucination rate (down from baseline).

## 2. Runner-ups (2–3, why not now)

- **Live 190Q subset/full re-run to measure Phase 1–3 lift** — Critical for validation, but purely evaluative; defer 48 hours until Phase 4 hardening lands so the re-run captures the complete CARC safety boundary rather than a partial fix.  
- **Collections/Daysheet export gap → empty revenue-composition** — High data-honesty ROI, but the pipeline fix requires SoftDent schema investigation and potentially new CSV parsers; higher risk than the CARC lookup table and less urgent than closing the HAL hallucination vector.  
- **QB payroll/AP atomic CSV → document-inbox polish** — Already shipped (REC-009 context); any remaining work is UI sugar, lower leverage than CARC correctness.

## 3. What NOT to redo

- WHY-ERRORS SQLite lock fixes (timeout/PRAGMA already applied)  
- HAL 190Q Phases 1–3 (constraints, structured deliverables, streaming TTFT)  
- SoftDent write-back prohibition (already enforced)  
- Empty ≠ $0 preflight (already enforced)  
- CARC unknown-code refusal (Phase 1 complete)

## 4. Acceptance criteria

- [ ] Curated whitelist covers top 25 CARC and 10 CAS codes found in last 90 days of production 835s (source: `era835_parser.py` historical scan)  
- [ ] Briefs are ≤140 characters, plain language, cite no PHI, and include “Staff Action:” hint when patient responsibility is involved  
- [ ] `apex_era835_pack.py` injects whitelist brief into HAL context; if code absent, hard refusal (no model fallback)  
- [ ] HAL responses for “What is CARC 45?” match whitelist text within Levenshtein distance ≤5 (exact citation)  
- [ ] No regression on streaming latency (TTFT < 800ms)  
- [ ] `test_carc_whitelist.py` passes; 190Q eval shows 100% CARC compliance (known = brief, unknown = refuse)

## 5. Executive Summary (5 bullets)

- **Scope:** Close the ERA 835 interpretation gap by replacing model-generated CARC explanations with a curated, version-controlled whitelist.  
- **Safety:** Unknown codes already refused in Phase 1; Phase 4 stops variable “best guess” explanations for known codes.  
- **Files:** Touch parser (data), pack (context), gateway (policy), and front-end (rendering) — all existing real paths.  
- **Validation:** Unit tests + 190Q eval subset; success = zero hallucination on sampled codes.  
- **Honesty:** Briefs cite CMS X12 835 guide only; no invented dollar amounts, no PHI, no speculative “this means patient pays $X.”

## 6. Approval checklist

- [ ] Operator confirms Phase 4 priority over immediate 190Q re-run  
- [ ] Source of truth for CARC briefs identified (CMS X12 835 TR3 vs. internal revenue-cycle SOP)  
- [ ] SoftDent/ERA export sample reviewed to confirm top 25 code list  
- [ ] No new dependencies (sqlite3/json only)  
- [ ] Rollback plan: Delete whitelist constant to restore Phase 1 behavior (unknown refuse only)