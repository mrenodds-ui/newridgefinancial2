# Moonshot AI — What's Next After Gold CSV OPS Proceed (CONSULT ONLY)

**Date:** 2026-07-13  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10608 (+ bad6d91 honesty)  
**Script:** `scripts/run_moonshot_whats_next_after_gold_csv_ops_consult.py`  
**Apply:** DO NOT APPLY until operator approves (`proceed`).

## Operator request (verbatim)

> next

---

# Verdict
OPS: SoftDent support / alternate Gold CSV procurement — escalate to Carestream support or authorized IT to extract the Insurance Payment Analysis line-item CSV via ODBC or alternate export that SoftDent v19.1.4 cannot Excel-export, delivering real `sd_insurance_payment_lines` to unblock HAL-10605/10606 settlement matrix hydration without inventing the $641,566.92 Print Preview aggregate.

## 0. Operator Intent (verbatim)
next

## 1. Confirmation of Gold CSV OPS proceed + honesty fix (pass/fail; residual risks)
**PASS** — Gold CSV drop attempted; Insurance Income Excel export confirmed unavailable on v19.1.4 (Print Preview only); last-page visual audit recorded ($641,566.92 payments / $7,274.69 adjustments) with `triggersGoldIngest=false`; ERA "ghost ready" from stale fixtures eliminated; `settlementMatrixReady` remains `false` with `paymentLines=0`, `matrixCells=0`.  
**Residual risks:**  
- Practice remains in "visual aggregate only" state indefinitely if support/ODBC path fails.  
- Staff may confuse Print Preview totals with actionable Gold data.  
- Matrix hydration impossible until line-item CSV lands; empty ≠ $0.

## 2. Recommended NEXT (name, why now, effort, REAL files, validation gate)
**OPS: SoftDent support / alternate Gold CSV procurement (HAL-10606 completion via support lane)**  
- **Why now:** HAL-10605/10606/10608 infrastructure is complete and idling. The only blocker is the absence of line-item payment data. Excel export is proven dead on this v19 install. Settlement truth (matrix hydration) is impossible without this file; it is the highest-leverage unblocking action and avoids cosmetic code that cannot compensate for missing foundation data.  
- **Effort:** Staff OPS (1–2 hours to open Carestream support ticket requesting "Insurance Payment Analysis" line-item export, or engage IT to run ODBC query against `SD_PATIENT_INS_PAYMENTS` / `SD_CLAIM_INS_PAYMENTS` mapped to `sd_insurance_payment_lines` schema).  
- **REAL files:** One file `insurance_payments_YYYYMMDD.csv` containing line-level insurance payment allocations (ClaimID, PatientID, InsCo, ADA Code, PaidAmt, DatePosted, Check/EFT #, etc.) — **not summary totals** — dropped into `C:\SoftDentFinancialExports\` and synced.  
- **Validation gate:** `paymentLines > 0` (ingested rows), `matrixCells > 0` (cartesian InsCo×ADA hydrate), `settlementMatrixReady = true`, `gapGold = null`, `inventedGold = false`.

## 3. Why this beats other candidates now
- **ERA 835 drop (Candidate 2):** Valid for remittance workflow, but HAL-10608 honesty fix explicitly makes `settlementMatrixReady` "Gold-only"; ERA aggregates cannot hydrate the matrix cells required for true settlement analysis without Gold line-items.  
- **Gold alternate-path discovery playbook (Candidate 3):** Merely surfaces the blockage in UI; does not procure the actual data file. We already know the Excel path is blocked; we need the file, not a dashboard saying we need the file.  
- **TP UI chip / Catalog filters (Candidates 4,7):** Cosmetic improvements that display "no_settlement" status but do not resolve the underlying data gap or invent dollars.  
- **Coventry MEDIUM (Candidate 5):** Premature optimization without baseline Gold data to validate against; risks false positives without the $641k foundation verified.  
- **COB estimation (Candidate 8):** Explicitly blocked until Gold arrives; cannot calculate secondary without primary payment lines.

## 4. Runner-ups (2–3)
1. **OPS: ERA 835 first real drop** — If support CSV procurement stalls >24–48h, dropping real ERA 835 files into `C:\SoftDentFinancialExports\era\` provides remittance truth and populates the ERA lane, though it cannot hydrate the Gold-dependent settlement matrix per HAL-10608 policy.  
2. **CODE: Wire ERA aggregates into non-settlement HAL posting backlog view** — If Gold procurement exceeds SLA, building a read-only ERA posting view prevents staff from working completely blind while maintaining honesty that these are un-mapped ERA aggregates, not settled matrix lines.

## 5. What NOT to redo
- Do NOT re-attempt SoftDent **Insurance Income → Excel** export (proven unavailable on v19.1.4; Print Preview is the only output).  
- Do NOT invent Gold from Print Preview aggregates ($641,566.92), DaySheet totals, ledger scrolling, or visual estimation.  
- Do NOT expand PWImages JPEG/PDF OCR to extract payment data (HAL-10608 STOP policy remains in force).  
- Do NOT force-match rejected carrier aliases (75 pending) to create phantom payment lines.  
- Do NOT write back to SoftDent (no Register collections invented).  
- Do NOT rebuild HAL-10588–10608 greenfield; build ON them.

## 6. Acceptance criteria
- [ ] Carestream support ticket opened **or** ODBC export executed by authorized IT against production SoftDent DB.  
- [ ] File `insurance_payments_*.csv` lands in `C:\SoftDentFinancialExports\` with line-item detail (one row per payment allocation, not summary rows).  
- [ ] Sync completes with `paymentLines > 0` and `inventedGold = false`.  
- [ ] `settlementMatrixReady` flips to `true` upon successful Gold ingest.  
- [ ] Optional sanity: Summed CSV `PaidAmt` reconciles within 1% of Print Preview visual aggregate ($641,566.92) to confirm completeness.

## 7. Executive Summary (5 bullets)
- **Blocker identified:** SoftDent v19.1.4 cannot export Insurance Income to Excel/CSV; only Print Preview summaries available, which are visually audited but not ingestible.  
- **Current state:** $641,566.92 in payments visible but not actionable; settlement matrix at 0 cells; Gold CSV missing; ERA inbox empty.  
- **Required action:** Procure line-item payment CSV via Carestream support ticket or authorized ODBC query (alternate export path).  
- **Risk mitigation:** Explicitly NOT inventing dollars from aggregates or OCR; refusing to hydrate matrix until real line-item file arrives.  
- **Outcome:** Unblocks HAL-10605/10606 settlement matrix hydration, enabling true InsCo×ADA settlement analysis and secondary COB estimation without phantom data.

## 8. Approval checklist
- [ ] Operator acknowledges SoftDent Excel export is definitively unavailable and approves support escalation or ODBC path.  
- [ ] IT/Security approves ODBC read-only query method (if used) against production SoftDent DB.  
- [ ] Staff briefed on correct drop path (`C:\SoftDentFinancialExports\`) and verification that `paymentLines > 0` before declaring victory.  
- [ ] Commit message template prepared for tracking: `ops(gold-csv-procure): support-odbc-path v19.1.4 workaround`.