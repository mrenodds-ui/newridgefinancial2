# Moonshot Desktop / HAL / Tax / EBITDA — Applied

**Date:** 2026-07-10  
**Build:** **hal-10300**  
**Consult:** `MOONSHOT_DESKTOP_HAL_TAX_EBITDA_CONSULT_2026-07-10.md`  
**Status:** Applied after operator **proceed**

## T1 — Desktop icon
- Ran existing `scripts/Create-Desktop-Shortcut.ps1` → Desktop `New Ridge Financial.lnk` → `StartProgram.bat`
- Icon: `assets/nr2-icon.ico` (copied to `site/favicon.ico` for browser tab)

## T2 — HAL on all widgets
- Every mosaic instrument (except HAL chat) gets **◐ Ask HAL**
- Context packet prepended to query (page, id, label, values/bars/slices/steps) — no invented dollars
- Opens HAL page / chat via existing `askHalFromBridge`

## T3 — Sync SoftDent + QuickBooks verify
- Apex Sync (`POST /api/apex/sync/trigger`) now also runs `sync_accounting_documents(LocalStore)` then `load_import_bundle(fullSync=True)`
- Returns diagnostics + `freshness` banner payload
- **Import Sync Verify** status instrument on Financial + Office Mgr
- Meta line shows sync result after refresh

## T4 — Federal + Kansas S-corp tax + EBITDA
- Taxes page: Federal / Kansas planning KPIs, book-to-tax waterfall, CPA banner
- `tax_engine.compute_ebitda_walk()` — Net Income + Dep/Amort + Interest when present in QB categories
- EBITDA waterfall on Financial + Taxes
- `POST /api/apex/tax/calculate-planning` for planning recalculation
- **Planning only — not for filing**

## T5 — Tax returns library
- Local path: `app_data/nr2/document_library/tax_returns/YYYY/{federal,kansas}/`
- Documents page: **Tax Returns Library** instrument (list / download / upload)
- APIs: `GET /api/apex/tax-returns`, `GET /api/apex/tax-returns/file?path=`, `POST /api/apex/tax-returns/upload`
- PDFs gitignored

## Honesty
- Never invent dollars; empty when imports lack fields
- Tax outputs labeled planning / CPA review
- EBITDA labeled management calc, not GAAP
