# SoftDent FULL Data Retrieval — Applied

**Date:** 2026-07-10  
**Build:** **hal-10370**  
**Consult:** `MOONSHOT_SOFTDENT_FULL_EXTRACT_CODING_2026-07-10.md`  
**Status:** Moonshot coding pack applied after operator “proceed” (adapted to live JSONL shape)

## What landed

### Transactions (MUST)
- New `softdent_transaction_extract.py`
  - Reads live `C:\SoftDentFinancialExports\transactions_for_period.jsonl` (`normalized` wrapper)
  - Upserts **every line item** into `sd_transactions_full`
  - Skips period-totals header rows
  - Parity proof: **1284 / 1284** (ratio **1.0**) on live run
  - Types captured: transaction 1048 · payment 164 · adjustment 72
- Register → `sd_register_detail` (14 rows from live register JSONL)
- Operatory → `sd_operatory_schedule` from `operatory_schedule.json` `operatoryChairs[]` (8 slots live)
- Typed rows also refresh `sd_payments` / `sd_adjustments`
- Does **not** write the legacy `transactions` table (owned by SoftDent financial importer)

### Payment / adjustment detection
- `softdent_odbc_extract.py`: `_normalize_softdent_code()` so `2.00` → `2`, `51.0` → `51`
- `_is_payment` / `_is_adjustment` honor SoftDent v19 codes + description tokens

### CSV report ingest (SHOULD)
- `ingest_csv_reports_to_sqlite()` in `softdent_practice_exports.py`
- Flexible header aliases → `sd_treatment_plan_csv` / `sd_hygiene_recall_csv` / `sd_case_acceptance_csv`
- Hydrates empty `treatment_plan_summary` when CSV present

### Sync wiring
- `import_sync.py` runs transaction extract + CSV ingest after ODBC/Sensei refresh
- Result surfaces as `softdent.transactionExtract` + `softdent.csvReportIngest`

### ODBC discovery (NICE prep)
- `suggest_transaction_queries()` added to `discover_softdent_odbc_schema.py`
- Emits illustrative fee / payment-plan / ledger / transaction SQL when DSN is configured

## Live verification (2026-07-10)

```text
ok: true
transactions: 1284
register: 14
operatory: 8
parity_ratio: 1.0
date_range: 2026-05-04 → 2026-05-28
amount_sum: 330622.22
```

## Tests
- `test_softdent_transaction_extract.py` (new)
- Existing `test_softdent_odbc_extract.py` still green

## Honesty / limits
- Does not invent SoftDent SQL schema — ODBC deep claims/fees/plans still need DSN + discovery
- Document Center / radiographs / encrypted audit log remain unreachable
- Register JSONL on this practice is mostly summary labels (not patient-level payment detail)
- Transaction export codes are often dollar-like strings; type field (`payment`/`adjustment`) is authoritative for classification

## Files
- `softdent_transaction_extract.py` (new)
- `softdent_odbc_extract.py`
- `softdent_practice_exports.py`
- `import_sync.py`
- `scripts/discover_softdent_odbc_schema.py`
- `test_softdent_transaction_extract.py` (new)
- `nr2-build.json` / `site/nr2-build.json` → **hal-10370**
