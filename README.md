
# New Ridge Family Financial

Production FastAPI backend plus the supported `frontend/` React SPA for financial analysis of New Ridge Family Dental.

## Supported Surfaces

- `app/` is the supported backend and API surface.
- `frontend/` is the supported browser application.

## Onboarding

- Backend: Python 3.13+, FastAPI, Uvicorn
- Frontend: React, TypeScript, Vite (see frontend/README.md)
- All endpoints require HTTP Basic authentication (see docs/API.md)

### Run Backend Locally

```powershell
cd C:\NewRidgeFamilyFinancial
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8095 --reload
```

Open: <http://127.0.0.1:8095/docs> (API docs)

### Run Integrated Dashboard

```powershell
cd C:\NewRidgeFamilyFinancial
npm install --prefix frontend
npm run dashboard:start
```

Open: <http://127.0.0.1:8095/app>

For automatic frontend rebuilds while keeping the backend-served `/app` runtime, use:

```powershell
npm run dashboard:watch
```

That command watches the frontend production bundle, rebuilds it on changes, and serves the merged app through FastAPI with backend reload enabled.

Before starting the backend, configure `APP_AUTH_USERS_JSON` plus optional `HAL_SQLITE_PATH`, `HAL_CHROMA_PATH`, and `HAL_EMBEDDING_PROVIDER` in your environment or `.env` file. Prefer `password_hash` entries in `APP_AUTH_USERS_JSON`; legacy plaintext `password` entries still load for compatibility but should be rotated out. The app now fails fast at startup if `APP_AUTH_USERS_JSON` is missing, malformed, or missing required HAL/admin roles. See `.env.example` for the expected shape.

For production or staging deployment, also complete the **Production environment checklist** below and read `docs/API.md` **Security contracts**.

### Production environment checklist

Set these in deployment configuration (not copy-pasted from `.env.example` placeholders):

| Variable | Required when | Notes |
| --- | --- | --- |
| `APP_ENV` | Production/staging | Set `APP_ENV=production`. Unset `APP_ENV` is treated as production-like. Use `APP_ENV=development` only on local workstations. |
| `APP_AUTH_USERS_JSON` | Always | Generate per environment. Do **not** use example hashes or placeholder users in production. |
| `APP_AUTH_SESSION_SECRET` | Production-like | Long random secret. Required when `APP_ENV` is unset, `production`, `staging`, or any non-dev value. |
| `WIDGET_API_KEY` | Production-like | Required for `/api/widgets/update` unless you are on explicit local dev/test **and** calling from localhost only. |
| `LITELLM_MASTER_KEY` | Non-local LiteLLM proxy | Required if the LiteLLM proxy is used beyond strictly local-only binding. Do not expose the proxy without auth. |
| `LITELLM_PROXY_BASE_URL` | Optional | Default local proxy is `http://127.0.0.1:4000`. Keep bind on localhost unless intentionally exposing with auth. |
| `AI_FRONTEND_BASE_URL` / `OLLAMA_FRONTEND_BASE_URL` | Local AI enabled | Frontend lane (default `http://127.0.0.1:11434`). `AI_*` takes precedence when set. |
| `AI_BACKEND_BASE_URL` / `OLLAMA_BACKEND_BASE_URL` | Local AI enabled | Backend/HAL lane (default `http://127.0.0.1:11435`). |
| `AI_FRONTEND_MODEL` / `OLLAMA_FRONTEND_MODEL` | Local AI enabled | Default frontend tag: `mistral-small3.1:24b`. |
| `AI_BACKEND_MODEL` / `OLLAMA_BACKEND_MODEL` | Local AI enabled | Default backend tag: `qwen3:30b`. |

**Operational notes:**

- Do not use example auth placeholders from `.env.example` in production.
- Do not expose the LiteLLM proxy without `LITELLM_MASTER_KEY` on any shared or remote interface.
- Local 235B evaluator outputs (`235b_*.md`, `235b_*.txt`, `235b_*.json`, raw logs) are gitignored — keep them local unless explicitly sanitized and approved for commit.
- Normal runtime must **not** use `:11436` or `qwen3:235b`; that lane is for isolated offline evaluation workflows only (see `docs/local_quantized_ai_setup.md`).

HAL now has two safe local financial context paths:

- Indexed aggregate SoftDent summaries built from the local dashboard export files in the repo, including KPI rollups, provider ranking, and payer-mix summaries.
- Optional controlled QuickBooks summary queries, enabled through approved read-only SQL in `HAL_QB_REVENUE_SQL`, `HAL_QB_EXPENSES_SQL`, or `HAL_QB_AR_SQL`.
- Live QuickBooks report helpers are SDK-only in production; raw ODBC queries are reserved for explicit admin diagnostics.

HAL still does not expose raw patient records or arbitrary QuickBooks SQL execution.

For the recommended QuickBooks Desktop safety model for this repo, see `docs/quickbooks_desktop_safe_architecture.md`.
For the local SQLite + OCR + automation accounting stack, see `docs/accounting/local_ai_accounting_stack.md`.

### Run Frontend Locally

Use this only when you explicitly want the separate Vite dev server. The supported merged runtime is the backend-served dashboard at `http://127.0.0.1:8095/app`.

```sh
npm install --prefix frontend
npm run dev --prefix frontend
```

Open: <http://localhost:5173/app>

---

See docs/API.md for endpoint documentation and authentication details.
For insurance narrative case packets and SoftDent export-file adapters (claims, procedures, patient ledger, claim status, clinical notes), see `docs/insurance_narratives.md`.

## SPA Overview

Single-page application (SPA) for financial analysis of New Ridge Family Dental.

- The supported SPA lives in `frontend/` and runs on <http://localhost:5173/app> by default.
- The supported integrated runtime serves that SPA from FastAPI at <http://127.0.0.1:8095/app> after `npm run dashboard:start`.
- It uses React, TypeScript, and Vite.
- It consumes backend APIs and can cache selected dashboard state in-browser.
- No writes are made to production databases from the SPA.

If you are developing the SPA, use the `frontend/` workspace and run Vite only when you specifically need its isolated dev server or hot-reload workflow.

## Run Locally

Primary merged runtime:

```sh
npm install --prefix frontend
npm run dashboard:start
```

Open: <http://127.0.0.1:8095/app>

Merged watch mode for local development:

```sh
npm run dashboard:watch
```

Optional separate frontend dev server:

```sh
npm install --prefix frontend
npm run dev --prefix frontend
```

Open: <http://localhost:5173/app>

## CI/CD Host Header Validation

If CI/CD or E2E tests fail due to host header validation, ensure your test runner and proxy are forwarding the correct Host header. Some security middleware may block requests with unexpected Host values.

## Backend Overview

FastAPI backend for financial analysis of New Ridge Family Dental.

## Scope

- No login page.
- No patient-facing workflows.
- Read-only SoftDent and QuickBooks imports.
- No writes to production databases.
- Local host binding by default: 127.0.0.1.

## Tech Stack

- Python, FastAPI, Jinja2
- Chart.js
- SQLite cache database
- Lightweight built-in analytics pipeline (pandas-ready upgrade path)

## Windows/Node-gyp/Visual Studio Note

If you are developing or running the backend on Windows, you **must** install Visual Studio with the "Desktop development with C++" workload to build native modules (e.g., better-sqlite3). Download from: <https://visualstudio.microsoft.com/visual-cpp-build-tools/>

If you only need to run the backend and not develop, consider using WSL or a Linux VM to avoid file lock and build issues.

## Pandas Limitation

Pandas is not installed by default due to missing wheels on Windows without build tools. If you need pandas, install it after ensuring Visual Studio is present, or use a platform with prebuilt wheels.

## CORS/Proxy/Frontend Integration

The frontend defaults to `/api`. In the merged runtime, those requests stay same-origin against the FastAPI server. In optional local Vite development, the dev server proxies that traffic to `http://127.0.0.1:8095`. If you override `VITE_API_BASE_URL`, keep it aligned with the backend host and port. If you bypass the Vite proxy and call the backend directly from a browser origin, configure your reverse proxy or deployment boundary accordingly.

For merged-runtime development, prefer `npm run dashboard:watch` so frontend file changes rebuild the backend-served bundle automatically without reintroducing a separate always-on browser entrypoint.

## Service Worker Caching

The service worker only caches the app shell, not API data, for security. If you add offline API caching, ensure no sensitive data is cached.

## Project Structure

- `app/main.py`: FastAPI entrypoint
- `app/routes.py`: API and HAL route handlers
- `app/services.py`: financial services, QuickBooks access, and rebuild helpers
- `app/data_pipeline.py`: import normalization, pull status, and cache recompute logic
- `app/hal/`: HAL orchestration, storage, chart planning, and accounting helpers
- `frontend/`: supported React SPA and Vite client

## Data Inputs

### QuickBooks CSV

Use exported reports such as:

- Profit and Loss by Month
- Deposit/Income report

Expected columns:

- `Date` or `Month`
- `Account` or `Account Name`
- `Amount`

### SoftDent CSV

Use read-only exports.

Expected columns:

- `Date` or `Month`
- `Metric` or `Measure`
- `Amount`
- `Provider`, `Category` optionally

## Financial Window And Refresh

- The program automatically uses a rolling 5-year financial window (`FINANCIAL_LOOKBACK_YEARS=5`).
- Financial cache is recomputed daily when the app is accessed (`FINANCIAL_DAILY_REFRESH_ENABLED=true`).
- Raw and KPI cache tables are rebuilt on refresh so storage does not grow endlessly from repeated daily recomputes.

Source report auto-pull runs before each recompute:

- `SOFTDENT_AUTO_PULL_ENABLED=true` with `SOFTDENT_SOURCE_DIR` (or `SOFTDENT_SENSEI_DATASYNC_ROOT`) copies supported SoftDent files into `SOFTDENT_IMPORT_DIR` before KPI recompute.
- `QUICKBOOKS_AUTO_PULL_ENABLED=true` with `QUICKBOOKS_SOURCE_DIR` copies supported QuickBooks CSV files into `QUICKBOOKS_IMPORT_DIR` before KPI recompute.
- `POST /softdent/import` and `POST /quickbooks/import` accept direct file uploads and write canonical import files into those same import directories.
- `POST /api/hal9000/staged-imports` writes approved `quickbooks_*.csv` review files into `AI_Workspace`; the next refresh syncs those staged files into the canonical QuickBooks import directory.
- Pull activity can be checked at `/api/reports/pull-status`, which now reports enabled state, summaries, scanned and copied counts, and the canonical files currently in use.

## Pandas Note

If you run this repo on Python 3.14 without Visual Studio build tools, pandas wheels may not be available. The analytics pipeline in this repo currently uses standard-library and optional spreadsheet parsers, so the supported KPI and reconciliation flows do not depend on pandas.

## Run Locally (Windows Server)

```powershell
cd C:\NewRidgeFamilyFinancial
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8095 --reload
```

Open: <http://127.0.0.1:8095>

## CI Test Command

Use this as the regular CI test command:

```powershell
python -m pytest app/tests -q
```

This now includes:

- A route-wiring smoke gate via `app/tests/test_ci_route_wiring.py`, which executes `scripts/smoke_all_routes.py` and fails CI automatically if any page/API wiring regresses.
- A focused ingest gate via `app/tests/test_ci_softdent_ingest_check.py`, which executes `scripts/focused_new_file_ingest_check.py` and fails CI if controlled new-file SoftDent ingest no longer changes pull counters and downstream KPI deltas as expected.

For low-noise structured diagnostics in CI logs, run:

```powershell
python scripts/run_ci_gates.py
```

This writes a JSON report to `scripts/ci_gate_report.json` (configurable with `--output`).

For a quick report-generation sanity check without executing the gate tests, use:

```powershell
python scripts/run_ci_gates.py --skip-gates --output scripts/ci_gate_report.quick.json
```

For a full rebuild receipt artifact (refresh + tests + gates), use:

```powershell
python scripts/write_rebuild_receipt.py --output scripts/rebuild_receipt.json
```

For a fast artifact-creation sanity check only:

```powershell
python scripts/write_rebuild_receipt.py --skip-steps --output scripts/rebuild_receipt.quick.json
```

## Key Pages

- `/` Dashboard
- `/softdent` SoftDent Analysis and import
- `/claims` Outstanding dental claims queue (daily refresh)
- `/accounts-receivable` All-accounts receivable view (daily refresh)
- `/quickbooks` QuickBooks Analysis and import
- `/reconciliation` Reconciliation table
- `/trends` Trend charts
- `/ebitda` EBITDA valuation page (daily estimate)
- `/hal9000` HAL 9000 dedicated question-and-monitoring console
- `/reports` Monthly and DSO-style summaries

## HAL 9000 Advisor Rules

- Uses only calculated KPI data.
- Does not invent numbers.
- Classifies findings as green/yellow/red.
- Returns direct practice-management recommendations.
- Applies all 15 HAL phases from New Ridge Portal in financial-only scope.

For the recommended PHI-safe local AI architecture and retrieval boundary for HAL, see `docs/hal_phi_rag_architecture.md`.
For the required authentication and audit controls before any real HAL model integration, see `docs/hal_auth_audit_plan.md`.
For dual-lane local quantized model setup on AMD Radeon (24B frontend / 30B backend, Ollama or llama.cpp), see `docs/local_quantized_ai_setup.md`.

HAL now uses a local Chroma-backed vector store for retrieval, loads credentials from `APP_AUTH_USERS_JSON`, and exposes a read-only admin audit endpoint at `/api/hal9000/audits`.

### HAL Runtime Posture Health Flag

`GET /api/hal9000/status` now includes `operating_picture.local_model_runtime_posture`.

- `cpu_fallback_active=true` indicates HAL is intentionally running local model inference in CPU fallback mode.
- `num_gpu_override` reports the active `OLLAMA_NUM_GPU_OVERRIDE` value when set.
- `posture_reason` reports whether posture came from env override or profile default.

### GPU Stability And WHEA Monitoring (Windows)

Use these scripts when PCIe corrected hardware warnings (WHEA ID 17) spike during local model work:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\apply_gpu_stability_mitigation.ps1
```

This disables PCIe Link State Power Management (ASPM) for the active power plan and writes `scripts/gpu_stability_mitigation_report.txt`.

One-shot WHEA root-port check with alert threshold:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\watch_whea_root_port.ps1 -WindowMinutes 5 -WarningThreshold 25
```

Continuous watch mode with file logging:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\watch_whea_root_port.ps1 -Continuous -PollSeconds 30 -WindowMinutes 5 -WarningThreshold 25 -OutputPath .\scripts\whea_watch_report.txt
```

## Security Notes

- Keep `.env` credentials out of source control.
- Do not expose the app to LAN unless explicitly changed.
- Keep all integrations read-only.
- Production-like deployments require `APP_AUTH_SESSION_SECRET` and `WIDGET_API_KEY`; see **Production environment checklist** above and `docs/API.md` **Security contracts**.
- Session cookies, if added later, should be `HttpOnly` and `Secure`; the browser app does not store auth tokens, API keys, or session IDs in `localStorage`.

### Content Security Policy

The backend sends a strict CSP by default with same-origin script loading, no object/embed content, and no framing. The app still allows `style-src 'unsafe-inline'` because the current React UI uses inline styles extensively. That exception is intentional and should be removed only after the UI is moved to CSS classes or CSS variables.

## SQLite, Telemetry, Redis, And Hardening

- SQLite remains the durable cache + analytics store (`SQLITE_PATH`) and now also stores request telemetry.
- Telemetry controls:

  - `TELEMETRY_ENABLED=true|false`
  - `TELEMETRY_MAX_ROWS=50000` (retention cap)

- Optional Redis runtime integration:

  - `REDIS_ENABLED=true|false`
  - `REDIS_URL=redis://127.0.0.1:6379/0`
  - Redis health is reported in `/api/health`.

- Hardened runtime controls:

  - `HARDENED_TRUSTED_HOSTS=127.0.0.1,localhost`
  - `HARDENED_SECURITY_HEADERS_ENABLED=true|false`
  - `HARDENED_HTTPS_REDIRECT=true|false`
  - `HARDENED_HSTS_ENABLED=true|false`

## SoftDent Read-Only Policy

- `SOFTDENT_READ_ONLY_MODE=true` blocks any mutation-style behavior by policy.
- `SOFTDENT_IMPORT_ONLY_MODE=true` limits SoftDent use to ingest and analysis.
- SoftDent reads are expected to come from canonical import files or explicit `SOFTDENT_*_EXPORT_PATH` overrides, not from repo-root or bridge-export fallbacks.
- Canonical SoftDent reads come from explicit `SOFTDENT_*_EXPORT_PATH` overrides or from files already landed in `SOFTDENT_IMPORT_DIR`.
- `SOFTDENT_SOURCE_DIR` and `SOFTDENT_SENSEI_DATASYNC_ROOT` are source locations for auto-pull before refresh, not fallback read roots.

## Browser-Native Frontend Architecture

The repository now includes a browser-native client in `frontend/` with this stack:

- IndexedDB via Dexie (`frontend/src/db.ts`) with typed tables, versioned schema, and CRUD helpers.
- TanStack Query (`frontend/src/queryClient.ts`) for server-state caching and query key discipline.
- Comlink (`frontend/src/workers/jsonWorker.ts` and `frontend/src/workers/jsonWorkerClient.ts`) for the KPI parsing worker.
- BroadcastChannel (`frontend/src/browser/crossTabSync.ts`) for cross-tab cache invalidation after browser-side writes and refreshes.
- Web Locks API (`frontend/src/browser/webLocks.ts`) around IndexedDB writes so multiple tabs do not run the same write-heavy job at once.
- Persistent storage requests (`frontend/src/browser/storagePersistence.ts`) so browser-managed cache data is less likely to be evicted.
- Zod validation for external API payloads (`frontend/src/api/schemas.ts`).
- Web Worker parsing for non-trivial payload validation/transforms (`frontend/src/workers/jsonWorker.ts`) with Comlink wrapping.
- A lightweight custom Service Worker app-shell cache (`frontend/public/sw.js`) for offline shell loading without caching API data.
- A web app manifest (`frontend/public/manifest.webmanifest`) so the browser shell can be installed without pretending full offline API support.

### Browser Update Strategy

- The service worker keeps app-shell caching only; API requests stay network-first.
- When a new service worker is installed and waiting, the app shows a `New version available` banner.
- Users can click `Refresh now` to activate the waiting worker (`skipWaiting`) and reload into the latest bundle.
- The app never silently traps users on stale code.

### Sync Conflict And Retry Rules

- KPI snapshot merge policy is `newest timestamp wins` for same-period rows.
- Local refresh retries are queued in IndexedDB (`syncQueue`) when admin refresh fails.
- Queued retries are attempted again when the browser comes back online on a stable connection.
- A manual `Retry queued actions` button is available in the admin dashboard as fallback.
- Conflict behavior and migration compatibility are covered in frontend tests.

### Diagnostics Panel

- Add `?diag=1` to `/app` or `/admin` to enable the developer diagnostics card.
- The panel reports app version, build date, browser info, IndexedDB availability, service worker status, storage persistence, estimated quota, database schema version, last sync time, and queued retry count.
- No secrets, tokens, or credentials are displayed.

### Release Safety Notes

- Browser-local data remains exportable through `Local Backup / Restore`; run a backup before major upgrades.
- IndexedDB schema evolution is versioned in `frontend/src/db.ts` and migration compatibility is tested.
- See `frontend/CHANGELOG.md` for release-facing browser-app changes.

### Migration Boundary

- Existing FastAPI backend still uses SQLite for server-side cache and reporting.
- Browser code does not use SQLite/Redis directly; local persistence is IndexedDB only.
- Redis/telemetry remain backend concerns and are isolated from browser state architecture.
- Workbox is not used yet because the current shell cache is small and the app does not need a broader precache pipeline.
- File System Access and Web Crypto are not added because the app does not yet have a real local file workflow or security need that justifies them.
- Browser API fallbacks are feature-detected in small modules so unsupported browsers can degrade gracefully instead of crashing.

### Frontend Commands

From `frontend/`:

```powershell
npm install
npm run lint
npm run typecheck
npm run test
npm run build
```

After building, FastAPI serves the browser app at:

- `/app`

If the bundle is missing, `/app` returns a setup page with build instructions and does not break other routes.
