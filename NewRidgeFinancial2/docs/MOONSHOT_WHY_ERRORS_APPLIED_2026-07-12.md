# Moonshot WHY-ERRORS — SQLite Lock Phase 1+2 APPLIED

**Date:** 2026-07-12  
**Consult:** `MOONSHOT_WHY_ERRORS_CONSULT_2026-07-12.md`  
**Operator:** proceed exactly as moonshot directs and do not deviate  

## Goal

Stop immediate `sqlite3.OperationalError: database is locked` during SoftDent practice export reads by matching `nr2_local_db.py` connect timeout practice, and distinguish lock rejections from other direct-pipeline failures via `direct_import_lock_rejection_count`.

## Applied (real paths — Moonshot Phase 1 + Phase 2)

| Piece | Where |
|-------|--------|
| `sqlite3.connect(..., timeout=10.0)` | `softdent_practice_exports.py` lines ~378, ~710, ~864 |
| `PRAGMA busy_timeout = 5000` immediately after connect | same three sites |
| Distinguish `sqlite3.OperationalError` | `practice_source_access.assemble_direct_import_sections` |
| Metric `direct_import_lock_rejection_count` | module counter + WARNING log (not full traceback) |
| Other exceptions still use `logger.exception` legacy message | unchanged |
| Tests | `test_why_errors_sqlite_lock.py` |

## Not in this package

- HAL 190Q Phase 3 streaming / TTFT  
- Collections/Daysheet export gap  
- SoftDent write-back  
- Invented dollars / empty ≠ $0  

## Honesty

- Lock path still falls back to legacy fetch (app stays up)  
- Metric is concurrency pressure only — no PHI  
- Empty collections remain empty (not $0)  

## Validate

1. `python -m unittest test_why_errors_sqlite_lock -q` (from `NewRidgeFinancial2/`)  
2. Under brief writer lock, `read_practice_export_datasets` waits and returns direct `newPatients` (`sourceKind=analytics-db`)  
3. Forced `OperationalError("database is locked")` increments `direct_import_lock_rejection_count` and logs the metric name  
