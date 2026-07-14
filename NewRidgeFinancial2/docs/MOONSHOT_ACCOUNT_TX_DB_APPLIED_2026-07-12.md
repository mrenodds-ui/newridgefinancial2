# Moonshot SoftDent Account Transactions DB — APPLIED

**Date:** 2026-07-12  
**Consult:** `MOONSHOT_ACCOUNT_TX_DB_DESIGN_CONSULT_2026-07-12.md`  
**Operator:** proceed  
**Status:** Applied (read-only Excel → JSONL → SQLite; empty != $0; no SoftDent write-back)

## Verdict shipped

Extend `C:\SoftDentFinancialExports\softdent_financial_analytics.db` with **`sd_account_transactions`** (separate from `sd_transactions_full`).

## What shipped

| Item | Detail |
|------|--------|
| DDL | `sd_account_transactions` + indexes in `ensure_transactions_schema` |
| Loader | `upsert_account_transactions_jsonl` — purge-by-`source_file`, `stable_id = source_file:row_number` |
| Ingest | `ingest_account_transactions_xls` / `continue_softdent_txn_excel.py --ingest` also upserts DB |
| Read path | `query_account_transactions` prefers DB (`source=sd_account_transactions`), JSONL/XLS fallback |
| Honesty | Money columns nullable REAL; empty → SQL `NULL` (35 null amounts in live load) |

## Live validation (TXN260201)

| Gate | Result |
|------|--------|
| DB rows for source | **1716** |
| Donna `27002` | **5** |
| Null amounts | **35** (not coerced to 0) |
| Idempotent re-upsert | same counts |
| HAL/query source | `sd_account_transactions` |

## Files

| File | Change |
|------|--------|
| `softdent_transaction_extract.py` | schema + upsert + DB-first query |
| `test_softdent_account_tx_db.py` | NEW |
| `docs/MOONSHOT_ACCOUNT_TX_DB_DESIGN_CONSULT_2026-07-12.md` | consult (prior) |
| `scripts/run_moonshot_account_tx_db_design_consult.py` | consult runner |

## Validation

```text
python scripts/continue_softdent_txn_excel.py --ingest
cd NewRidgeFinancial2 && python -m unittest test_softdent_account_tx_db -v
```

## Not done (per Moonshot — do not deviate)

- Extending / mutating `sd_transactions_full` for this ledger  
- New separate `account_transactions.db`  
- ODBC write-back / invented claim links / $0 coercion  
