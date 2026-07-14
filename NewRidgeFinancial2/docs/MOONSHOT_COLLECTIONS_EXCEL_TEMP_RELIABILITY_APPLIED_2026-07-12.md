# Collections Excel-Temp Reliability — APPLIED (hal-10576)

**Date:** 2026-07-12  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_ERA_10575_DISCOVERY_2026-07-13.md`  
**Operator:** proceed  
**Build:** **hal-10576**

## What shipped

| Item | Detail |
|------|--------|
| `softdent_excel_temp.py` | Retry/backoff (100ms / 500ms / 1s) on Excel share-locks + truncated workbooks |
| `atomic_write_excel_export` | NamedTemporaryFile → validate non-empty → `os.replace`; emits `collections_summary_export_success` |
| GUI SaveCopyAs | `softdent_gui_export._save_excel_sdwin_copy` wraps atomic write + retry |
| Register Excel load | `_load_excel_register_rows` retries through lock window |
| Health API | `GET /api/apex/hal/collections-export/health` (system telemetry) |
| HAL policy | excel-temp / `temp_file_locked` → `policy:collections-excel-temp` |
| Honesty | empty ≠ $0; no SoftDent write-back; no Register re-export for Ins Plan > 0 |

## Error codes (health)

| Code | Meaning |
|------|---------|
| `temp_file_locked` | SoftDent/Excel still holds share lock |
| `truncated_workbook` | Half-written / bad zip workbook |
| `no_exports` | No COL/REG/SDWIN candidates under export root or %TEMP% |
| `unreadable` | Other open failure |

## Validation

```text
cd NewRidgeFinancial2
python -m unittest test_collections_excel_temp_reliability_hal10576 -v
```

| Gate | Result |
|------|--------|
| Unit tests 10576 | **PASS** (10/10) |
| Live `collections_export_health()` | **PASS** — `collectionsExportReady=true`, REG2607 + SDWIN temps readable |
| BUILD_ID stamp | **hal-10576** |

## Staff use

1. Restart backend + hard-refresh for **hal-10576**
2. SoftDent Collections/Register → Excel (never Printer) as before
3. If exports fail mid-lock: wait briefly — HAL retries automatically; check health endpoint if stuck
4. Insurance gap still needs real payer 835s — this build does not invent Ins Plan dollars

## Not done

- ERA procurement / portal playbook  
- Auto-ingest when 835s appear  
- Register re-export hoping Ins Plan > 0  
