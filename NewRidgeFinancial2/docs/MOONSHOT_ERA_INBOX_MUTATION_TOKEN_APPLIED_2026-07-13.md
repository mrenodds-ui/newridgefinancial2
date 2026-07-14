# Moonshot UI Mutation-Token Wiring for ERA Inbox Ingest — APPLIED (hal-10574)

**Date:** 2026-07-13  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_ERA_FIRST_DROP_OPS_2026-07-13.md`  
**Operator:** proceed  
**Build:** **hal-10574**

## Package (verbatim intent)

Wire the browser mutation-token path so staff can trigger ERA inbox ingest from the Apex UI without a raw POST 403, while real payer 835 files remain pending. Empty ≠ $0; no SoftDent write-back.

## What shipped

| Area | Change |
|------|--------|
| `nr2_browser_security.py` | `era_inbox_mutation_contract()`, `request_mutation_token_if_bound()`, ERA status on system-status prefixes |
| `apex_era835_pack.py` | `era_inbox_status()` always exposes CSRF contract (`mutationAuthRequired`, ingest URL, CLI fallback) |
| `apex_backend.py` | Status GET merges live token when bound; BUILD_ID **hal-10574**; ingest POST stamps `writeBack=false` |
| `apex_softdent_hardening_pack.py` | Gap tile exposes `eraInboxIngestUrl` / **Refresh Inbox** label |
| `site/apex-core.js` | Status widget renders **Refresh Inbox**; `apexFetch` POST with `X-NR2-Session-Token` |
| `nr2_hal_gateway.py` | Local policy for “refresh era inbox” / “awaiting first 835” |
| Cache stamps | `site/index.html`, `nr2-build.json`, `sw.js` → hal-10574 |
| Tests | `test_era_inbox_mutation_token_hal10574.py` |
| CLI fallback | unchanged: `scripts/run_era_inbox_ingest_ops.py` |

## Acceptance criteria

- [x] Mutation contract permits POST `/api/apex/hal/era-inbox/ingest` from same-origin UI session (`X-NR2-Session-Token`)
- [x] Status/ingest handlers + gap tile expose Refresh Inbox action
- [x] `site/apex-core.js` acquires token via `apexFetch` / `/api/app-info` and POSTs ingest
- [x] Empty inbox ingest returns `ok`, `honesty=empty_not_zero`, `writeBack=false` (no invented $)
- [x] Staff can trigger without running Python CLI (CLI remains valid fallback)
- [x] No SoftDent Register re-export; no synthetic 835 as production truth

## Not done (runner-ups — do not deviate)

- Third OPS procurement of real ERA-835 files (still blocked on clearinghouse drop)
- Collections Excel-temp / QB payroll/AP OPS

## Browser smoke

Completed on proceed after ship — see `MOONSHOT_ERA_INBOX_MUTATION_TOKEN_BROWSER_SMOKE_2026-07-12.md`  
(Refresh Inbox UI click → POST 200 with session token; empty honesty preserved).

## Live verify

After `browser_app.py` restart on **hal-10574** (2026-07-13):

| Gate | Result |
|------|--------|
| `GET /api/apex/hal/era-inbox/status` | **PASS** — `buildId=hal-10574`, `mutationAuthRequired=true`, `honesty=empty_not_zero` |
| `GET /api/app-info` → session token | **PASS** — token length 32 |
| `POST …/era-inbox/ingest` **without** token | **PASS** — **403** `browser_mutation_forbidden` / `token_invalid` |
| `POST …/era-inbox/ingest` **with** `X-NR2-Session-Token` | **PASS** — **200**, `empty=true`, `honesty=empty_not_zero`, `writeBack=false`, `ingested=[]` |
| Unit tests `test_era_inbox_mutation_token_hal10574` (+ 10572/10573) | **20 OK** |

Collections Gap tile **Refresh Inbox** ships via widget spec + `apex-core.js`; hard-refresh dashboard to pick up cache-bust `?v=hal-10574`.
