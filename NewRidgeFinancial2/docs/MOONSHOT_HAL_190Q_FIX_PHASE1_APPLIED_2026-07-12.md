# Moonshot HAL 190Q Fix — Phase 1 APPLIED

**Date:** 2026-07-12  
**Consult:** `MOONSHOT_HAL_190Q_FIX_CONSULT_2026-07-12.md`  
**Source eval:** `MOONSHOT_HAL_190Q_REPORT_2026-07-12.md` / `HAL_190Q_EVAL_2026-07-12.json`  
**Operator:** proceed  

## Goal

Raise operational quality after the 190Q run (quality 26.3%, read-only OK 25%, ~53s avg) by enforcing post-generation constraints, hard write/CARC preflight, short-ask `num_predict` caps, and recalibrating the eval rubric so policy-compliant refusals are not false-failed.

## Applied (real paths)

| Piece | Where |
|-------|--------|
| Sentence-limit parse + post-gen cap / plain-language strip | `nr2_hal_gateway.apply_response_constraints`, `sentence_limit_from_query` |
| Clean/extract pass query into constraints | `clean_gateway_text`, `extract_ollama_message_text` |
| Short-ask latency caps (`num_predict`) | `options_for_query` → `evaluate_query`, `evaluate_query_stream`, SSE |
| Write-intent SoftDent/QB preflight before LLM | `try_local_policy_reply` |
| Unknown CARC/CAS refuse (no invention) | `try_local_policy_reply` + `_KNOWN_CAS_CODES` |
| Empty payroll/AP ≠ $0 | `try_local_policy_reply` |
| Two-sentence HAL summary local reply | `try_local_policy_reply` |
| Read-only / consent / deliverable rubric fix | `scripts/hal_eval_scoring.py` |
| Deliverable required only when ask implies steps | `score_answer` + `_needs_deliverable` |
| Tests | `test_nr2_hal_local_policy.py`, `scripts/test_hal_eval_scoring.py` |

## Not in this phase

- Phase 2 structured JSON deliverables  
- Phase 3 perceived-latency SSE UX polish beyond existing stream path  
- Loading a second 8B model beside `hal-local:32b`  

## Honesty

- Empty ≠ $0; no invented dollars / CARC meanings / PHI  
- Local policy blocks SoftDent write-back and QB post without inventing ledger amounts  
- Rubric accepts “cannot post / staff update” as read-only compliance, not only the literal token  

## Validate

1. `python -m unittest NewRidgeFinancial2.test_nr2_hal_local_policy -q`  
2. `python -m unittest scripts.test_hal_eval_scoring -q`  
3. Optional: re-run a 190Q subset after warm (`scripts/run_moonshot_hal_190q_eval.py`) and compare quality / read-only rates  
