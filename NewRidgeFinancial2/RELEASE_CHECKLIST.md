# NR2 release checklist

Use before tagging a desktop build or handing off to practice staff.

## Pre-flight

- [ ] `python -m unittest discover -s NewRidgeFinancial2 -p "test_*.py"` — all green
- [ ] `node NewRidgeFinancial2/test_import_loader_accounting.mjs`
- [ ] `node NewRidgeFinancial2/test_import_diagnostics_node.mjs`
- [ ] `node NewRidgeFinancial2/test_month_end_close.mjs`
- [ ] `node NewRidgeFinancial2/validate-hal.mjs`
- [ ] `node NewRidgeFinancial2/validate-pages.mjs`
- [ ] `node NewRidgeFinancial2/smoke_desktop_live.mjs`
- [ ] `node NewRidgeFinancial2/smoke_desktop_pages.mjs`
- [ ] `NewRidgeFinancial2/import-automation/Run-Accounting-MonthEnd-Checklist.ps1` (when imports present)
- [ ] `powershell -ExecutionPolicy Bypass -File scripts/Invoke-NR2PracticeOnboarding.ps1` (first workstation setup)

## Data paths

- [ ] SoftDent cache: `app_data/nr2/document_inbox/softdent/`
- [ ] QuickBooks cache: `app_data/nr2/document_inbox/quickbooks/`
- [ ] Analytics DB: `NR2_FINANCIAL_ANALYTICS_DB` points at `softdent_financial_analytics.db`
- [ ] Legacy `app/data/imports` migrated or empty (first sync migrates automatically)

## Widget smoke (desktop)

- [ ] Financial overview shows production; collections either a dollar amount or “not reported” (not silent $0)
- [ ] Month-end checklist on Financial + Documents pages computes without errors
- [ ] Documents: status transitions enforce reviewer on Posted
- [ ] Journal posting queue: enqueue, approve, export approved CSV
- [ ] Optional: mark document Posted with “Queue journal draft” checked → row appears in SQLite queue

## Out of scope (known gaps)

- Claims pipeline still requires upstream `softdent_claims_export.csv` (not generated from analytics DB)
- QuickBooks A/R is collected from SDK probe summary when available; manual CSV still accepted as fallback
- NR2 never posts to QuickBooks — approved CSV is for human entry only

## HAL eval artifacts

Local `hal_*.md`, `hal_*_raw.json`, and `run_*_eval.py` at repo root are dev-only and gitignored.
