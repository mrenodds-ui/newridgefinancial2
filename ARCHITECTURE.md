# Architecture Overview

## Structure

- `NewRidgeFinancial2/` — active NR2 Apex Bridge program (Bottle loopback on `127.0.0.1:8765`, vanilla JS site)
- `NewRidgeFinancial2/site/` — Apex UI (`index.html`, `apex-*.js`) plus HAL/workstation helpers
- `scripts/` — launchers, Moonshot consult runners, build bump, CI helpers
- Root `docs/` — architecture, PHI/RAG, SoftDent, and compliance notes

## Data Flow

1. SoftDent / QuickBooks exports are read (direct-first) into NR2 import/cache layers and SQLite (`local_store.py` / desktop bridge).
2. The loopback API (`/api/apex/...`, HAL evaluate routes) serves widget mosaics and program actions to the browser.
3. The Apex client paints mosaics from the API and keeps a **stale-while-revalidate IndexedDB cache** (`site/indexeddb-store.js`) for faster reloads and offline fallback of non-detail pages.
4. Durable program state prefers **SQLite** via the desktop/loopback bridge; browser fallback is IndexedDB, then `sessionStorage`.

## Client storage (IndexedDB)

| Layer | Role |
|-------|------|
| SQLite (loopback / pywebview) | Canonical local persistence when the NR2 server is up |
| IndexedDB (`nr2-apex`) | Apex widget mosaic cache (24h TTL); non-chat key/value fallback |
| sessionStorage | Ephemeral UI state; chat/transcript keys that must not be durable in the browser |

PHI rule: model transcripts / chat history are **not** written to IndexedDB (session-only denylist in `indexeddb-store.js`). Detail views with an `id` query are not cached.

## Security

- Loopback-only bind (`127.0.0.1`); session tokens on mutating API calls.
- HTTPS/HSTS via local TLS when enabled by the launcher.
- See `docs/hal_phi_rag_architecture.md` and `SECURITY_HEADERS.md`.

## CI/CD

- Python pytest for NR2 backend modules; frontend validators / smoke scripts under `NewRidgeFinancial2/scripts` and root `scripts/`.
- GitHub Actions under `.github/workflows/`.

## See Also

- `NewRidgeFinancial2/README.md`
- `docs/hal_phi_rag_architecture.md`
- `SECURITY_HEADERS.md`
