# ERA-835 Inbox Ingest Wiring — APPLIED (hal-10573)

**Date:** 2026-07-12  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_GAP_TILE_10572_2026-07-12.md`  
**Operator:** proceed  
**Build:** **hal-10573**

## What shipped

| Item | Detail |
|------|--------|
| `scan_era_inbox()` | Lists drop-box files; empty → `{empty:true, honesty:empty_not_zero, chipStatus:awaiting}` |
| `ensure_era_inbox_dirs()` | Creates `C:\SoftDentFinancialExports\era` + `C:\SoftDentReportExports\era` |
| `ingest_era_inbox()` | Empty → awaiting (no invent $); files → `ingest_era835_to_unified` per drop |
| `attach_era_to_ingest` | Hook kept for legacy matches shape; U1 path already mirrors aggregates |
| Status API | `GET /api/apex/hal/era-inbox/status` |
| Ingest API | `POST /api/apex/hal/era-inbox/ingest` |
| Gap tile chip | `ERA-835 path · Awaiting first 835 drop` when empty |
| Honesty | Empty inbox does **not** flip `ERA_835_REQUIRED` → `AVAILABLE` |

## Validation

```text
cd NewRidgeFinancial2
python -m unittest test_era835_inbox_empty_not_zero_hal10573 test_gap_tile_era_required_label_hal10572 test_era_835_honesty_ux_hal10571 -v
```

| Gate | Result |
|------|--------|
| Empty scan/ingest → awaiting, no invented $ | **PASS** (unit + live) |
| Single-file mock 835 → rowsInserted ≥ 1, writeBack=false | **PASS** (unit) |
| Live inbox roots exist, fileCount=0, chip awaiting | **PASS** |
| Gap stays `ERA_835_REQUIRED` with empty inbox | **PASS** |
| `GET /api/apex/hal/era-inbox/status` buildId=hal-10573 | **PASS** |
| `POST /api/apex/hal/era-inbox/ingest` without mutation token | **403** expected (browser security; local `ingest_era_inbox()` works) |


## Files

| File | Change |
|------|--------|
| `apex_era835_pack.py` | scan / ensure / status / **ingest_era_inbox** |
| `softdent_practice_exports.py` | stub → scaffold + ingest_era_inbox hook |
| `apex_softdent_era_pack.py` | attach `eraInbox` on Register Ins Plan $0 |
| `apex_softdent_hardening_pack.py` | chip sub-status |
| `apex_backend.py` + build/site assets | **hal-10573** + inbox routes |
| `test_era835_inbox_empty_not_zero_hal10573.py` | empty + single-file ingest |

## Not done

- Staff dropping the first real 835 into the inbox  
- Collections Excel-temp / inventing QB payroll/AP / Register re-export  
