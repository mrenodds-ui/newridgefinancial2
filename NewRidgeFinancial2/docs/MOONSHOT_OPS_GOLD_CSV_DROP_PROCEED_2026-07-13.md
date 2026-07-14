# OPS Proceed — SoftDent Gold CSV drop attempt (after HAL-10608)

**Date:** 2026-07-13  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_HAL10608_2026-07-13.md`  
**Operator:** `proceed`  
**Build:** `hal-10608`

## Verdict

**OPS partially executed; Gold CSV still missing.** SoftDent v19.1.4 cannot export Insurance Income to Excel/CSV. Print Preview last-page visual audit was recorded. Settlement matrix remains unhydrated (`paymentLines=0`). empty ≠ $0 · inventedGold=false.

## What was done

1. **Disk hunt** — no `insurance_payments*.csv` under SoftDentFinancialExports / ReportExports / Downloads.
2. **SoftDent live** — `CS SoftDent Software v19.1.4 - [INSURANCE INCOME REPORT]` Print Preview opened (period shown `07/13/26–07/13/26`).
3. **Paged to last page** — Next disabled; **page 6/6**.
4. **Last-page totals (visual only):**
   - TOTAL PAYMENTS **$641,566.92**
   - TOTAL ADJUSTMENTS **$7,274.69**
5. **HAL-10590 audit appended** — `reportType=InsuranceIncome`, `lastPageAggregateTotal=641566.92`, `pageCount=6`, `triggersGoldIngest=false` (`print_preview_audit_log.jsonl`).
6. **HAL-10608 honesty fix** — ERA “ghost ready” from stale `t.835` fixtures (`totalPaid=null`) no longer marks readiness; `settlementMatrixReady` is Gold-only. Live readiness now **false** until Gold CSV or paid ERA evidence.

## Screenshots

- `docs/_softdent_shot.png` (earlier page)
- `docs/_softdent_shot_lastpage.png` (last page with totals)

## Still blocked for settlement matrix

| Check | Result |
|-------|--------|
| gapGold | `GOLD_CSV_MISSING` |
| paymentLines | `0` |
| matrixCells | `0` |
| settlementMatrixReady | **false** |
| SoftDent Excel for Insurance Income | **unavailable** (Print Preview only) |

## Staff next (to actually unblock Gold)

1. Obtain a **real line-item** insurance payment CSV from SoftDent support / alternate export path (not Print Preview aggregates).
2. Save as `C:\SoftDentFinancialExports\insurance_payments_YYYYMMDD.csv`.
3. Sync or `POST /api/apex/gold-era-settlement/run`.
4. Gate: `paymentLines>0`, `settlementMatrixReady=true`, `inventedGold=false`.

**Alternate:** drop real ERA 835 files into `C:\SoftDentFinancialExports\era\` (ops lane only — still does not invent matrix cells without Gold).

## Honesty

- Print Preview ≠ `sd_insurance_payment_lines`
- Do not invent Gold from $641,566.92 visual total
- No SoftDent write-back
- OCR expansion remains STOPPED (HAL-10608)
