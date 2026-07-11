# NewRidgeFinancial 2.0

Browser-based mission-control program for New Ridge Family Financial.

The legacy program in `_legacy/` is for reference only and is not used here.

## Run

Double-click `StartProgram.bat` (repo root), or run:

```powershell
scripts\start_nr2_browser.ps1
```

The launcher starts the NR2 server on **https://127.0.0.1:8765/** (TLS by default) and opens your default browser to that address.

### Staff pages (mock-only)

Staff pages render **elite mock HTML** inside the live app chrome (`NR2_STAFF_MOCK_ONLY`). To add or replace a page:

1. Create or edit `.local_logs/moonshot_financial_eval/page_mockups_elite/{page-id}.html`
2. Run `node NewRidgeFinancial2/scripts/sync-mockup-elite-pages.mjs`
3. Optionally add nav labels in `site/moonshot-page-registry.js` (`PAGE_META`)
4. Restart Start Program and open `#page-id`

Legacy wired widgets, layout engine, and chart bundles are **not** loaded on the 8765 app until live-wire sign-off. HAL (`#hal`) stays live.

The server binds to **127.0.0.1 only** (not LAN). API write routes (posting queue, outbound) require a per-session loopback token issued at `/api/app-info` and reject cross-origin mutation requests in browser mode.

### Operator security checklist

- Use **one browser tab** for NR2 financial work (a second tab shows a warning).
- Prefer a **dedicated browser profile** with extensions disabled for `https://127.0.0.1:8765/`.
- Confirm port **8765** is not reachable from another PC on the LAN.
- **Cloud HAL** is off by default in browser mode; set `sessionStorage.nr2AllowCloudHal = "1"` only if you explicitly need cloud reasoning.
- Financial pages show **Last import load**; amber/red banners mean refresh imports before posting or month-end decisions.

## Files

```
NewRidgeFinancial2/
  browser_app.py     browser app launcher (Bottle HTTP server, no pywebview)
  desktop_app.py     legacy pywebview launcher (not used by Start Program)
  import_sync.py     syncs live SoftDent/QuickBooks exports into import cache
  import_loader.py   reads SoftDent / QuickBooks export files for HAL
  accounting_tools.py  single-source chart of accounts + journal templates (Python)
  accounting_bridge.py journal draft + SQLite posting queue bridge
  import-manifest.json shared import filename contract (Python + JS)
  local_store.py     local SQLite state store
  site/
    import-loader.js maps import files into dashboard shapes HAL uses
    index.html        app shell
    styles.css        mission-control shell styling
    app.js            internal routing and local app state
    page-views.js     real client-side screens for program pages
    hal-page.js       real HAL Command Center screen
    desktop-bridge.js loopback HTTP + optional pywebview bridge
```

## Stop

`StopNewRidgeFinancial2.bat`

## SoftDent / QuickBooks imports (read-only)

**Default (direct-first):** widgets scan upstream export roots for the newest SoftDent and QuickBooks files via `practice_source_access.py`. Document-inbox cache folders are fallback only:

- `app_data/nr2/document_inbox/softdent/`
- `app_data/nr2/document_inbox/quickbooks/`

Set `NR2_DIRECT_FIRST_IMPORTS=0` to use cache-only mode with scheduled `Sync-HAL-Imports.ps1` copies instead.

Override cache paths with `SOFTDENT_IMPORT_DIR` or `QUICKBOOKS_IMPORT_DIR` if needed.

On first sync, any files still in the legacy `app/data/imports/` folders are migrated into the document-inbox cache automatically.

When imports are missing, dashboards show empty shells — there is no bundled mock or demo data.

Automation is in `import-automation/`:

- `Sync-HAL-Imports.ps1` — copies approved SoftDent and QuickBooks exports into the document-inbox cache (financial widgets).
- `Sync-HAL-Document-Sources.ps1` — import pull plus Documents page queue sync.
- `Verify-HAL-Readiness.ps1` — pre-flight check for upstream paths and required exports.
- `Register-HAL-Import-Automation.ps1` — registers a Windows scheduled task (import sync every 5 minutes).
- `Register-HAL-Document-Source-Automation.ps1` — registers document-source sync (every 30 minutes).

Default upstream source folders (override in repo `.env`):

- SoftDent: `NR2_SOFTDENT_EXPORT_SOURCE` or `SOFTDENT_SOURCE_DIR` (see `import-manifest.json` defaults)
- QuickBooks: `NR2_QUICKBOOKS_EXPORT_SOURCE` or `QUICKBOOKS_SOURCE_DIR`

After files are copied, ask HAL **"refresh imports"** or restart Start Program. HAL reads only — nothing is posted or written back to SoftDent or QuickBooks.

In direct-first mode (`NR2_DIRECT_FIRST_IMPORTS=1`, default), **refresh imports** re-scans upstream exports instead of copying into cache. Optional `NR2_DIRECT_FIRST_WRITE_CACHE=1` mirrors direct reads into document-inbox on refresh.

HAL's top priority is to monitor the program, place correct import data into the right financial and accounting views, apply accounting and Excel-style review, and recommend the next safe staff action.

## Local HAL models (GPU)

Workstation default (**R9700 32 GB**, 2026-07-11): single GPU-pinned **`hal-local:24b`** (Q4_K_M) via Ollama on `127.0.0.1:11434`. Orchestrator lane ids (`chat8b`, `escalate30b`, …) still exist but all resolve to that one model. Prior 8B/30B tags stay on disk for rollback / future external-GPU 8B.

```powershell
powershell -ExecutionPolicy Bypass -File .\NewRidgeFinancial2\model-automation\Apply-HAL-GPU-Performance.ps1
powershell -ExecutionPolicy Bypass -File .\NewRidgeFinancial2\model-automation\Start-HAL-Ollama-Local.ps1
```

Config: `site/data/hal-models.json` (`gpuPinnedModels`, `singleGpuLayout`).  
Detail: `docs/HAL_LOCAL_24B_SINGLE_GPU_2026-07-11.md` · architecture overview: repo-root `ARCHITECTURE.md`.

## Tests

From `NewRidgeFinancial2/`:

```powershell
python -m unittest discover -s . -p "test_*.py"
node test_import_loader_accounting.mjs
node test_import_diagnostics_node.mjs
node test_month_end_close.mjs
node validate-hal.mjs
node validate-pages.mjs
```

CI runs the same checks via `.github/workflows/validate-nr2.yml` (automatic on push).  
Secret Scan runs on push/PR; legacy Build/Frontend/FastAPI workflows are manual-only.  
See repo-root `README.md` (CI section) and `docs/nr2-audit-findings.md`.
