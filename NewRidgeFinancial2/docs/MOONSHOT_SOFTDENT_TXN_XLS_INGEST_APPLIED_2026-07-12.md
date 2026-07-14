# Moonshot SoftDent TXN Excel Ingest + HAL Patient Ledger — APPLIED

**Date:** 2026-07-12  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_ACCOUNT_TX_EXCEL_2026-07-12.md`  
**Operator:** proceed with recommendations and do not deviate  
**Status:** Applied (read-only Excel parse; no SoftDent GUI automation)

## What shipped

| Item | Detail |
|------|--------|
| `parse_account_transactions_xls` | Typed records: date, account_num, patient_name, provider, procedure, amount, note_flag (.xls via xlrd / .xlsx via openpyxl) |
| JSONL ingest | `scripts/continue_softdent_txn_excel.py` default/`--ingest` → `C:\SoftDentFinancialExports\tx_parsed\` |
| HAL query | `nr2_hal_gateway.query_account_transactions(account_num, patient_name, date_range)` + local-policy Donna-style ledger replies |
| Honesty | empty money cells stay `null` (never invent $0); no SoftDent write-back |

## Live validation (TXN260201.xls)

| Gate | Result |
|------|--------|
| Sheet `rowCount` | **1736** |
| Typed data records | 1716 |
| Nickel name mentions | **8** |
| Donna Nickel acct **27002** | **5** lines (matches validation `donnaLines`) |
| JSONL | `C:\SoftDentFinancialExports\tx_parsed\TXN260201.jsonl` |
| HAL | `What are Donna Nickel's February 2026 transactions?` → `policy:softdent-account-tx-ledger` with 27002 / 2026-02-18 lines |

## Files

| File | Change |
|------|--------|
| `softdent_transaction_extract.py` | parse / ingest / query / format HAL reply |
| `scripts/continue_softdent_txn_excel.py` | default ingest mode; `--gui` preserves desktop continue |
| `nr2_hal_gateway.py` | expose `query_account_transactions`; ledger local policy + chat context |
| `test_softdent_txn_xls_ingest.py` | NEW — live TXN + HAL policy gates |

## Validation

```text
python scripts/continue_softdent_txn_excel.py --ingest
cd NewRidgeFinancial2 && python -m unittest test_softdent_txn_xls_ingest test_softdent_signon -v
```

## Not done (per Moonshot runner-ups — do not deviate)

- Trans-for-Period Excel auto-save GUI wiring  
- OPS July Register/Collections Ins/Patient export  
- Better Backend Widgets SHOULD follow-ups  
