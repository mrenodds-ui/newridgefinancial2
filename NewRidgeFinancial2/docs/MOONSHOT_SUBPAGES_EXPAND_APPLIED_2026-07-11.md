# Moonshot Subpages Expansion — APPLIED (Phases 1–4 + Wave 5 COMPLETE)

**Date:** 2026-07-11  
**Consult:** `MOONSHOT_SUBPAGES_EXPAND_CONSULT_2026-07-11.md`  
**Build:** `hal-10460`  
**Operator:** continue coding without deviation

## Shipped

| Wave | What |
|------|------|
| **1–4** | Core drill-downs, workflow benches, docs/payers, ERA/forecast/periods |
| **5** | Remaining master-map **ADD** subpages (blocked reconcilations still omitted) |

### Wave 5 routes

- Taxes: `entities`, `calendar`, `workpapers`
- SoftDent: `register`, `schedule`
- QuickBooks: `coa`, `vendors`
- A/R: `aging-detail`
- Claims: `attachments`
- Narratives: `templates`, `history`, `audit`
- Documents: `tax-docs`
- Library: `codes`
- Office Mgr: `tasks`
- HAL: `history`, `system-logs`

**Still omitted (consult BLOCKED):** SoftDent/QB `reconciliation`

## Files

- `NewRidgeFinancial2/apex_subpages_wave5_pack.py` (new)
- `NewRidgeFinancial2/apex_subpages_pack.py` (resolve → wave5)
- `NewRidgeFinancial2/nr2_local_db.py` (tax_payments)
- `NewRidgeFinancial2/apex_backend.py` (`hal-10460`, tax-payments API)
- `NewRidgeFinancial2/site/apex-core.js`, `apex-bridge.css`, build JSON, tests

## Validate

1. Hard-refresh Apex `hal-10460`
2. Spot-check Taxes Calendar, SoftDent Register, QB Vendors, Narratives Audit, OM Tasks, HAL System Logs
3. Confirm SoftDent/QB Reconciliation are **not** in subnav
4. `python -m pytest NewRidgeFinancial2/test_apex_subpages_pack.py -q`
