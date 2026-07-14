# Moonshot OPS — SoftDent 2026-07 Collections Export (PROCEED #2)

**Date:** 2026-07-12  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_REGISTER_XLS_10566_2026-07-12.md`  
**Operator:** `proceed` (OPS-only package; no code deviation)  
**Build:** hal-10566  
**Status:** SoftDent GUI **is running** — export still requires staff menu clicks (no vendor CLI).

## Moonshot package

**SoftDent Register/Collections Export — July 2026 Open Month (OPS-only)**  
Target: `07/01/2026`–today, Ins Plan Collections **> 0**, save to `C:\SoftDentReportExports`.

## What was executed this proceed

| Step | Result |
|------|--------|
| Confirm SoftDent process | **PASS** — `SDWIN.EXE` PID running (`CS SoftDent Software v19.1.4`) |
| Vendor CLI / `softdent_export_command` | **Empty** — automation `enabled:false`; cannot drive SoftDent Reports from code without inventing a GUI bot |
| Focus SoftDent main window | **Done** — brought SoftDent to foreground for staff |
| Inbox scan for July Ins>0 | **FAIL** — still May daysheet + June register (Ins Plan $0) + June-bodied XLS |
| Invent July CSV / invent $ | **Not done** (DEF-001 honesty) |
| Invent SoftDent GUI bot | **Not done** (Moonshot: prohibited) |

## Exact SoftDent steps (do these now — SoftDent is open)

1. In SoftDent: **Reports → Accounting → Register for a Period** (or **Collections**).  
2. Date range: **07/01/2026** through **today** (not June).  
3. Export **CSV** or **XLS** (hal-10566 ingests both).  
4. Confirm **Ins Plan Collections** is **> $0** in the report body (June’s $0 will not clear the gap).  
5. Save to **`C:\SoftDentReportExports\`**.  
6. Reply here (or ask HAL: **Refresh SoftDent period**) so validation can re-run.

## Validation gate (after file lands)

- Content period = `2026-07`  
- `insurance` > 0 and `patient` > 0 on 2026-07 dashboard row  
- `coversOpenMonth: true`, `collectionsExportRequired` clears (or honest format-required if Ins Plan still $0)

## What was NOT done

- No SoftDent write-back  
- No invented July Ins/Patient dollars  
- No fictional `softdent_export_command`  
- No GUI SendKeys/UIAutomation bot
