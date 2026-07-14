# Moonshot QB Payroll/AP Export → Inbox — APPLIED

**Date:** 2026-07-12  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_REC005_REC007_2026-07-12.md`  
**Operator:** proceed (typo: proceex)  

## Goal

Close the optional live gap for `quickbooks.payroll` / `quickbooks.ap` by dropping atomic CSVs into the real QuickBooks document-inbox and syncing upstream payroll/AP filenames on import pull. Empty ≠ $0; no SoftDent write-back.

## Applied (real paths — not fictional `apex_hal.py`)

| Piece | Where |
|-------|--------|
| Atomic CSV writer + empty-batch sidecar | `apex_qb_export_inbox_pack.py` |
| Gap honesty treats empty-batch as present | `apex_qb_payroll_pack.assess_payroll_ap_gap` |
| Sync pulls payroll/AP from upstream roots | `import_sync.py` (`QUICKBOOKS_PAYROLL_NAMES` / `QUICKBOOKS_AP_NAMES`) |
| API | `POST /api/apex/sync/qb-payroll-ap-export` |
| Tests | `test_qb_export_inbox.py` |

## Filenames (import-manifest)

- Payroll: `quickbooks_payroll_detail.csv` (also accepts `quickbooks_payroll.csv`, …)
- AP: `quickbooks_ap_aging.csv` (also accepts `quickbooks_ap.csv`, `unpaid_bills.csv`, …)
- Empty markers: `quickbooks_payroll.batch_empty.json`, `quickbooks_ap.batch_empty.json`

## Honesty

- No rows without `emptyPayroll` / `emptyAp` → reject (do not invent wages/balances)
- Empty batch = header-only CSV + sidecar; widgets still report empty ≠ $0

## Validate

1. `python -m pytest test_qb_export_inbox.py -q`  
2. `POST /api/apex/sync/qb-payroll-ap-export` with `{"emptyPayroll":true,"emptyAp":true}`  
3. Ask HAL what’s missing for QB → should not list payroll/AP as missing (or note empty period)  
4. Drop real CSVs into `app_data/nr2/document_inbox/quickbooks/` or upstream QuickBooksExports → Sync  
