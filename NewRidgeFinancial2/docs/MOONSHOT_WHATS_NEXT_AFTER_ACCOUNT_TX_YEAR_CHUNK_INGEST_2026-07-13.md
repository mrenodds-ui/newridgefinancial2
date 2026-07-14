# Moonshot AI — What's Next After Account-TX Year-Chunk Ingest (CONSULT ONLY)

**Date:** 2026-07-13  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10576  
**Prior:** year-chunk ingest shipped (`6843a9c`; 549564 rows)  
**Script:** `scripts/run_moonshot_whats_next_after_account_tx_year_chunk_ingest_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> next

---

# Verdict
Wire the HAL gateway (`nr2_hal_gateway.py`) to query `sd_account_transactions` for multi-year account history, exposing the 549k-row ledger and date-span honesty to operators without inventing dollars.

## 0. Operator Intent (verbatim: next)
next

## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
**Name:** HAL Gateway Multi-Year Account-TX Wiring  

**Why now:** The 549k-row ingest (1996–2026) is live in `softdent_financial_analytics.db` and validated (Donna 27002 Feb=5 rows), but HAL currently returns “no history” or limited single-year extracts because the gateway does not yet route account queries to `sd_account_transactions`. This is the highest-leverage CODE unlock: it makes the just-shipped year-chunk data immediately usable by operators while ERA procurement (external) and July Register Ins>0 (blocked on ERA) remain stalled.  

**Effort:** Small–Medium (1–2 files, ~60–100 lines):  
- Extend `softdent_transaction_extract.py` with `query_account_transactions(account_id, date_from, date_to)` → returns rows + `source_table` tag.  
- Modify `nr2_hal_gateway.py` to route account-history intent through the new query, injecting `account_tx_multi_year_available=true` and honest `service_date_min/max` (1996–2026) into the HAL reply context.  
- Add formatters that render transaction lists without coercing null amounts to $0.  

**REAL files:**  
- `NewRidgeFinancial2/nr2_hal_gateway.py` (HAL policy surface)  
- `NewRidgeFinancial2/softdent_transaction_extract.py` (query helper)  
- `C:\SoftDentFinancialExports\softdent_financial_analytics.db` (source of truth)  
- `C:\SoftDentFinancialExports\softdent_account_tx_year_chunks_ingest.json` (metadata for date-range honesty)  

**Validation gate:**  
HAL query “Show Donna 27002 transactions Feb 2026” returns 5 rows cited as `source: sd_account_transactions` with `db_total: 549564` and `available_range: 1996-07-12 to 2026-02-28`; query “Account history 2018–2020” returns actual DB rows rather than “no data found.”

## 2. Runner-ups (2–3, why not now)
- **Browser/HAL Smoke Test (multi-year query):** Depends on the gateway wiring above; lower priority than enabling the feature itself. Defer until after this package ships so the smoke test has a real surface to validate.  
- **ERA 835 Procurement (OPS):** Discovery proved `candidateCount=0` and local files are absent; procurement requires external payer-portal contracts, not local CODE. Defer until procurement delivers files to `C:\SoftDentFinancialExports\ERA_Inbound`.  
- **July Register/Collections Ins>0 (OPS):** Blocked by `registerInsPlanZero=true` and `ERA_835_REQUIRED`; impossible to complete without real 835 remittance data. Defer until ERA ingest unblocks the insurance dollar stream.

## 3. What NOT to redo
- **Year-chunk re-pull or re-ingest:** 11/11 chunks verified (TXNALL + TXN2017H2…TXN2026YTD) at 549,564 rows; manifest parity confirmed.  
- **ERA discovery:** Already conclusive (zero local candidates); do not re-run scans.  
- **SoftDent write-back:** Never write synthetic dollars or insurance plans back to SoftDent; maintain read-only ledger discipline.  
- **Inventing insurance dollars:** `registerInsPlanZero=true` and `insurance: 0.0` are ground truth; do not fabricate 835-level adjustments.

## 4. Acceptance criteria
- [ ] `nr2_hal_gateway.py` routes account-transaction intent to `query_account_transactions()` in `softdent_transaction_extract.py`.  
- [ ] Query returns rows from `sd_account_transactions` with correct `service_date`, `amount` (nulls preserved), and `source_file` provenance.  
- [ ] HAL reply includes `account_tx_multi_year_available: true` and honest `date_range: {min: "1996-07-12", max: "2026-02-28"}`.  
- [ ] Donna 27002 Feb 2026 test returns exactly 5 rows; Jan 2018 test returns 3 rows.  
- [ ] Empty result sets distinguish “no transactions for this account/period” from “data unavailable” without inventing zero-dollar rows.  
- [ ] No references to GitHub PRs or fictional file trees; only paths listed in REAL PATHS are used.

## 5. Executive Summary (5 bullets)
- **Ingest is dark:** 549,564 rows (1996–2026) reside in the local SQLite ledger but remain invisible to HAL operators because the gateway lacks a query path.  
- **Highest-ROI unlock:** Wiring the existing `nr2_hal_gateway.py` to the existing DB enables immediate multi-year account answers (e.g., Donna Feb 2026) without external procurement.  
- **Additive only:** New helper `query_account_transactions` + context flags; no modification of SoftDent source data or invention of ERA dollars.  
- **Date-span honesty:** HAL replies will cite actual `service_date_min/max` from the ingest manifest, managing operator expectations for historical coverage.  
- **Unblocks parallel work:** Once live, smoke tests and widget UX can be validated against real DB responses rather than mocked data.

## 6. Approval checklist
- [ ] Operator confirms no pending HAL gateway refactors that would conflict with `nr2_hal_gateway.py` changes.  
- [ ] Confirm `softdent_transaction_extract.py` can safely host SQL queries against `sd_account_transactions` without breaking existing Excel-extract paths.  
- [ ] Operator accepts exposing 1996–2026 date range in HAL replies (patient privacy/coverage policy check).  
- [ ] Acknowledge that insurance dollar gaps (`ERA_835_REQUIRED`) will persist until external 835 files arrive; this package does not close that gap.
