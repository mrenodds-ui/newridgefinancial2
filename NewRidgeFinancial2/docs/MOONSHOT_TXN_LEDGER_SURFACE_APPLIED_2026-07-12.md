# Moonshot TXN Ledger Surface — APPLIED (hal-10569)

**Date:** 2026-07-12  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_TXN_XLS_INGEST_2026-07-12.md`  
**Operator:** proceed  
**Build:** **hal-10569**  
**Status:** Applied (read-only; empty != $0; no SoftDent GUI/write-back)

## What shipped

| Item | Detail |
|------|--------|
| Widget builder | `build_transaction_ledger_table` → SoftDent + Office Manager `data-table` |
| API | `GET /api/apex/softdent/ledger?account_num=&patient_name=&date_range=&limit=` |
| Data source | `C:\SoftDentFinancialExports\tx_parsed\TXN260201.jsonl` (read-only) |
| BUILD_ID | **hal-10569** (+ site asset cache-bust) |
| Honesty | null Amount stays null; unknown account → `emptyState: true` |

## Validation

| Gate | Result |
|------|--------|
| Donna acct 27002 / Feb 2026 | **5** widget rows |
| Unknown account | `status=empty`, `emptyState=true`, `rows=[]` |
| HAL phrase | Donna February 2026 → ledger policy with 27002 / 2026-02-18 |
| Tests | `test_txn_ledger_surface_hal10569` green |

```text
cd NewRidgeFinancial2
python -m unittest test_txn_ledger_surface_hal10569 -v
```

## Files

| File | Change |
|------|--------|
| `apex_better_backend_widgets_pack.py` | `build_transaction_ledger_table` |
| `apex_backend.py` | SoftDent + OM wire; `/api/apex/softdent/ledger`; BUILD_ID |
| `nr2-build.json` + site assets | Cache-bust **hal-10569** |
| `softdent_transaction_extract.py` | Procedure code normalize (whole floats); `load_txn_jsonl` |
| `test_txn_ledger_surface_hal10569.py` | NEW |

## Not done (runner-ups — do not deviate)

- OPS July Register/Collections Ins>0  
- Widgets NICE (pareto / tax-calendar / timeline)  
- Trans-for-Period Excel auto-save GUI  
