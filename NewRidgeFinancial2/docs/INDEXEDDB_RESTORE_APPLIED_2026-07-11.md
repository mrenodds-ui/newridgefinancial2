# IndexedDB client cache — Applied

**Date:** 2026-07-11  
**Build:** **hal-10471**  
**Status:** Applied (restore IndexedDB + docs)

## What shipped

### IndexedDB module
`site/indexeddb-store.js` — vanilla key/value store (`nr2-apex` / `kv`):
- Apex widget mosaic cache (24h TTL; skips pages with `id` query)
- Session-only denylist for chat/transcript/evidence keys (PHI retention)

### Apex stale-while-revalidate
`apex-core.js` `loadPage`:
1. Paint IndexedDB cache immediately on cold navigation
2. Fetch `/api/apex/widgets/...` and replace
3. On network failure, fall back to IndexedDB if available

### DesktopBridge fallback
`desktop-bridge.js` browser fallback order: IndexedDB → `sessionStorage` (chat keys stay session-only).

### Readiness
`app.js` / `hal-core.js` report `storageMode: indexedDB` when SQLite is offline but IndexedDB works.

### Docs
- `ARCHITECTURE.md` — NR2 + IndexedDB layers
- `docs/hal_phi_rag_architecture.md` — accurate runtime + PHI rules
- `NewRidgeFinancial2/README.md` — file list

## Files

| File | Change |
|------|--------|
| `site/indexeddb-store.js` | **New** |
| `site/apex-core.js` | Widget cache paint/save |
| `site/desktop-bridge.js` | IndexedDB storage fallback |
| `site/app.js` / `site/hal-core.js` | Readiness storage modes |
| `site/index.html` / `sw.js` / `nr2-build.json` | **hal-10471** |
| `site/workstation/index.html` | Load `indexeddb-store.js` |
| `ARCHITECTURE.md`, PHI RAG doc, NR2 README | Docs |

## Validate

1. Restart Start Program  
2. Open Financial → confirm mosaic loads  
3. DevTools → Application → IndexedDB → `nr2-apex` → `kv` has `widgets:financial:`  
4. Hard-refresh: mosaic should paint from cache before network settles  
5. Ask HAL chat — confirm transcripts are **not** written under IndexedDB keys matching `*chatHistory*`
