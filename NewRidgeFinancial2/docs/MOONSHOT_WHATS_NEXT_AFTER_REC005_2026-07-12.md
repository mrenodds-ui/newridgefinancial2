# Moonshot AI — What's Next After REC-005 (CONSULT ONLY)

**Date:** 2026-07-12  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10561 + hal-local:32b  
**Script:** `scripts/run_moonshot_whats_next_after_rec005_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> next

**Constraint:** avoid GitHub / PR for now.

---

# Verdict
Implement **REC-007 HAL cache warming** for the local qwen3:32b instance to eliminate cold-start latency on high-frequency payer and coding queries, closing the final Expert SE SHOULD item without any git operations.

## 0. Intent
Close the remaining Expert SE SHOULD requirement by pre-loading the local HAL model’s KV-cache and Apex hot-context (payer rules, common CPT/ICD clusters) entirely on-local-workstation, ensuring sub-500ms responses after restarts or post-ERA batch imports.

## 1. Already Done (do not redo)
- REC-005 ERA depth parsing (Loop 2110 serviceLines, CAS/CARC, LQ RARC, denialFlag, summarize_835_for_hal) in `era835_parser.py`, `apex_era835_pack`, `apex_program_improve_pack`
- REC-008 batch claim narratives and REC-009 voice context carry
- Zero-scroll widgets (hal-10561) and HAL GPU pin to qwen3:32b
- Deterministic import-gap replies for QuickBooks payroll/AP
- Inbox sync coherence and import gate hardening

## 2. Recommended NEXT — REC-007 Cache Warming (NO GitHub required)
**Goal:** Warm the qwen3:32b local model cache and Apex context stores on HAL startup and after ERA batch imports so that repetitive underwriter queries (e.g., “explain CO-45 for Anthem”) never hit cold-start penalties.

**Why now:**  
- It is the only remaining Expert SE SHOULD item blocking 100% phase completion.  
- The local HAL (qwen3:32b) is large; cold starts cost 3–5 seconds on first inference, degrading live UX during ERA reviews.  
- Zero external dependencies—pure local Python/JSON work.

**Effort:** 2–3 hours.

**REAL files:**
- `apex_hal_bridge.py` – add `warm_cache()` orchestrator called on init and post-import.
- `hal_cache_manifest.json` *(new local file)* – ordered list of warming prompts (top 20 payer IDs, high-volume CARC codes, common CPT/ICD pairs).
- `era835_parser.py` – hook `trigger_selective_warm(batch_payer_ids)` after `summarize_835_for_hal` completes to prime cache for newly seen payers.
- `apex_context_store.py` *(if exists)* or inline in bridge – preload hot payer rule text into the 32k context window.

**Validation gate:**
1. Restart local HAL (qwen3:32b).
2. First query: `apex_hal_bridge.py` CLI test “summarize denial CARC CO-45 for Anthem” → must complete <600ms (cache miss allowed).
3. Second identical query immediately → must complete <200ms (cache hit).
4. After ingesting a new 835 batch containing “UnitedHealthcare”, query “explain RARC N706 for UHC” → must complete <500ms without prior UHC queries (warmed by parser hook).

## 3. Runner-up options (max 3)
1. **QB Payroll/AP Inbox Export (Optional functional gap)**  
   Generate QuickBooks Desktop IIF/CSV exports from the deterministic `quickbooks.payroll` and `quickbooks.ap` inbox threads.  
   *Files:* `apex_qb_export.py`, `inbox_sync.py`  
   *Why runner-up:* Closes the “optional missing” functional hole, but lower urgency than HAL latency.

2. **ERA 835 Observability Hook**  
   Add structured SQLite logging (`apex_observability.db`) to `era835_parser.py` tracking denialFlag hit rates and LQ RARC capture depth per batch.  
   *Why runner-up:* Operational visibility into REC-005 performance without external telemetry, but does not improve live speed.

3. **Local HAL Context Compaction**  
   Trim stale voice contexts (REC-009 residue) and old ERA summaries from the qwen3:32b 32k window when token count exceeds 28k to prevent drift.  
   *Files:* `hal_context_manager.py` or inline in `apex_hal_bridge.py`  
   *Why runner-up:* Prevents long-session degradation, but cache warming solves the more painful cold-start problem first.

## 4. Approval checklist
- [ ] No `git commit`, `push`, or PR operations required; work stays on `fix/main-validate-ci` local branch only.  
- [ ] All edits confined to real paths: `NewRidgeFinancial2/apex_*.py`, `era835_parser.py`, and new local JSON/SQLite files.  
- [ ] Validation script runs entirely offline (no `gh auth`, no GitHub API calls).  
- [ ] HAL restart test confirms cache hit on second identical query before proceeding to any runner-up.