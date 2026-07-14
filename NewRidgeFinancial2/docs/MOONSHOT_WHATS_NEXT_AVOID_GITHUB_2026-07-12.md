# Moonshot AI — What's Next (Avoid GitHub) (CONSULT ONLY)

**Date:** 2026-07-12  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10561 + hal-local:32b  
**Script:** `scripts/run_moonshot_whats_next_avoid_github_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> next

**Constraint:** avoid GitHub / PR for now.

---

# Verdict
Implement **REC-008 batch narratives** locally to close the Expert SE loop and provide immediate HAL value for financial data processing without touching GitHub.

## 0. Intent
Close the highest-value open Expert SE item (REC-008) locally to enhance HAL's financial narrative capabilities while respecting the GitHub freeze.

## 1. Already Done (do not redo)
- Expert SE Phases 1–3, compact pages, import gate harden, inbox sync coherence
- Zero-scroll widgets (hal-10561)
- HAL GPU pin → qwen3:32b (hal-local:32b)
- HAL deterministic import-gap replies naming quickbooks.payroll + quickbooks.ap
- Critical completeness at 100%; QB payroll+AP handlers stubbed but optional

## 2. Recommended NEXT — REC-008 Batch Narratives
**Goal:** Generate consolidated natural language summaries for transaction batches (payroll/AP clusters) to replace per-line noise with context-rich HAL responses.

**Why now:** 
- Closes the only high-value Expert SE loose end without GitHub surface area
- Leverages existing deterministic QB naming infrastructure you just shipped
- Immediate HAL utility: transforms raw transaction dumps into executive summaries for local financial workflows

**Effort:** 1–2 hours local HAL module work; zero CI/CD or remote dependencies.

**Files:**
- `hal/modules/narrative_batch.py` (new local module)
- `hal/prompts/batch_narrative_v1.j2` (local prompt template)
- `config/local/hal_batch_config.yaml` (local overlay, never committed)

**Validation gate:** HAL generates coherent multi-transaction summaries for synthetic payroll batches (e.g., "Bi-weekly payroll: $24,500 across 12 employees, 2 exceptions flagged") without falling back to individual line-item spam.

## 3. Runner-up options (max 3)
1. **REC-009 Voice Context Carry** — Enable session continuity for voice commands across HAL restarts using local SQLite state; improves UX but lower immediate value than financial narratives.
2. **QB Payroll+AP Gap Fill** — Implement the optional missing import handlers for the two remaining QB modules; purely mechanical extension of existing deterministic naming work.
3. **Gitignore Hygiene** — Add `site/index.pre-apex.html` to `.gitignore`; process theater, zero functional value, only if you need tidiness dopamine.

## 4. Approval checklist
- [ ] Confirm write access to local HAL modules (no `gh auth` required)
- [ ] Verify batch test fixtures exist in `tests/fixtures/qb_batches/` or create locally
- [ ] Confirm qwen3:32b GPU pin active for narrative generation load (VRAM check)
- [ ] Acknowledge: work stays on `fix/main-validate-ci` or local feature branch, no push to origin until GitHub freeze lifts