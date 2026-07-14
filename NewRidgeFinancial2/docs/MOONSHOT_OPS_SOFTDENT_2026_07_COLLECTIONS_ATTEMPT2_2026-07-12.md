# Moonshot OPS — SoftDent July 2026 Register/Collections Export (ATTEMPT #2)

**Date:** 2026-07-12  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_REGISTER_XLS_10566_2026-07-12.md`  
**Operator:** proceed (OPS-only; no code package)  
**Build:** hal-10566  
**Status:** **BLOCKED on staff SoftDent GUI export** — SoftDent is running; no July Ins Plan > 0 file yet.

## Moonshot package (verbatim intent)

**OPS SoftDent July 2026 Register/Collections Export (Ins-Patient Split)**  
- SoftDent → Reports → Accounting → Register for a Period **or** Collections  
- Date range **07/01/2026 – today**  
- CSV or XLS with **Ins Plan Collections > 0** → `C:\SoftDentReportExports`  
- Refresh SoftDent period → validate coversOpenMonth + non-zero ins/patient

## What was executed (no deviation / no invented $)

| Step | Result |
|------|--------|
| SoftDent process | **PASS** — `SDWIN.EXE` running (PID present at `C:\SoftDent\SDWIN.EXE`) |
| Vendor CLI / `softdent_export_command` | **FAIL** — config `enabled=false`, command empty (no auto-export) |
| Period export automation | **Ran** — promoted June register only; **missingPeriods: 2026-07** (“No Transactions/Register for 2026-07-01–2026-07-12”) |
| Excel convert of inbox XLS | **Ran** — `RegisterForPeriodReportFor07012026.xls` → still **June** body, Ins Plan **$0** |
| Scan export roots for July Ins>0 | **FAIL** — no new July Register/Collections with Ins Plan > 0 |
| Daysheet JSONL July payment codes | **FAIL** — 0 July txs / ins=0 / pat=0 |
| `refresh_softdent_period_imports` | **PASS** (refresh ok) — gap unchanged for open month |
| Invent CSV / invent $ / SoftDent write-back / GUI SendKeys | **Not done** (honesty) |

## Live validation after refresh (hal-10566)

| Field | Value |
|-------|--------|
| period | `2026-07` |
| production | `45684.25` |
| collectionsPending | `true` |
| collectionsFormatRequired | `true` |
| collectionsGapCode | `COLLECTIONS_EXPORT_REQUIRED` |
| coversOpenMonth | `false` |
| classifiedPeriods | `["2026-05","2026-06"]` |
| insurance / patient | still empty (not inventable) |

## Exact SoftDent steps (SoftDent is already open)

1. In the running SoftDent window: **Reports → Accounting → Register for a Period** (preferred) **or Collections**.  
2. Date range: **07/01/2026** through **today** (2026-07-12).  
3. Export **CSV** or **XLS/XLSX** (hal-10566 ingests both).  
4. Confirm **Ins Plan Collections > $0.00** (and Regular/Patient side) before saving — June’s Ins Plan $0 will not clear the gap.  
5. Save to **`C:\SoftDentReportExports\`**.  
6. Reply **proceed** (or ask HAL to Refresh SoftDent period) for re-validation.

## What was NOT done

- No fictional SoftDent GUI bot / write-back  
- No invented July Ins/Patient dollars  
- No code package (Moonshot: OPS-only)  
- No enabling `softdent_export_command` without IT/vendor CLI
