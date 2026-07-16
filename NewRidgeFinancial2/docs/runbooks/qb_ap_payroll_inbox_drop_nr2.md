# QuickBooks AP / payroll inbox drop — NR2 (optional)

**Office:** New Ridge Family Financial  
**Rule:** empty ≠ `$0` · no invented AP/payroll rows · SoftDent write-back forbidden  
**Related:** `MOONSHOT_QB_PAYROLL_AP_INBOX_EXPORT_APPLIED_2026-07-12.md`

## Why

`importReadiness` may mark QuickBooks **AP** / **payroll** optional datasets stale when SDK monthly reads are unavailable. Staff CSV drops clear the gap; do not invent dollars.

## Staff steps

1. In QuickBooks (desktop or QBO export staff uses), export:
   - **AP aging / unpaid bills** → save as `quickbooks_ap_aging.csv` (also accepted: `quickbooks_ap.csv`, `unpaid_bills.csv`)
   - **Payroll detail** → save as `quickbooks_payroll_detail.csv` (also accepted: `quickbooks_payroll.csv`)
2. Drop files into the NR2 QuickBooks document inbox (this office):
   - Preferred: `app_data/nr2/document_inbox/quickbooks/`
   - Or the configured QuickBooksExports upstream folder used by SoftDent/QB Sync
3. In NR2 Optical: run **SoftDent/QB Sync** (or `POST /api/apex/sync/qb-payroll-ap-export` only when packing empty-batch markers intentionally).
4. Confirm import readiness no longer lists AP/payroll as blocking (optional severity may still note empty period).

## Empty period honesty

If there are truly no AP/payroll rows for the period:

- Use empty-batch markers (`quickbooks_ap.batch_empty.json` / `quickbooks_payroll.batch_empty.json`) via existing `apex_qb_export_inbox_pack` — **do not** invent balances/wages.
- Widgets must still report empty ≠ `$0`.

## What NOT to do

- Do not invent CSV dollars to clear staleness.
- Do not treat optional QB gaps as a reason to flip `forceCloseAvailable`.
- SoftDent Excel morning bundle remains a separate SoftDent Output Options gate (`docs/runbooks/softdent_excel_enablement_nr2.md`).

## Code (real paths)

- `NewRidgeFinancial2/apex_qb_export_inbox_pack.py`
- `NewRidgeFinancial2/import_sync.py` (`QUICKBOOKS_AP_NAMES` / payroll names)
- `NewRidgeFinancial2/test_qb_export_inbox.py`
