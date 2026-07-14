# OPS Proceed — Gold CSV support / alternate procurement (after Gold CSV OPS consult)

**Date:** 2026-07-13  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_GOLD_CSV_OPS_2026-07-13.md`  
**Operator:** `proceed`  
**Build:** `hal-10608` (+ `bad6d91` honesty)

## Verdict

**OPS pack prepared; Gold still missing.** SoftDent v19.1.4 has **no Excel** on Insurance Income **or** the three alternate payment reports. ODBC DSN is **unset** (cannot extract line gold yet). Carestream support ticket draft is ready for staff submit. empty ≠ $0 · inventedGold=false.

## What was done

1. **Reconfirmed disk** — no `insurance_payments*.csv` under SoftDentFinancialExports / ReportExports.
2. **SoftDent live Excel probe** (Output Options labels) for:
   - Payment Allocation → **Printer + Print Preview only** (no Excel)
   - Contractual Plan Analysis → **Printer + Print Preview only**
   - Insurance Payment Distribution → **Printer + Print Preview only**
3. **Probe artifact:** `C:\SoftDentFinancialExports\gold_csv_procurement_alt_menu_probe_2026-07-13.json` (`anyExcel=false`).
4. **ODBC lane** — `SOFTDENT_ODBC_DSN` / `NR2_SOFTDENT_ODBC_DSN` **unset**; `NR2_CONSENT_EXECUTOR` unset. Cannot run read-only SQL gold extract until IT configures DSN + Carestream table map.
5. **Sensei mirror** — configured mirror path not present on this host; no alternate gold file found.
6. **Support ticket pack written** — `docs/CARESTREAM_SUPPORT_TICKET_GOLD_CSV_2026-07-13.md` (subject/body + schema + checklist). Copied to exports for staff.

## Still blocked

| Check | Result |
|-------|--------|
| gapGold | `GOLD_CSV_MISSING` |
| paymentLines | `0` |
| settlementMatrixReady | **false** |
| SoftDent Excel (all gold candidate menus) | **unavailable** |
| SoftDent ODBC DSN | **not configured** |
| Carestream ticket | **draft ready — staff must submit** |

## Staff / IT next (unblocks matrix)

1. Submit Carestream ticket from `CARESTREAM_SUPPORT_TICKET_GOLD_CSV_2026-07-13.md`.
2. **Or** IT: create 64-bit read-only SoftDent SQL DSN (`SoftDentReadOnly`), set `SOFTDENT_ODBC_DSN` + `NR2_CONSENT_EXECUTOR=1`, run schema discovery, then export InsCo×ADA×Paid lines to `insurance_payments_YYYYMMDD.csv` (only after Carestream confirms table/column names — do not guess invent).
3. Drop CSV → Sync / `gold-era-settlement/run`.
4. Gate: `paymentLines>0`, `settlementMatrixReady=true`, `inventedGold=false`.

**Alternate while waiting:** real ERA 835 drop into `C:\SoftDentFinancialExports\era\` (ops lane only — does not hydrate settlement matrix without Gold).

## Honesty

- Do not invent Gold from $641,566.92 Print Preview total
- Do not treat Printer output as gold
- Do not invent ODBC row mappings without Carestream/schema discovery evidence
- OCR expansion remains STOPPED (HAL-10608)
- No SoftDent write-back
