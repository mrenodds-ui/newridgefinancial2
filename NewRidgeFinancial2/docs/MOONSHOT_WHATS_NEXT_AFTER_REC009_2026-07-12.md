# Moonshot AI — What's Next After REC-009 (CONSULT ONLY)

**Date:** 2026-07-12  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10561 + hal-local:32b  
**Script:** `scripts/run_moonshot_whats_next_after_rec009_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> next

**Constraint:** avoid GitHub / PR for now.

---

# Verdict (one sentence)
Ship REC-005 ERA parser depth locally to close the Expert SE SHOULD backlog and unlock automated remittance reconciliation without touching GitHub.

## 0. Intent
Close the remaining Expert SE Phase gap (REC-005) to deepen ERA 835 parsing logic, enabling HAL to extract denial codes (CARC/RARC), adjustment reason codes, and service-line level payment amounts from electronic remittances currently passing through as opaque blobs.

## 1. Already Done (do not redo)
- REC-008 batch claim narratives (consent + batch generate + print packet)
- REC-009 voice context carry (focused claim → session POST + Narratives voice [ClaimRef] resolve; 5‑min TTL; tests passed)
- Zero-scroll widgets (hal-10561)
- HAL GPU pin → qwen3:32b (hal-local:32b)
- HAL deterministic import-gap replies naming quickbooks.payroll + quickbooks.ap
- Import gate harden, inbox sync coherence, compact pages

## 2. Recommended NEXT (single package) — must NOT require GitHub
**Goal:** Extend ERA 835 parser to unpack Loop 2100 (claim level) and Loop 2110 (service line level) to capture adjustment reason codes, denial flags, and paid amounts per CPT line.  
**Why now:** This is the last open Expert SE SHOULD item; it enables HAL to auto-generate denial appeal drafts and payment reconciliation narratives instead of manual reading. Pure local Python work, zero remote dependencies.  
**Effort:** 1 focused day; augment existing parser grammar, add 3–4 new regex/FSM segments for 835 loops, update internal `RemittanceClaim` dataclass.  
**Files:** `NewRidgeFinancial2/apex_era.py`, `hal_learning/era_schema.json`, `tests/fixtures/era/sample_835_*.txt`.  
**Validation gate:** Local pytest passes on 3+ production 835 samples; HAL CLI command `hal narrate remittance <file.835>` outputs a structured summary containing specific denial reasons and line-item adjustments without hallucinating missing data.

## 3. Runner-up options (max 3)
1. **REC-007 Cache Warming:** Pre-compute dashboard widget data and claim list aggregates on HAL startup to eliminate first-load latency; touches `NewRidgeFinancial2/apex_cache.py` or local SQLite warming routines.  
2. **QB Payroll/AP File Exports:** Generate IIF/CSV exports for QuickBooks Desktop from local invoice/payroll data and drop them into `inbox/exports/`; closes the optional gap noted in live readiness; purely local file I/O.  
3. **Git Hygiene:** Add `site/index.pre-apex.html` to `.gitignore` to prevent pre-compiled artifacts from dirtying the local working tree; 5-minute cleanup, zero functional risk.

## 4. Approval checklist
- [ ] Confirm `NewRidgeFinancial2/apex_era.py` exists locally and REC-005 logic is not already partially shipped  
- [ ] Verify 3+ sample 835 files available in `tests/fixtures/era/` or local `inbox/`  
- [ ] Confirm no GitHub remote operations required (no push, no PR, no `gh auth`)  
- [ ] Agree on validation gate: HAL can parse a local 835 file and output line-level adjustments/denials in the narrative session