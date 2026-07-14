# Collections Summary Excel-Temp Reliability — APPLIED (hal-10576)

**Date:** 2026-07-13  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_ERA_10575_DISCOVERY_2026-07-13.md`  
**Operator:** proceed  
**Build:** **hal-10576**

## Package (verbatim intent)

Collections Summary Excel-Temp Reliability Fix — atomic temp-write + lock retry so SoftDent Excel exports (Collections/Register SaveCopyAs of `%TEMP%\SDWIN*`) do not leave zero-byte / AV-lock debris. Does **not** invent Ins Plan dollars or re-export Register hoping Ins Plan > 0. ERA-835 still required when Register Ins Plan is $0.

## What shipped

| Area | Change |
|------|--------|
| `softdent_practice_exports.py` | `atomic_write_excel_export()` / `atomic_copy_export()` — NamedTemporaryFile + `os.replace`, rejects zero-byte, `event=collections_summary_export_success`, `temp_cleanup=true` |
| `softdent_excel_temp.py` | Lock/truncation retry (100/500/1000ms), `copy_file_with_retry` (atomic), `collections_export_health()` |
| `softdent_gui_export.py` | `_save_excel_sdwin_copy` uses atomic finalize + retry; canonical/mirror copies use retry |
| `apex_backend.py` | `GET /api/apex/hal/collections-export/health`; BUILD_ID **hal-10576** |
| `nr2_browser_security.py` | Health path on system-status prefixes |
| `nr2_hal_gateway.py` | Local policy `policy:collections-excel-temp` |
| Tests | `test_collections_summary_excel_atomic_temp_hal10576.py` |
| Cache stamps | `site/index.html`, `nr2-build.json` → hal-10576 |

## Acceptance

- [x] Atomic finalize — no zero-byte dest; temps cleaned on failure
- [x] openpyxl load validation in unit test (Ins Plan row stays `0.0` honesty)
- [x] Telemetry event `collections_summary_export_success` with `temp_cleanup=true`
- [x] No SoftDent write-back; `writeBack=false`
- [x] Health API + HAL policy for lock/readiness without inventing dollars

## Not done (runner-ups)

- Concrete payer-portal 835 acquisition playbook (no repo portal creds)
- QB payroll/AP OPS drop
- Expanding ERA discovery roots (already scanned; candidates=0)

## Live verify (2026-07-13)

| Gate | Result |
|------|--------|
| Unit tests `test_collections_summary_excel_atomic_temp_hal10576` (+ 10574/10575) | **22 OK** |
| `GET /api/apex/hal/collections-export/health` | **PASS** — `buildId=hal-10576`, `collectionsExportReady=true`, `writeBack=false`, `honesty=empty_not_zero` |
| HAL policy `excel temp health` | **PASS** — `policy:collections-excel-temp` |

ERA gap remains `ERA_835_REQUIRED` until real payer 835 files arrive (discovery candidateCount=0).