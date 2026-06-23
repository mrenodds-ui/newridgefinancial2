# New Ridge Financial Browser App — Frontend

React 18 + TypeScript + Vite SPA that caches dental practice KPIs in IndexedDB and syncs with the FastAPI backend. The primary runtime is the backend-served bundle at `http://127.0.0.1:8095/app`; the Vite dev server remains an optional frontend-only development surface.

See `ARCHITECTURE_HARDENING.md` for security rules, browser API fallbacks, and backup/restore strategy.

---

## Quick start

Primary merged runtime from the workspace root:

```bash
cd ..
npm install --prefix frontend
npm run dashboard:start
```

Open: `http://127.0.0.1:8095/app`

Automatic merged watch mode from the workspace root:

```bash
cd ..
npm run dashboard:watch
```

That keeps the FastAPI-served `/app` entrypoint and rebuilds the production bundle whenever frontend files change.

Optional frontend-only dev server in this folder:

```bash
# Install dependencies
npm install

# Start dev server (proxied to backend at :8096)
npm run dev

# Type-check without emitting
npm run typecheck

# Lint (Biome)
npm run lint

# Format source in-place
npm run format

# Lint + format check together
npm run check

# Run unit/integration tests (Vitest)
npm run test

# Build for production
npm run build

# Build and assert bundle size limits
npm run build:check

# Preview the production build locally
npm run preview
```

---

## Testing

- `npm run test` runs the Vitest unit and integration suite with fake-indexeddb, MSW, and axe.
- `npm run test:security` runs storage and sanitization guardrail checks.
- `npm run test:a11y` runs accessibility unit checks with axe.
- `npm run typecheck` runs the strict TypeScript compile check.
- `npm run smoke:playwright` runs Playwright smoke coverage against a live FastAPI server on port 8096.

Playwright requires the Python backend to be running (`uvicorn app.main:app --host 127.0.0.1 --port 8096`). The config in `playwright.config.ts` will start it automatically if it is not already running.

Optional API mocking in local development:

```bash
VITE_ENABLE_MSW=true npm run dev
```

When enabled, the app starts MSW browser handlers from `src/mocks/browser.ts`.

---

## Lint and formatting

This project uses **Biome** for both linting and formatting (replaces ESLint + Prettier).

```bash
npm run check          # lint + format check (no writes)
npm run check:ci       # same, exits non-zero on any issue (used in CI)
npm run lint           # lint only
npm run format         # format and write changes
```

Config lives in `biome.json` at the repo root of `frontend/`.

---

## Storage architecture

| Layer          | Technology           | Purpose                                                     |
| -------------- | -------------------- | ----------------------------------------------------------- |
| Server state   | TanStack Query       | Fetch, cache, and invalidate API responses                  |
| Local cache    | Dexie 4 (IndexedDB)  | Persist KPI snapshots, preferences, import jobs, sync queue |
| Worker parsing | Comlink + Web Worker | Parse large KPI JSON off the main thread                    |

### IndexedDB schema (v3)

- `kpiSnapshots` — PK: `period`. Newest `updatedAt` wins on conflict.
- `preferences` — PK: `key`. App-level settings (lastSyncAt, theme).
- `importJobs` — PK: `++id`. Audit log of sync operations.
- `syncQueue` — PK: `++id`. Queued mutations for offline retry.
- `kpiRecords` — PK: `id`. Local KPI record editing workflow.

---

## Browser-native API modules

All browser API usage is kept behind small modules in `src/browser/`.

- BroadcastChannel: `browser/crossTabSync.ts` for cross-tab invalidation and local update notifications without sensitive payloads.
- Web Locks: `browser/webLocks.ts` to prevent concurrent multi-tab write jobs such as IndexedDB writes and restore flows.
- Storage persistence: `browser/storagePersistence.ts` to request durable local storage when local data matters.
- File System Access API: `browser/fileAccess.ts` for backup export/import with graceful fallback to download/upload.
- Service worker cache: `public/sw.js` plus `offline/registerServiceWorker.ts` for app-shell caching and offline fallback for repeat loads.
- Web Worker + Comlink: `workers/jsonWorker.ts` plus `workers/jsonWorkerClient.ts` for off-main-thread KPI payload parsing.

Security baseline:

- No app secrets/tokens/session IDs are stored in localStorage or sessionStorage.
- CSP is enforced by backend security headers.
- If authenticated sessions are added later, use HttpOnly Secure SameSite cookies.

### Workbox evaluation

Workbox was evaluated and not added at this time. The current custom service worker already covers this app's needs:

- App shell asset caching
- Offline fallback behavior
- No caching of `/api/*` responses to avoid stale/sensitive server-state reuse

If routing/runtime caching rules become more complex later, Workbox can be introduced with `injectManifest` without changing app-level data flow.

---

## Offline behavior

The app registers `public/sw.js` as an app-shell service worker.

- **Network-first** strategy for all requests.
- Falls back to cached shell for non-API GETs when offline.
- `OfflineBanner` component shows a banner when `navigator.onLine` is false.
- Failed admin refreshes are queued in `syncQueue` and retried automatically when the connection returns.
- If the browser supports Background Sync, the app registers a retry sync tag and the service worker nudges clients to process queued mutations.
- A manual "Retry queued actions" button remains available as a fallback.
- A `ServiceWorkerUpdateBanner` prompts users to reload when a new version is waiting.

## Update strategy

- The app surfaces update availability with `ServiceWorkerUpdateBanner`.
- Clicking refresh activates the waiting worker via `SKIP_WAITING` and reloads on `controllerchange`.
- Users are not silently pinned to stale cached code.

---

## Routing

The app uses **TanStack Router** with explicit route ownership in `src/router.tsx` and shared path constants in `src/routingPaths.ts`.

Current routes:

- `/app` shows the KPI overview with IndexedDB and health-check status.
- `/admin` shows the SoftDent-fed financial dashboard.

Route search params are validated with Zod at the route layer to keep URL behavior predictable.

---

## Keyboard shortcuts

| Shortcut | Action                              | Page          |
| -------- | ----------------------------------- | ------------- |
| `Alt+R`  | Trigger admin refresh from SoftDent | `/admin` only |

---

## Forms

The local KPI editor uses **React Hook Form** paired with **Zod** validation:

- Component: `src/components/LocalKpiRecordManager.tsx`
- Schema: `src/kpiRecords.ts`

Validation errors are shown inline and save failures surface explicit error text.

---

## Storybook

```bash
npm run storybook          # dev server at :6006
npm run build:storybook    # build static storybook to storybook-static/
```

Stories live in `src/stories/`. The following components have stories:

- `DashboardCard` — four accent variants
- `LoadingSpinner`
- `EmptyState`
- `ServiceWorkerUpdateBanner`
- `OfflineBanner`

---

## Performance budgets

After every production build, run:

```bash
npm run build:check
```

Limits (uncompressed):

| Scope               | Limit  |
| ------------------- | ------ |
| Any single JS chunk | 500 KB |
| Any single CSS file | 100 KB |
| Total JS            | 650 KB |

Adjust limits in `scripts/check-bundle-size.mjs`.

---

## Lighthouse audits

With the app running (`npm run preview` or the full stack), run:

```bash
npm run lighthouse:local
```

This uses LHCI (`@lhci/cli`) with config from `.lighthouserc.json`. The command starts `vite preview` on port 5001, runs Lighthouse against `/app` and `/admin`, and prints scores.

Targets: Performance ≥ 80, Accessibility ≥ 90, Best Practices ≥ 80.

To run Lighthouse manually (Chrome DevTools → Lighthouse tab) open `http://127.0.0.1:5001/app`.

---

## Diagnostics panel

Append `?diag=1` to any URL to show the diagnostics card. It displays browser capabilities, storage quota, last sync time, and failed sync queue count.

---

## Deployment

1. `npm run build` — outputs to `dist/`
2. The FastAPI backend serves `dist/` as a static mount at `/app` and `/admin`.
3. The service worker scope is `/` (root), so both paths participate in update handling.

Build metadata (`__APP_VERSION__`, `__BUILD_DATE__`) is injected at compile time via `vite.config.ts`.

---

## CI

See `.github/workflows/frontend-ci.yml`. The pipeline runs: install → typecheck → biome check → unit tests → build → bundle size check → (optional) Playwright smoke.
