# Moonshot AI — What's Next After REC-005 + REC-007 (CONSULT ONLY)

**Date:** 2026-07-12  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10561 + hal-local:32b  
**Script:** `scripts/run_moonshot_whats_next_after_rec005_rec007_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> next

**Constraint:** avoid GitHub / PR for now.

---

# Verdict
Ship the local QB payroll/AP export-to-inbox generator to close the QuickBooks reconciliation loop and complete the optional live gap.

## 0. Intent
Complete the end-to-end QuickBooks integration by generating structured export files that feed HAL's existing deterministic import-gap processor, replacing the current stubbed optional path with live file I/O.

## 1. Already Done (do not redo)
- Expert SE Phases 1–3, compact pages, import gate harden, inbox sync coherence  
- Zero-scroll widgets (hal-10561); HAL GPU pin → qwen3:32b  
- HAL deterministic import-gap replies for `quickbooks.payroll` and `quickbooks.ap` intents  
- REC-008 batch claim narratives; REC-009 voice context carry  
- REC-005 ERA parser DEPTH (Loop 2110 serviceLines, CAS/CARC, RARC, denialFlag, summarize_835_for_hal, POST /api/apex/claims/era-summary)  
- REC-007 HAL model keep-alive + prompt warm (apex_hal_cache_warm_pack, Ollama keep_alive=-1)  
- Phase 3 widget stub warming  

## 2. Recommended NEXT (single package) — must NOT require GitHub
**Package:** QB Payroll/AP Export-to-Inbox Generator (closes the live optional gap)  

**Goal:**  
Generate atomic QB payroll and AP export files (JSON line-delimited) and drop them into `inbox/` for HAL’s existing deterministic processor to consume, completing the reconciliation loop without manual data entry.

**Why now:**  
The HAL reply logic for `quickbooks.payroll` and `quickbooks.ap` is live but has no upstream file source; this is the final mile to make the integration testable end-to-end and close the explicitly identified optional gap.

**Effort:**  
1 session (2–3 hours). Reuses existing inbox sync coherence and checksum validation.

**REAL files:**  
- `NewRidgeFinancial2/import_sync/qb_export_generator.py` — generates `payroll_YYYYMMDD_HHMMSS.jsonl` and `ap_YYYYMMDD_HHMMSS.jsonl` with SHA-256 checksums in headers  
- `NewRidgeFinancial2/inbox/` — existing drop target (atomic move via `os.rename`)  
- `NewRidgeFinancial2/apex_hal.py` — hook `process_inbox_file()` to route `qb_*` filenames to existing `quickbooks.payroll/ap` reply logic  
- `NewRidgeFinancial2/apex_config.yaml` — add `qb_export: {payroll_code: "PAY", ap_code: "AP", min_batch_size: 1}`  

**Validation gate:**  
1. Run generator with 3 dummy records → verify JSONL appears in `inbox/` with `.tmp` prefix then atomic rename to final  
2. Trigger HAL inbox scan → verify deterministic replies contain correct entity IDs and no scroll/widget errors  
3. Verify generator handles empty batches (zero records) by writing empty JSONL with `{"batch_empty": true}` to prevent HAL stall  

## 3. Runner-up options (max 3)
1. **REC-005/007 Live Burn-in Validation** — Process 5–10 real 835 ERA files through the Loop 2110/CARC parser to verify denialFlag hit-rates match expected denials; zero code, pure operational validation if current code is untested on production 835s.  
2. **ERA Observability Log** — Add structured local logging to `NewRidgeFinancial2/era835_parser.py` capturing denialFlag frequency, top 10 CAS/CARC codes per batch, and RARC distributions to debug REC-005 edge cases without external telemetry.  
3. **HAL Context Compaction** — Implement sliding-window token truncation in `NewRidgeFinancial2/apex_hal.py` for sessions exceeding 8k tokens (REC-009 voice context hardening) to prevent GPU OOM on long interactive sessions.

## 4. Approval checklist
- [ ] Confirm QB export JSONL schema matches existing `quickbooks.payroll` and `quickbooks.ap` intent signatures in `apex_hal.py`  
- [ ] Verify `inbox/` directory permissions allow atomic moves from `import_sync/` (no GitHub operations required)  
- [ ] Define payroll/AP test records (employee_id, check_date, amount, gl_code) for validation  
- [ ] Ensure generator logs to local rotating file only (no external sinks)  
- [ ] Confirm empty-batch handling prevents HAL from hanging on zero-record files