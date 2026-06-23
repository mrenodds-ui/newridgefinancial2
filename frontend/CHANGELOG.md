# Changelog

## Unreleased

- Added a web app manifest and install metadata for the browser shell.
- Added a service worker update banner so users can refresh into the newest cached shell.
- Added a developer-only diagnostics panel with browser, storage, service worker, and local sync status.
- Documented the update strategy and local backup/recovery flow.
- Added migration-compatibility coverage for IndexedDB data.
- Added optional Background Sync registration for queued admin-refresh retries with online/manual fallbacks.
- Added a dedicated background sync helper test suite.
- Added a local backup reminder in the backup/restore UI.
