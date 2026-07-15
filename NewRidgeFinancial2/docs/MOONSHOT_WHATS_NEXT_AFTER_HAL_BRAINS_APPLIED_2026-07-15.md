# Moonshot AI — What's Next After HAL Brains (APPLIED)

**Date:** 2026-07-15  
**Source:** `MOONSHOT_WHATS_NEXT_AFTER_HAL_BRAINS_2026-07-15.md`  
**Build:** `nr2-12018-hal-brains`  
**Operator:** approve  

## Package

Browser smoke + route-fix for HAL brains P0–P3 live viability.

## Root cause

Live process was still serving **`nr2-12017-optical-ops`** (stale Python process), so new `/api/hal/*` brains routes 404'd. Session POSTs without the loaded route hit mutation auth → 403. After restart, aggressive HAL rate limit (`5/min`) caused 429 during smoke. App-info read **`site/nr2-build.json`**, which still said 12017 while repo-root stamp was 12018.

## Fixes applied

1. **Restart** NR2 via `scripts/start_program.ps1 -Restart` → routes from `nr2_http_server.py` live.
2. **`nr2_rate_limit.py`** — HAL default `5` → `60`/min; exempt SoftDent/QB status beams, actions pending, browser-session, session history.
3. **`site/nr2-build.json`** — synced to `nr2-12018-hal-brains` so `/api/app-info` reports the correct stamp.
4. **`/api/hal/chat` stream** — SSL/wsgiref generator streaming caused Bottle critical 500 (also on legacy `/api/v1/hal/stream-sse`). Fixed by buffering SSE frames into a single `text/event-stream` string body; optical client still falls back to JSON multi-turn if needed.
5. **`nr2-optical-page-hal.js`** — SSE first, JSON fallback for chat resilience.

## Smoke results (https://127.0.0.1:8765)

| Check | Result |
|-------|--------|
| `assetVersion` / `schemaVersion` | `nr2-12018-hal-brains` |
| `GET /api/hal/tools/softdent-status` | 200 · `$7,714` live |
| `GET /api/hal/tools/qb-summary` | 200 · `$78,399` live |
| `POST /api/hal/session` | 200 · UUID |
| `POST /api/hal/chat` (stream:false) | 200 · `HAL brains online.` |
| `GET /api/hal/session/<id>/history` | 200 · turns persisted |
| `POST /api/hal/actions/propose` | 200 · consentRequired |
| `GET /api/hal/actions/pending` | 200 · pending action present |
| Session JSONL under `app_data/nr2/hal-sessions/` | present |
| Execute without consent | 403 consent_required |
| Execute with consent (qb_sync) | 200 |
| `POST /api/hal/chat` stream:true | 200 · `text/event-stream` buffered SSE tokens |

## Acceptance checklist

- [x] Live `POST /api/hal/session` returns 200 with UUID
- [x] Live `POST /api/hal/chat` multi-turn works (JSON + SSE)
- [x] SoftDent/QB tool GETs return live data (not 404)
- [x] Consent propose/pending/execute path works
- [x] Session files appear in `app_data/nr2/hal-sessions/`
- [x] Live app asset advances to `nr2-12018-hal-brains`

## Files touched

- `NewRidgeFinancial2/nr2_rate_limit.py`
- `NewRidgeFinancial2/site/nr2-build.json`
- `NewRidgeFinancial2/nr2_http_server.py` (buffered SSE for `/api/hal/chat`)
- `NewRidgeFinancial2/site/nr2-optical-page-hal.js` (SSE + JSON fallback)
- `NewRidgeFinancial2/docs/MOONSHOT_WHATS_NEXT_AFTER_HAL_BRAINS_APPLIED_2026-07-15.md` (this file)

## Note

Optical HAL page consent modal is client-side; API consent path is verified. Open `/nr2-optical-page-hal.html` in the browser after this restart to use the command center.
