# Architecture Overview

## Structure

- `app/` — FastAPI backend, HAL services, import/report APIs, and Python tests
- `frontend/` — Active React SPA frontend for the supported browser experience
- `scripts/` — Utility, rebuild, and CI scripts

## Data Flow

1. Data is ingested by the FastAPI backend from SoftDent/QuickBooks exports and local rebuild scripts.
2. The backend exposes authenticated APIs for dashboard, HAL, admin, and reporting workflows.
3. The active `frontend/` SPA consumes those APIs and maintains browser-local caches where appropriate.

## Modernization & Scalability

- Backend and SPA are decoupled enough to evolve independently.
- Browser caching and worker-based parsing in `frontend/` reduce UI latency without changing backend ownership.

## Security

- Backend authentication and server-side integrations live in `app/`.
- HTTPS/HSTS are enforced in production via reverse proxy and backend security headers.

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

- Backend pytest and frontend type/test/build checks are the supported validation paths.
- Automated deploy pipeline; see `.github/workflows/`.

## Containerization

- Deployment docs should be read as a split stack: FastAPI backend plus the active `frontend/` SPA.

## See Also

- `NewRidgeFinancial2/README.md`
- `NewRidgeFinancial2/docs/HAL_LOCAL_24B_SINGLE_GPU_2026-07-11.md`
- `docs/local_quantized_ai_setup.md`
- `docs/hal_phi_rag_architecture.md`
- `SECURITY_HEADERS.md`
