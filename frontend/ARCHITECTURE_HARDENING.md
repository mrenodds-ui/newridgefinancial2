# Update Handling, Sync, and Release Safety

## Update Handling

This app does **not** use a service worker or Workbox. All updates are live on reload. No offline/PWA caching is present, so users always get the latest code. No update notification is needed.

## Sync Conflict Handling

All data is local to the browser. There is no backend sync, so no conflict resolution is required. Local data is always the source of truth.

## Background Sync

No offline write or retry queue is implemented. All mutations are local and immediate. If offline writes are added in the future, background sync and a manual retry button should be implemented with feature detection.

## Passkeys / WebAuthn

No authentication is present. Passkeys and WebAuthn are not applicable. If authentication is added, prefer passkeys or secure backend-managed auth over storing tokens in localStorage.

## Trusted Types

All HTML sinks use a centralized sanitizer (`sanitizeHtml`). Trusted Types policy is feature-detected and paired with DOMPurify. No raw HTML rendering is scattered across components.

## Diagnostics Page

A diagnostics page is available at `/diagnostics` for debugging and support. It shows app version, build date, browser info, IndexedDB, service worker status, storage persistence, quota, DB schema version, last backup/export, and failed sync queue count. No secrets or user data are exposed.

## Release Safety

- [CHANGELOG.md](CHANGELOG.md) tracks all notable changes.
- Database migration is tested by opening old data after updates.
- Users are reminded to back up/export local data after major updates.

## Browser App Hardening Notes

## Storage choice

- Local user data is stored in IndexedDB through Dexie (`src/db.ts`).
- `localStorage` and `sessionStorage` are intentionally avoided for app data.
- A security regression test enforces this rule (`src/__tests__/securityPolicies.test.ts`).

## Caching strategy

- Server-state caching and invalidation uses TanStack Query (`src/queryClient.ts`).
- Local cache/state sync uses IndexedDB + BroadcastChannel topics (`src/browser/crossTabSync.ts`).
- Service worker does app-shell caching only and does not cache `/api/*` responses.

## Offline behavior

- `public/sw.js` handles shell caching and offline fallback for non-API requests.
- Failed admin refresh operations are queued locally and retried when online.
- When supported, the service worker triggers Background Sync (`newridge-admin-refresh-retry`) to request queued retry processing.
- When Background Sync is unavailable, retry still works through online-event detection plus a manual "Retry queued actions" button.
- `OfflineBanner` and update banners keep users informed of connectivity/update state.

## App update handling

- Service worker updates are never silently trapped; a visible "New version available" banner prompts user refresh.
- Refresh calls `SKIP_WAITING`, then `controllerchange` reloads into the newest shell.
- This keeps users on current code while preserving explicit user control over when activation happens.

## Worker usage

- Large KPI payload parsing runs in a Web Worker with Comlink (`src/workers/jsonWorker.ts`).
- App behavior stays functional even when worker-heavy operations are not needed.

## Security rules

- Backend sends hardened response headers including CSP (`app/main.py`).
- CSP defaults to enforcement and can be switched to report-only mode with `hardened_csp_report_only=true`.
- Current CSP exception: `style-src 'unsafe-inline'` remains because current UI uses inline React style attributes.
- No secrets, API keys, auth/session tokens, or sensitive IDs are stored in `localStorage`/`sessionStorage`.
- If authenticated sessions are introduced, use backend-issued HttpOnly Secure SameSite cookies instead of browser storage.

## Authentication evaluation

- Current app surface has no login flow and no token/session handling in the browser app.
- Passkeys/WebAuthn are not implemented here because there is no auth module yet.
- If auth is added later, prefer backend-managed passkeys or secure cookie sessions; do not store auth secrets in browser storage.

## Trusted Types evaluation

- Current UI does not use `innerHTML`/`dangerouslySetInnerHTML` paths.
- A centralized sanitizer (`src/security/sanitizeHtml.ts`) is present for imported/pasted HTML scenarios.
- Trusted Types policy is deferred until actual HTML rendering sinks are introduced to avoid unnecessary platform complexity.

## Browser API fallbacks

- IndexedDB: app shows diagnostics and degrades gracefully when unsupported.
- File System Access API: backup export/import falls back to download/upload flows.
- Web Locks: code path falls back to normal execution when lock manager is absent.
- BroadcastChannel: sync events become local-only when unsupported.
- Service Worker: app remains functional without offline enhancement.
- Web Workers: availability is surfaced in diagnostics.
- Storage persistence (`StorageManager.persist`): requested opportunistically and reported in diagnostics.
- OPFS availability is feature-detected and shown in diagnostics.

## Backup/import/export strategy

- Browser backups are versioned JSON (`version: 1`) via `src/browser/browserBackup.ts`.
- Import payloads are validated with Zod before any IndexedDB writes.
- Restore operations use a lock + transaction and trigger cross-tab invalidation.

## API mocking for dev/tests

- Unit/integration tests use MSW node server (`src/mocks/server.ts`).
- Optional browser-side MSW can be enabled in local dev with `VITE_ENABLE_MSW=true`.
- Use realistic but minimal handlers in `src/mocks/handlers.ts`.
