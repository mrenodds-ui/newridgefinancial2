# Moonshot OPS — SoftDent July 2026 Register/Collections (Ins Plan) — APPLIED ATTEMPT

**Date:** 2026-07-12  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_ACCOUNT_TX_DB_2026-07-12.md`  
**Operator:** proceed (OPS SoftDent July Register/Collections with Ins Plan > 0)  
**Build:** hal-10569  
**Status:** **PARTIAL** — July Register Excel re-exported and refreshed; **Ins Plan Collections remains $0.00 in SoftDent body** (honesty: empty/zero Ins Plan ≠ invent patient split)

## What was executed

| Step | Result |
|------|--------|
| SoftDent running | **PASS** — CS SoftDent Software v19.1.4 (`SDWIN`) |
| Register for a Period Excel | **PASS** — `07/01/26`–`07/12/26`, Doctors `999` |
| Inbox file | `C:\SoftDentReportExports\register_for_period_2026-07-01_2026-07-12.xls` (also `REG2607`) |
| SoftDent Ins Plan line | **Ins Plan Collections = $0.00** |
| SoftDent Regular line | **Regular Collections = $30626.42** |
| Collections Summary Excel | **FAIL** — Output Options opened; Excel workbook never materialized for SaveCopyAs |
| Invent Ins/Patient dollars | **Not done** |
| SoftDent write-back | **Not done** |
| Period refresh | `refresh_softdent_period_imports()` → `ok: true` |

## SoftDent Register body (live truth)

| Field | Value |
|-------|--------|
| Period | 2026-07 |
| Productions | 44735.00 |
| Collections | 30626.42 |
| Ins Plan Collections | **0.00** |
| Regular Collections | 30626.42 |
| `collectionsFormatRequired` | **true** (parser honesty) |

## Gap after refresh

| Field | Value |
|-------|--------|
| period | 2026-07 |
| production (dashboard) | 45684.25 |
| collectionsReported | true |
| collectionsFormatRequired | true |
| collectionsGapCode | `COLLECTIONS_EXPORT_REQUIRED` / ERA path note |
| insurance / patient | still not populated from Register (Ins Plan $0) |

## Code assist (minimal, for SoftDent Excel-temp behavior)

`softdent_gui_export._complete_output_setup_and_save` now falls back to Excel COM **SaveCopyAs** when SoftDent skips **Select File Name** and opens `%TEMP%\SDWIN*` (same pattern as Trans-for-Period). This unblocked the July Register export; it does not invent dollars.

## Why Ins Plan > 0 was not achieved

Moonshot’s gate required a SoftDent export with **Ins Plan Collections > 0**. SoftDent’s own July Register reports **Ins Plan = $0.00**. Re-exporting cannot create a split SoftDent does not print. Collections Summary Excel path did not yield a file in this session.

## Staff follow-up (if Ins/Patient split exists elsewhere in SoftDent)

1. SoftDent → Reports → Practice Management → **Collection Reports → Summary** (or alternate Collections report that shows Ins vs Patient).  
2. Confirm on-screen **Ins Plan > $0** before export.  
3. Output Options → **Excel** (never Printer) → save to `C:\SoftDentReportExports`.  
4. Refresh SoftDent period again.

## What was NOT done

- Inventing July insurance/patient dollars  
- SoftDent ODBC/GUI write-back  
- Claiming DEF-001 Ins/Patient gap closed  
