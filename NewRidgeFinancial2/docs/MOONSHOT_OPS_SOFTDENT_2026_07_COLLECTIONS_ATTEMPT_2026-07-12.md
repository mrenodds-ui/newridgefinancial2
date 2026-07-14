# Moonshot OPS — SoftDent 2026-07 Collections Export (ATTEMPT)

**Date:** 2026-07-12  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_PERIOD_SYNC_10565_2026-07-12.md`  
**Operator:** proceed exactly as Moonshot wants (no code package)  
**Build:** hal-10565  
**Status:** **BLOCKED on SoftDent GUI export** — no invented dollars; no code deviation.

## Moonshot package (verbatim intent)

**OPS SoftDent 2026-07 Collections Export (Ins-Patient Split)**  
- SoftDent → Reports → Accounting → Collections (or Register for a Period `07/01/2026`→today)  
- CSV with Insurance + Patient columns → `C:\SoftDentReportExports`  
- HAL Refresh SoftDent period  
- Validate `coversOpenMonth=true` and non-zero ins/patient (or honest empty)

## What was executed (no deviation)

| Step | Result |
|------|--------|
| Scan inbox for 2026-07 Collections/Register | **FAIL** — no July period report. Existing Register is **2026-06**; DaySheet is **2026-05**; Trans is **05/01–05/28**. |
| SoftDent GUI export | **BLOCKED** — SoftDent (`SDWIN.EXE`) is installed at `C:\SoftDent` but **not running**; no vendor CLI (`softdent_export_command` empty / automation `enabled:false`). Agent cannot complete Reports → Accounting without staff SoftDent session. |
| `refresh_softdent_period_imports` | **Ran** — period automation + dashboard sync OK. Period status still lists **2026-07 missing**. |
| Invent CSV / invent $ | **Not done** (honesty) |

## Live validation after refresh

- **2026-07 row:** production present, `collectionsPending: true`, insurance/patient `0.0`  
- **coversOpenMonth:** `false`  
- **classifiedPeriods:** `["2026-05","2026-06"]` (not July)  
- **period automation missingPeriods:** no Transactions/Register for `2026-07-01`–`2026-07-12`  
- **June Register note:** `Ins Plan Collections = $0.00` / Regular Collections only — even June lacks a real Ins/Patient mix

## Exact SoftDent steps for staff (Moonshot acceptance)

1. Open SoftDent (`C:\SoftDent\SDWIN.EXE`) with admin rights.  
2. Reports → Accounting → **Collections** (preferred) **or** **Register for a Period**.  
3. Date range: **07/01/2026** through **today**.  
4. Export **CSV** including Insurance and Patient (or Ins Plan) columns — not PDF.  
5. Save to **`C:\SoftDentReportExports\`** (filename should include 2026-07 or 07_01_2026).  
6. Reply **proceed** (or ask HAL to Refresh SoftDent period) so validation can re-run.

## What was NOT done (per Moonshot)

- No new parser / SoftDentImportParser fiction  
- No SoftDent write-back  
- No commit of uncommitted `softdent_practice_exports.py` helpers (Moonshot: only after export validates)  
- No invented July dollars
