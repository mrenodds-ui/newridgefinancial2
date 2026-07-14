# Moonshot AI — Why This Program Is Throwing Errors (CONSULT ONLY)

**Date:** 2026-07-12  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10561 (process start logged hal-10550)  
**Primary live error:** `sqlite3.OperationalError: database is locked`  
**Script:** `scripts/run_moonshot_why_errors_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> ask moonshot why this program is throwing errors an report

---

# Verdict
**SQLite connections in `softdent_practice_exports.py` open with zero timeout and no busy-wait PRAGMA, causing immediate `OperationalError: database is locked` when SoftDent export processes or concurrent readers hold the file handle, forcing the app to degrade to legacy fetch and serve potentially stale data.**

## 0. Operator Intent (verbatim)
> ask moonshot why this program is throwing errors an report

## 1. What's Throwing (ranked; blunt)

| Rank | Error | Severity | Evidence | Root Cause vs Symptom |
|------|-------|----------|----------|----------------------|
| **1** | `sqlite3.OperationalError: database is locked` at `_table_exists` → `sqlite_master` query | **Recovered (fallback)** — app stays up, but pipeline degrades | Traceback lines 27→70→379 in `softdent_practice_exports.py`; logs show "Direct import pipeline unavailable; falling back to legacy fetch" | **Root:** `sqlite3.connect(db_path)` at lines 377, 709, 862 uses default `timeout=0.0` and sets no `PRAGMA busy_timeout`; **Symptom:** the traceback noise staff see |
| **2** | Silent data-freshness regression | **Operational** — no crash, but dishonest data | Health monitor shows `ok=True` (HAL path up) yet widgets load from legacy fallback instead of direct SoftDent reads | **Root:** Fallback logic in `practice_source_access.py:248-250` catches all exceptions and silently switches to legacy fetch without surfacing data-age warnings to the UI |

## 2. Why Now (concurrency / connect flags / callers)

- **Concurrency collision:** SoftDent practice exports (or another NR2 process) are writing to the SQLite DB while `assemble_direct_import_sections` (called from cache warm or direct import assembly) attempts to read. SQLite locks the entire file during writes; without busy-wait, readers get immediate `DATABASE LOCKED`.
- **Missing connect flags:** `softdent_practice_exports.py` uses naked `sqlite3.connect(db_path)` (lines 377, 709, 862). Contrast with `nr2_local_db.py:32` which uses `timeout=10`. No `PRAGMA busy_timeout` is executed post-connect.
- **Caller chain:** `browser_app.py` cache warm → `practice_source_access.py:195` `assemble_direct_import_sections` → `import_direct_pipeline.py:413` `build_softdent_pipeline_datasets` → `softdent_practice_exports.py:377` `read_practice_export_datasets` → immediate lock on first table-existence check.

## 3. Impact on staff / data honesty

- **Log noise:** Staff see repeated tracebacks in console/logs during normal operations, creating false alarms about system stability.
- **Cold-load latency:** Direct import pipeline is disabled for the affected cycle; legacy fetch is slower, causing multi-second "Loading…" states on first dashboard open.
- **Data staleness:** Fallback uses older cached exports instead of live SoftDent data. **Empty collections cells remain empty** (do not confuse with $0 revenue); this is the Collections/Daysheet export gap manifesting longer because the direct pipeline that might partially compensate is offline.
- **No corruption risk:** All operations are read-only (no SoftDent write-back), so patient ledgers remain safe.

## 4. Fix Package (ordered; REAL files; validation gate) — CONSULT ONLY

**Phase 1 — Additive Timeout Hardening (Day 1)**

1. **`NewRidgeFinancial2/softdent_practice_exports.py`**
   - Lines 377, 709, 862: Change `sqlite3.connect(db_path)` to `sqlite3.connect(db_path, timeout=10.0)`.
   - Optionally add `conn.execute("PRAGMA busy_timeout = 5000")` immediately after connect for explicit 5-second busy-wait.

**Phase 2 — Observability (Day 1, parallel)**

2. **`NewRidgeFinancial2/practice_source_access.py`**
   - Line 249: Distinguish `sqlite3.OperationalError` from other exceptions; log specific metric `direct_import_lock_rejection_count` so operators can track concurrency pressure without reading full tracebacks.

**Validation Gate**
- Trigger a SoftDent export (or hold a write lock on the DB file) while running `assemble_direct_import_sections()`.
- **Pass criteria:** No `OperationalError` in logs; log shows "Direct import pipeline assembled" rather than "falling back to legacy fetch"; dashboard widgets populate from direct pipeline (verify by checking `source_file` metadata in dataset).

## 5. What NOT to confuse with these errors (already fixed / other tracks)

- **HAL 190Q quality/latency issues** — Separate from this SQLite stack; those involve `nr2_hal_gateway.py` and Ollama latency, not SoftDent file locking.
- **Collections/Daysheet export gap** — That is a *data gap* (missing CSV exports causing empty revenue-composition widgets). This report covers the *locking* error that prevents the direct pipeline from reading whatever data is present.
- **Fatal crash** — The app does not crash; it recovers via legacy fallback. Do not treat this as a stability failure requiring restart.
- **Logic bugs in aggregation** — The `_aggregate_new_patients` logic is correct; it fails at the connection level before reaching business logic.
- **Empty = $0** — Do not interpret missing collections data as zero dollars; the lock prevents reading, not the existence of money.

## 6. Executive Summary (5 bullets)

- **Root cause:** Zero-timeout SQLite connections in `softdent_practice_exports.py` collide with concurrent SoftDent exports, raising `database is locked` immediately instead of waiting.
- **Symptom vs severity:** Recovered error (fallback works) but causes log spam, cold-load delays, and stale data reads.
- **Data impact:** Direct pipeline disabled for affected cycles; staff may see outdated patient counts and pending collections statuses until the next successful warm.
- **Fix:** Additive 10-second timeout to three connect calls; no changes to query logic or SoftDent write-back required.
- **Validation:** Reproduce under concurrent export load; verify fallback no longer triggers and logs remain clean.

## 7. Approval checklist

- [ ] Confirm SoftDent export schedule (is it automated overnight or manual midday?) to validate concurrency hypothesis.
- [ ] Verify `timeout=10` is acceptable (matches `nr2_local_db.py` standard) or request different value.
- [ ] Confirm no other processes require zero-timeout connects to the SoftDent SQLite file (unlikely, but check).
- [ ] Approve Phase 1 only, or Phase 1+2 together?
- [ ] Confirm "DO NOT APPLY" — await explicit "proceed" before generating patch.