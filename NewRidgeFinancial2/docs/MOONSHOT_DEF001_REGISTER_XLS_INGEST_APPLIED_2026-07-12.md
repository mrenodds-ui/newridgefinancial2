# Moonshot DEF-001 Register XLS Ingest — APPLIED (hal-10566)

**Date:** 2026-07-12  
**Build:** hal-10566  
**Prior consult:** `MOONSHOT_WHATS_NEXT_AFTER_PERIOD_SYNC_10565_2026-07-12.md`  
**OPS attempt:** `MOONSHOT_OPS_SOFTDENT_2026_07_COLLECTIONS_ATTEMPT_2026-07-12.md` (SoftDent GUI blocked)  
**Status:** Applied (operator `proceed` → escalate to Parse Register XLS runner-up)

## Why code (not OPS)

Moonshot’s primary NEXT was OPS July CSV export. SoftDent was not running (no GUI session / automation disabled). Escalation checklist item: parse existing Register XLS.

## What shipped

| Item | Detail |
| --- | --- |
| XLS/XLSX register parse | `parse_softdent_register_xls` + `_load_excel_register_rows` (xlrd / openpyxl) |
| Summarize routing | `summarize_daysheet_export` no longer `read_text`s binary Excel as CSV |
| Content period wins | Filename `…For07012026.xls` may be run-date; body `06/01/26 thru 06/30/26` → **2026-06** |
| Honesty | Ins Plan `$0` → `collectionsFormatRequired`; never invent patient = collections |
| Inbox classify | Excel periodHints + mismatch notes |
| Build | `hal-10566` |

## Live fact (important)

`C:\SoftDentReportExports\RegisterForPeriodReportFor07012026.xls` body is **June 2026**, Ins Plan Collections **$0.00**. Parsing it cannot populate July Ins/Patient — staff must still export a true **2026-07** Register/Collections with positive Ins Plan side.

## Validation

```text
python -m unittest test_softdent_register_xls_hal10566 test_collections_daysheet_hal10564 test_period_sync_format_hal10565 -v
```

## Not done (OPS)

- SoftDent open → Register/Collections for **07/01/2026–today**, CSV or XLS with Ins Plan > 0 → SoftDentReportExports → Refresh SoftDent period.
