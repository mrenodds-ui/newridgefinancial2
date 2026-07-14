# Moonshot OPS — SoftDent 2026-07 Register Export Automated (APPLIED)

**Date:** 2026-07-12  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_REGISTER_XLS_10566_2026-07-12.md`  
**Operator:** `automate it` (pywinauto GUI drive; SoftDent read-only)  
**Build:** hal-10566  
**Status:** **APPLIED** — July Register XLS exported, ingested, `coversOpenMonth: true`

## What shipped

| Item | Result |
|------|--------|
| Script | `scripts/automate_softdent_register_period_export.py` |
| SoftDent path | Reports → Accounting → Registers → Period → Excel |
| Date range | `07/01/26`–`07/12/26`, provider `999` |
| Save path | 8.3 short path `C:\SOFTDE~1\REG202607` (long paths rejected by SoftDent) |
| Canonical inbox | `C:\SoftDentReportExports\register_for_period_2026-07-01_2026-07-12.xls` |
| Mirror | `C:\SoftDent\softdentexportreports\` (same name) |
| Refresh | `refresh_softdent_period_imports()` → `ok: true` |

## Validation after refresh

| Field | Value |
|-------|--------|
| `coversOpenMonth` | `true` |
| `classifiedPeriods` | `2026-05`, `2026-06`, `2026-07` |
| `missingPeriods` | `[]` |
| July `production` | `45684.25` |
| July `collections` | `29965.32` |
| July `collectionsReported` | `true` |
| July `insurance` / `patient` | `0.0` / `0.0` |
| July `collectionsFormatRequired` | `true` (honest — Ins Plan Collections still $0 in SoftDent body) |
| `collectionsGapCode` | still `COLLECTIONS_EXPORT_REQUIRED` / format path until real Ins/Patient split |

## Honesty gate

Register export fixed the **open-month coverage** gap. It did **not** invent an Ins/Patient split: SoftDent’s July Register still shows Ins Plan Collections = $0, so DEF-001 keeps `collectionsFormatRequired` until a report with a real split lands (or SoftDent shows non-zero Ins Plan).

## How to re-run

1. SoftDent (`SDWIN.EXE`) must be running and logged in.  
2. From repo root:

```powershell
.\.venv\Scripts\python.exe scripts\automate_softdent_register_period_export.py --start 2026-07-01 --end 2026-07-12
```

3. Then refresh SoftDent period imports (HAL or `refresh_softdent_period_imports()`).

## What was NOT done

- No SoftDent write-back  
- No invented Ins/Patient dollars  
- No commit/push (ask explicitly if wanted)
