# Moonshot OPS — SoftDent July 2026 Register/Collections Export (ATTEMPT #3)

**Date:** 2026-07-12  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_REGISTER_XLS_10566_2026-07-12.md`  
**Operator:** proceed (OPS re-validate after staff export)  
**Build:** hal-10566  
**Status:** **PARTIAL PASS** — July Register ingested; Ins Plan still **$0.00** (honest SoftDent figure).

## What changed since attempt #2

| File | Period | Notes |
|------|--------|--------|
| `register_for_period_2026-07-01_2026-07-12.csv` | **2026-07** | New (~8:33 AM) |
| `register_for_period_2026-07-01_2026-07-12.xls` / `REG202607.XLS` | **2026-07** | New |
| SoftDent body | 07/01/26 thru 07/12/26 | Productions $44,735 · Collections $29,965.32 · **Ins Plan Collections $0.00** · Regular $29,965.32 |

## Actions run

1. Confirmed SoftDent `SDWIN` still running  
2. Parsed July Register (CSV + XLS) via hal-10566 summarize  
3. `refresh_softdent_period_imports` → ok  
4. Re-assessed collections gap  

## Validation after refresh

| Check | Result |
|-------|--------|
| `classifiedPeriods` includes 2026-07 | **PASS** |
| `coversOpenMonth` | **PASS** (`true`) |
| July row `collectionsReported` | **PASS** (`29965.32`) |
| July `collectionsPending` cleared | **PASS** |
| Ins Plan / insurance > 0 | **FAIL** — SoftDent reports **$0.00** |
| patient populated | **FAIL** — honesty gate (no invent all-patient dump) |
| `collectionsFormatRequired` | still **true** |
| `collectionsGapCode` | `COLLECTIONS_EXPORT_REQUIRED` (ERA may show `ERA_835_AVAILABLE` on gapCode) |

### July dashboard row (post-ingest)

- production ≈ `45684.25` (merged)  
- collections = `29965.32` reported  
- insurance = `0.0`, patient = `0.0`  
- `collectionsFormatRequired: true`

## Honesty note

This is **not** a parser failure. SoftDent’s own Register for 07/01–07/12 lists **Ins Plan Collections = $0.00**. Hal-10566 correctly refuses to invent insurance/patient mix from Regular-only totals.

## Remaining OPS (if revenue-composition split is required)

1. SoftDent → Reports → Accounting → **Collections** (not only Register) for **07/01/2026–today**, with a real Ins/Patient (or Ins Plan) side **> $0**, **or**  
2. Confirm with SoftDent that July MTD insurance postings truly show as Ins Plan $0 on Register (then format-required is the honest state until postings change).  
3. Save to `C:\SoftDentReportExports\` → reply **proceed** to re-validate.

## What was NOT done

- No invented Ins/Patient dollars  
- No SoftDent write-back  
- No code package
