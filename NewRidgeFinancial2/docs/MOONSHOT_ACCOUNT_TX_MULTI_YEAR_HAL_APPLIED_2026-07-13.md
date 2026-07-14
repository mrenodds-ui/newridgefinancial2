# Moonshot HAL Multi-Year Account-TX Wiring — APPLIED

**Date:** 2026-07-13  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_ACCOUNT_TX_YEAR_CHUNK_INGEST_2026-07-13.md`  
**Operator:** proceed  
**Status:** Applied (HAL → `sd_account_transactions`; empty ≠ $0; no SoftDent write-back)

## Verdict shipped

Wire HAL gateway multi-year account-tx queries to the ingested `sd_account_transactions` ledger with honest coverage metadata (`account_tx_multi_year_available`, `db_total`, `available_range`).

## What shipped

| Item | Detail |
|------|--------|
| Year / span parsing | `_parse_date_range("2018")`, `"2018:2019"` → full-year ISO bounds |
| Filter extraction | `account history`, `in 2018`, `from 2018 to 2019`; stopwords avoid `Show account` false names |
| Coverage helper | `account_tx_ledger_coverage()` from ingest log + DB min/max |
| HAL reply | `format_account_transactions_hal_reply` cites source + multi-year coverage |
| Gateway | `prefer_db=True` on ledger policy path |
| Donna upsert count | Scoped to `source_file` (no cross-source inflation) |
| Tests | `test_account_tx_multi_year_hal.py`; account-tx DB tests use temp DB |

## Live validation

| Gate | Result |
|------|--------|
| Donna `27002` Feb 2026 | **5** rows from `sd_account_transactions` |
| HAL Donna Feb policy | PASS — includes `account_tx_multi_year_available=true` |
| HAL “Show account 27002 transactions in 2018” | PASS — DB source + coverage chip |
| Coverage | `db_total=549564`, range **1996 → 2026** |
| Unit tests | **15/15 PASS** (multi-year + ledger + account-tx DB) |

## Files

| File | Change |
|------|--------|
| `softdent_transaction_extract.py` | coverage + year parsing + HAL format |
| `nr2_hal_gateway.py` | multi-year filter extraction |
| `test_account_tx_multi_year_hal.py` | NEW |
| `test_softdent_account_tx_db.py` | temp DB (protect live year-chunk ledger) |
| `scripts/run_moonshot_whats_next_after_account_tx_year_chunk_ingest_consult.py` | consult runner |
| `docs/MOONSHOT_WHATS_NEXT_AFTER_ACCOUNT_TX_YEAR_CHUNK_INGEST_2026-07-13.md` | consult |

## Validation

```text
cd NewRidgeFinancial2
python -m unittest test_account_tx_multi_year_hal test_txn_ledger_surface_hal10569 test_softdent_account_tx_db -v
```

## Not done

- ERA / Ins Plan Collections procurement (`ERA_835_REQUIRED`)
- BUILD_ID bump (kept `hal-10576`; coverage is data/path wiring)
- SoftDent write-back / invented dollars
