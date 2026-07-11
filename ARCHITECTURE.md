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

## Local AI (HAL / Ollama)

Workstation default (**AMD Radeon AI PRO R9700 32 GB**, 2026-07-11):

| Item | Current |
|------|---------|
| Active model | `hal-local:24b` ← `mistral-small3.1:24b` **Q4_K_M**, `num_ctx` 8192 |
| GPU pin | Single model only · `OLLAMA_MAX_LOADED_MODELS=1` · `OLLAMA_NUM_PARALLEL=1` |
| Listener | `OLLAMA_HOST=127.0.0.1:11434` (prefer `Start-HAL-Ollama-Local.ps1`; avoid tray LAN bind) |
| Orchestrator lanes | `chat8b` / `reason21b` / `escalate30b` / `coder32b` resolve to the same 24B tag |
| Cloud | `cloudReasoning.enabled=false` unless explicitly enabled |
| Prior dual pin | `hal-chat:8b` + `hal-escalate:30b` retained on disk; not auto-routed |

**Evolution:** Early Program Manager plans used an 8B (fast) + 30B (deep) dual pin. That layout was replaced by one mid-size 24B for full GPU residency and VRAM headroom on the internal card. Lane IDs remain for routing policy; the model tag is unified.

**Future (not configured):** when an external ~12 GB GPU is installed, run a **separate 8B** on that card and keep **24B on the R9700** — do not reload dual models onto the 32 GB card alone.

Detail, validation, and rollback: `NewRidgeFinancial2/docs/HAL_LOCAL_24B_SINGLE_GPU_2026-07-11.md`  
Ops: `NewRidgeFinancial2/model-automation/README.md`

## CI/CD

- Python pytest for NR2 backend modules; frontend validators / smoke scripts under `NewRidgeFinancial2/scripts` and root `scripts/`.
- GitHub Actions under `.github/workflows/`.

## See Also

- `NewRidgeFinancial2/README.md`
- `NewRidgeFinancial2/docs/HAL_LOCAL_24B_SINGLE_GPU_2026-07-11.md`
- `docs/local_quantized_ai_setup.md`
- `docs/hal_phi_rag_architecture.md`
- `SECURITY_HEADERS.md`
