# Moonshot OPS — ERA-835 First Drop — APPLIED ATTEMPT

**Date:** 2026-07-12  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_ERA_INBOX_10573_2026-07-12.md`  
**Operator:** proceed (OPS ERA-835 First Drop — real file ingestion validation)  
**Build:** hal-10573  
**Status:** **BLOCKED ON DATA** — inbox wiring healthy; no real payer 835 files found on this machine

## What was executed

| Step | Result |
|------|--------|
| Primary inbox `C:\SoftDentFinancialExports\era` | **PASS** — exists, writable, empty |
| Fallback inbox `C:\SoftDentReportExports\era` | **PASS** — exists, writable, empty |
| `scan_era_inbox(ensure_dirs=True)` | **PASS** — `fileCount=0`, `empty=true`, `chipStatus=awaiting` |
| `ingest_era_inbox()` on empty inbox | **PASS** — `ok=true`, `honesty=empty_not_zero`, no invented dollars |
| `era_inbox_status()` | **PASS** — chip **Awaiting first 835 drop** |
| Gap honesty | **PASS** — `collectionsGapCode=ERA_835_REQUIRED`, `registerInsPlanZero=true` |
| Machine search for real `.835` / `.edi` / `.x12` / remittance files | **NONE** (excluding test fixtures) |
| Synthetic test fixture | **NOT USED** — `NewRidgeFinancial2/test/fixtures/synthetic.835` is not production truth |
| SoftDent Register re-export for Ins Plan > 0 | **NOT DONE** (forbidden by hal-10571 honesty) |
| SoftDent write-back | **NOT DONE** |

## Live snapshot (2026-07-12)

| Field | Value |
|-------|--------|
| BUILD_ID | hal-10573 |
| inbox roots | `C:\SoftDentFinancialExports\era`, `C:\SoftDentReportExports\era` |
| fileCount | 0 |
| chipStatus | awaiting |
| chipLabel | Awaiting first 835 drop |
| collectionsGapCode | ERA_835_REQUIRED |
| registerInsPlanZero | true |
| insurance (Register) | 0 |
| writeBack / softDentWriteBack | false |

## Why full ingest did not run

Moonshot’s gate requires **real** ERA 835 remittance files from payer portals (Delta Dental, MetLife, etc.) or practice EDI archives. A full-disk search under `C:\SoftDentFinancialExports`, `C:\SoftDentReportExports`, and the repo found **no production 835/EDI remittance files**. Without staff-supplied payer data, `ingest_era_inbox()` correctly stays in awaiting mode and does not invent insurance dollars.

## Staff follow-up (required to unblock)

1. Download **real** ERA 835 remittances from payer benefit portals or copy from existing practice EDI archives (July 2026 or relevant period).
2. Drop files into **`C:\SoftDentFinancialExports\era`** (primary) or `C:\SoftDentReportExports\era` (fallback).  
   Accepted: ANSI 5010 X12 835, CSV equivalents, plain-text 835 remittances.
3. **Do not** re-export SoftDent Register hoping for Ins Plan > 0.
4. **Do not** copy `synthetic.835` or other test fixtures into the inbox.

### Validation after drop (local Python)

```powershell
cd C:\NewRidgeFamilyFinancial
$env:PYTHONIOENCODING='utf-8'
& .\.venv\Scripts\python.exe -c "
import sys
sys.path.insert(0, r'C:\NewRidgeFamilyFinancial\NewRidgeFinancial2')
from apex_era835_pack import scan_era_inbox, ingest_era_inbox, list_era835_payments
from apex_softdent_hardening_pack import assess_collections_gap
from apex_backend import _load_reports_and_bundle

scan = scan_era_inbox(ensure_dirs=True)
print('scan', {k: scan.get(k) for k in ('empty','fileCount','chipStatus','chipLabel')})
ingest = ingest_era_inbox(ensure_dirs=False)
print('ingest', {k: ingest.get(k) for k in ('ok','empty','chipStatus','chipLabel','fileCount','writeBack')})
print('ingested', ingest.get('ingested'))
_r, b, _e = _load_reports_and_bundle()
print('gap', assess_collections_gap(b).get('collectionsGapCode'))
print('ledger_sample', list_era835_payments(limit=3))
"
```

### Expected gates once real files are present

| Gate | Expected |
|------|----------|
| `scan_era_inbox()` | `fileCount≥1`, `empty=false` |
| `ingest_era_inbox()` | `processedFiles≥1` or `ingested[]` with `ok=true`, `rowsInserted≥1` |
| HAL chip | no longer **Awaiting first 835 drop** (e.g. ready / processing) |
| Ledger rows | insurance payments from file content only; `writeBack=false` |
| Gap code | stays `ERA_835_REQUIRED` until cumulative ERA volume clears gap (do not force flip) |

### Optional API check (when Apex backend is running)

- `GET /api/apex/hal/era-inbox/status` — should show `fileCount>0` after drop  
- `POST /api/apex/hal/era-inbox/ingest` — use local Python above if browser POST returns 403 (mutation token)

## Rollback

If dropped files are corrupt or wrong payer: delete from inbox and re-drop. Scaffold ingest is non-destructive; no SoftDent write-back occurred.

## What was NOT done

- Inventing insurance/patient dollars  
- Using synthetic/test 835 as production truth  
- SoftDent Register re-export  
- Git commit/push (doc only until operator requests)
