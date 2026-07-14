# Moonshot Account-TX Year-Chunk Ingest — APPLIED

**Date:** 2026-07-13  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_ACCOUNT_TX_YEAR_CHUNKS_2026-07-13.md`  
**Operator:** proceed  
**Status:** Applied (read-only Excel/CSV → JSONL → `sd_account_transactions`; empty ≠ $0; no SoftDent write-back)

## Verdict shipped

Ingest verified year-chunk TX exports (TXNALL260712 + TXN2017H2…TXN2026YTD) into the existing SoftDent account-tx SQLite/JSONL ledger via `scripts/continue_softdent_txn_excel.py --ingest-year-chunks`.

## What shipped

| Item | Detail |
|------|--------|
| CSV-as-`.xls` loader | `_load_account_tx_excel_rows` detects OLE vs SoftDent CSV text |
| Year-chunk ingest | `ingest_account_transactions_year_chunks` — manifest parity + purge-by-`source_file` upsert |
| CLI | `continue_softdent_txn_excel.py --ingest-year-chunks` |
| Supersede sample | Purges `TXN260201` after `TXN2026YTD` (no Feb duplicate rows) |
| Log | `C:\SoftDentFinancialExports\softdent_account_tx_year_chunks_ingest.json` |
| Tests | `test_softdent_account_tx_year_chunks_ingest.py` |

## Live validation

| Gate | Result |
|------|--------|
| Chunks | **11/11 ok** (TXNALL + 10 year files) |
| DB total | **549,564** rows |
| Service years | **1996 → 2026** |
| TXNALL max date | **2017-06-28** (no overlap with TXN2017H2) |
| Manifest parity | Exact row match for TXN2017H2…TXN2026YTD |
| Null amounts | **18,676** (not coerced to $0) |
| Donna `27002` Feb 2026 | **5** via `sd_account_transactions` |
| `account_tx_multi_year_available` | **true** |
| Idempotent upsert | existing purge-by-`source_file` |

## Files

| File | Change |
|------|--------|
| `softdent_transaction_extract.py` | CSV load + year-chunk ingest |
| `scripts/continue_softdent_txn_excel.py` | `--ingest-year-chunks` |
| `test_softdent_account_tx_year_chunks_ingest.py` | NEW |
| `scripts/run_moonshot_whats_next_after_account_tx_year_chunks_consult.py` | consult runner |
| `docs/MOONSHOT_WHATS_NEXT_AFTER_ACCOUNT_TX_YEAR_CHUNKS_2026-07-13.md` | consult |

## Validation

```text
python scripts/continue_softdent_txn_excel.py --ingest-year-chunks
cd NewRidgeFinancial2 && python -m unittest test_softdent_account_tx_year_chunks_ingest -v
```

## Not done

- ERA / Ins Plan Collections procurement (still `ERA_835_REQUIRED`)
- Commit of unrelated local hal-10576 Excel-temp WIP
- SoftDent write-back / invented dollars
