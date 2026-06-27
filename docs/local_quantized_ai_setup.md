# Local Quantized AI (AMD Radeon RX 9060 XT 16GB)

This repo routes **frontend-facing** HAL interactions through a **14B** model and **backend/HAL server** review through the same **14B** tag on a separate port. The browser never loads models directly; React calls backend HAL APIs, which call local model runtimes.

## Runtime selection

| Check | Result on this workstation |
| --- | --- |
| ROCm (`rocminfo`, `rocm-smi`) | Not installed / not on PATH (Windows) |
| Vulkan (`vulkaninfo`) | Available |
| Preferred stack | **Ollama with Vulkan** (already integrated) |
| Fallback | **llama.cpp** server with Vulkan (`AI_RUNTIME=llama_cpp`) |

ROCm is not assumed on Windows. Do not add CUDA-only tooling. This repo targets AMD Radeon on Windows with **Vulkan-first Ollama**; use **llama.cpp + Vulkan** when Ollama is unavailable. ROCm is optional on Linux only when cleanly supported for your GPU.

## Local-only artifacts (never commit)

Quantized model weights and runtime outputs stay on the workstation only:

- Write outputs to `models/` or `.local_models/` (both gitignored).
- Never commit `.gguf`, `.safetensors`, `.bin`, `.pth`, `.pt`, or Ollama/model caches.
- Override output location with `MODEL_OUTPUT_DIR` when running quantize scripts.

## Architecture

```text
Frontend UI -> POST /api/hal9000, /api/hal9000/second-opinion, /api/hal9000/document-rag/ask -> backend HAL
  -> AI_FRONTEND_BASE_URL (:11434) -> qwen3:14b (Q4_K_M, ctx 3072)

Backend HAL server tasks (journal draft parser, coder profile, second-opinion lane)
  -> POST /api/hal9000/second-opinion uses chat_second_opinion on AI_BACKEND_BASE_URL (:11435) -> qwen3:14b

Optional LiteLLM proxy (:4000)
  -> hal-chat-balanced / hal-vision -> OLLAMA_FRONTEND_BASE_URL (:11434) -> qwen3:14b
  -> hal-coding / hal-second-opinion / hal-analysis -> OLLAMA_BACKEND_BASE_URL (:11435) -> qwen3:14b
  -> qwen3:235b evaluator (:11436) is isolated workflow only; no normal LiteLLM alias uses it

Optional experimental fast structured reviewer (opt-in profile `fast_review` only)
  -> AI_FAST_REVIEW_BASE_URL (:11437) -> qwen3-coder:30b (Ollama default)
  -> not wired into user-facing narrative generation or second-opinion defaults yet
  -> explicit checker: POST /api/hal9000/fast-review-check (hal:operator, not in OpenAPI schema)
```

Configuration is centralized in `app/ai_local_config.py` and `evals/local_model_profiles.json`.

## Security defaults

| Surface | Development / test (`APP_ENV=development` or `test`) | Production-like (`APP_ENV` unset, `production`, `staging`, or other) |
| --- | --- | --- |
| `/api/widgets/update` | Localhost fallback allowed without `WIDGET_API_KEY` | `WIDGET_API_KEY` required |
| Session cookies | `APP_AUTH_SESSION_SECRET` optional (dev-only fallback exists) | `APP_AUTH_SESSION_SECRET` required at startup |
| LiteLLM proxy (`:4000`) | Localhost-only; `LITELLM_MASTER_KEY` optional with startup warning | Set `LITELLM_MASTER_KEY`; do not expose the proxy without auth |

`scripts/start_litellm_proxy.ps1` warns when `LITELLM_MASTER_KEY` is unset. Bind the proxy to `127.0.0.1` unless you intentionally expose it on a shared network.

Full API security contracts and the README production checklist are in `docs/API.md` and `README.md`.

## Environment

Copy `.env.example` to `.env` and adjust:

```dotenv
AI_RUNTIME=ollama
AI_GPU_BACKEND=vulkan
AI_FRONTEND_BASE_URL=http://127.0.0.1:11434
AI_BACKEND_BASE_URL=http://127.0.0.1:11435
AI_FRONTEND_MODEL=qwen3:14b
AI_BACKEND_MODEL=qwen3:14b
AI_FRONTEND_QUANT=Q4_K_M
AI_BACKEND_QUANT=Q4_K_M
AI_CONTEXT_SIZE=3072
AI_FRONTEND_CONTEXT_SIZE=3072
AI_BACKEND_CONTEXT_SIZE=3072
HAL_ENABLE_FAST_MODEL=1
HAL_FAST_MODEL_NAME=qwen3:14b
HAL_FAST_MODEL_TIMEOUT_SECONDS=10
HAL_MAIN_MODEL_TIMEOUT_SECONDS=15
```

Model weights, `.gguf` files, and caches belong under `.local_models/` or `models/` (gitignored).

## Configuration overrides

All lane settings are env-driven (`app/ai_local_config.py` reads `.env`); do not hardcode paths in source.

| Variable | Purpose |
| --- | --- |
| `AI_RUNTIME` | `ollama` (default) or `llama_cpp` |
| `AI_GPU_BACKEND` | `vulkan` (Windows AMD default) or `rocm` when available |
| `AI_GPU_LAYERS` | `auto`, `cpu`, or explicit layer count for partial offload |
| `AI_FRONTEND_BASE_URL` / `AI_BACKEND_BASE_URL` | OpenAI-compatible or Ollama base URLs (ports default `:11434` / `:11435`) |
| `OLLAMA_FRONTEND_BASE_URL` / `OLLAMA_BACKEND_BASE_URL` | LiteLLM proxy lane URLs (should match the `AI_*` values above) |
| `OLLAMA_EVALUATOR_BASE_URL` | Isolated 235B evaluator on `:11436` only; not used by normal HAL or LiteLLM aliases |
| `AI_FAST_REVIEW_BASE_URL` / `OLLAMA_FAST_REVIEW_BASE_URL` | **Experimental** fast structured reviewer on `:11437` (`fast_review` profile only; opt-in) |
| `AI_FAST_REVIEW_MODEL` / `OLLAMA_FAST_REVIEW_MODEL` | Fast reviewer model tag. **Ollama default:** `qwen3-coder:30b`. The GGUF name `Qwen3-Coder-30B-A3B-Instruct` is not in the Ollama registry; use your exact local tag or a custom Ollama import / `llama.cpp` GGUF path. |
| `AI_FRONTEND_MODEL` / `AI_BACKEND_MODEL` | Ollama model tags or LiteLLM aliases (`qwen3:14b`) |
| `OLLAMA_FRONTEND_MODEL` / `OLLAMA_BACKEND_MODEL` | Optional model-tag overrides used by run scripts when `AI_*_MODEL` is unset |
| `AI_FRONTEND_MODEL_PATH` / `AI_BACKEND_MODEL_PATH` | Local GGUF paths for `llama_cpp` |
| `AI_CONTEXT_SIZE` | Shared default context (3072 recommended on 16GB for daily 14B lanes) |
| `AI_FRONTEND_CONTEXT_SIZE` / `AI_BACKEND_CONTEXT_SIZE` | Per-lane context override |
| `AI_FRONTEND_QUANT` / `AI_BACKEND_QUANT` | Target GGUF quant labels (`Q4_K_M`, `Q4_K_S`, etc.) |
| `AI_PORT` / `AI_HOST` | Run-script listen port and host |
| `AI_MODEL_PATH` | Run-script GGUF path shortcut |
| `MODEL_OUTPUT_DIR` | Quantize-script output directory |

## Quantize (llama.cpp path)

Requires `llama-quantize` on PATH. Source can be HuggingFace directory or an existing `.gguf`.

```bash
./scripts/quantize_frontend_24b.sh /path/to/mistral-small-24b Q4_K_M
./scripts/quantize_backend_30b.sh /path/to/qwen3-30b Q4_K_S
```

Fallback quants are attempted automatically if the primary quant fails.

Outputs are written to `.local_models/` by default (gitignored, local-only — do not commit).

## Experimental fast structured reviewer (`:11437`)

**Status: experimental and opt-in.** This lane does **not** replace the production backend default (`qwen3:14b` on `:11435`) or `POST /api/hal9000/second-opinion`.

Use the `fast_review` profile when you want a faster structured checker for:

- insurance narrative fact-checking
- missing-data detection
- citation/source compliance checks
- contradiction checks
- structured JSON review output

It is **not** the default narrative writer. Benchmark structured review quality against `qwen3:14b` before promoting it.

| Item | Value |
| --- | --- |
| Profile alias | `fast_review` |
| Default port | `127.0.0.1:11437` |
| Default Ollama model | `qwen3-coder:30b` |
| GGUF reference name | `Qwen3-Coder-30B-A3B-Instruct` (use when serving a local GGUF; not an Ollama registry tag) |
| Config | `AI_FAST_REVIEW_*` or `OLLAMA_FAST_REVIEW_*` in `.env` |
| Opt-in checker API | `POST /api/hal9000/fast-review-check` (`hal:operator`; hidden from OpenAPI schema) |

**Operational rules**

1. Start only when needed; normal HAL chat, coder, and second-opinion routes never call `:11437` unless code explicitly targets `fast_review`.
2. Do **not** run `:11437` at the same time as the isolated 235B evaluator (`:11436` / `qwen3:235b`).
3. Override `AI_FAST_REVIEW_MODEL` when your local Ollama tag or custom GGUF import differs.

Start the lane (Ollama example):

```powershell
$env:AI_PORT = '11437'
$env:AI_FAST_REVIEW_MODEL = 'qwen3-coder:30b'  # supported Ollama default
$env:OLLAMA_HOST = '127.0.0.1:11437'
ollama serve
# Health check: curl http://127.0.0.1:11437/v1/models
```

### Opt-in checker workflow (`POST /api/hal9000/fast-review-check`)

Explicit structured review only — does **not** replace `POST /api/hal9000/second-opinion` or narrative generation.

Request body:

```json
{
  "source_text": "de-identified packet text...",
  "review_task": "insurance_narrative_review",
  "packet_id": "optional-label"
}
```

Response `review` object keys when `status` is `ok`:

```json
{
  "missing_data": [],
  "citation_issues": [],
  "possible_invented_facts": [],
  "contradictions": [],
  "recommended_action": "...",
  "ready_for_human_review": true
}
```

If the `fast_review` lane is down, `status` is `lane_unavailable` with an explicit error — the checker does **not** fall back to `chat_second_opinion` or cloud models.

Python entry point: `app.hal.fast_review_checker.run_fast_review_check(...)`.

Resolve the lane in Python/tests via `app.ai_local_config.resolve_profile_base_url("fast_review")`.

### Bakeoff harness (`scripts/run_fast_review_bakeoff.py`)

Compare the experimental reviewer against the current backend default on **de-identified** insurance
narrative review packets. This is manual and local-only; it does not run in CI and does not change
any route or user-facing behavior.

```bash
python scripts/run_fast_review_bakeoff.py \
  --packets evals/insurance_narrative_packets \
  --profiles chat_second_opinion fast_review \
  --out fast_review_bakeoff_report.json
```

- Packets live in `evals/insurance_narrative_packets/` and contain **no PHI** (enforced by
  `app/tests/test_fast_review_bakeoff.py`).
- Each profile resolves to its lane via `app.ai_local_config`; the harness never uses the `:11436`
  evaluator lane and never falls back to cloud models.
- A down lane is recorded as `lane_unavailable`, not a pass/fail success.
- Per packet/profile it records: latency, output length, JSON/structured parse, missing-data
  detection, citation/source compliance, invented-fact warning count, model, and base URL.
- The default report `fast_review_bakeoff_report.json` is gitignored.
- Use `--dry-run` to resolve lanes and check health without calling models.

Benchmark `fast_review` against `qwen3:14b` here before considering it for any real workflow. Do
**not** run the bakeoff at the same time as the isolated 235B evaluator.

## Run model servers

Both lanes must be running for backend tasks (journal AI parser, coder profile, LiteLLM backend aliases). HAL `/api/hal9000/status` and `/control/runtime` report frontend and backend lane health separately.

`run_frontend_model.ps1` and `run_backend_model.ps1` are **long-running foreground processes**. They call `ollama serve` (or `llama-server`) and block until you stop them.

1. **Keep the terminal open** while you need that lane. Closing the window or stopping the PowerShell task takes the lane down.
2. **Stopping the backend script stops `:11435`.** Stopping the frontend script stops `:11434` (when it is the process bound to that port).
3. For continuous use, run each lane in a **dedicated terminal**, or wrap the script in a Windows service, scheduled task, or process manager (NSSM, pm2, etc.).
4. Check lane health:

```powershell
curl http://127.0.0.1:11434/v1/models
curl http://127.0.0.1:11435/v1/models
```

### Ollama (recommended)

Terminal 1 — frontend 14B chat:

```powershell
$env:AI_PORT = '11434'
.\scripts\run_frontend_model.ps1
# Default tag: qwen3:14b (override with AI_FRONTEND_MODEL)
# or: ollama pull qwen3:14b with default Ollama on :11434
```

Terminal 2 — backend 14B review on a second port:

```powershell
$env:AI_PORT = '11435'
.\scripts\run_backend_model.ps1
# Default tag: qwen3:14b (override with AI_BACKEND_MODEL)
# or: $env:OLLAMA_HOST='127.0.0.1:11435'; ollama serve
```

### llama.cpp (Vulkan fallback)

```bash
AI_MODEL_PATH=.local_models/frontend/frontend-24b.Q4_K_M.gguf \
AI_PORT=11434 AI_RUNTIME=llama_cpp AI_GPU_BACKEND=vulkan \
./scripts/run_frontend_model.sh
# Default tag: qwen3:14b (override with AI_FRONTEND_MODEL)

AI_MODEL_PATH=.local_models/backend/backend-30b.Q4_K_S.gguf \
AI_PORT=11435 AI_RUNTIME=llama_cpp AI_GPU_LAYERS=0 \
./scripts/run_backend_model.sh
# Default tag: qwen3:14b (override with AI_BACKEND_MODEL)
```

## 235B evaluator workflow (isolated, one section at a time)

Do **not** run the 14B frontend lane or 14B backend lane while the 235B evaluator is active. Resource contention on 16GB VRAM makes multi-lane 235B runs unreliable.

| Step | Action |
| --- | --- |
| 1 | Ensure tracked git tree is clean (or pass `-AllowDirtyRepo` intentionally). |
| 2 | Stop normal lanes: `scripts/stop_normal_model_lanes.ps1` |
| 3 | Verify `:11434` and `:11435` do not respond to `/v1/models`. |
| 4 | Start only the evaluator on `:11436` (foreground `ollama serve` in a dedicated terminal, or `scripts/start_235b_evaluator_lane.ps1`). |
| 5 | Run **one** section: `scripts/run_235b_isolated_section.ps1 -Section N` |
| 6 | Save **one** report (`235b_sectionN_*_report.md` at repo root). Root-level `235b_*` reports, context files, raw JSON, and legacy eval runners are gitignored by default—do not commit unless explicitly sanitized and approved. |
| 7 | Tear down `:11436` only: `scripts/stop_235b_evaluator_lane.ps1` kills the LISTENING serve PID (not client connections). It does **not** block on `ollama stop qwen3:235b`. Exits 0 immediately if `:11436` is already down. |
| 8 | Restart 14B lanes only if needed: `-RestartNormalLanes` on the orchestrator, or start `run_frontend_model.ps1` / `run_backend_model.ps1` manually. |

Orchestrator (single section, lane checks, optional report overwrite):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_235b_isolated_section.ps1 -Section 2
```

Python runner (called by the orchestrator; use `--isolated` when normal lanes must be down):

```powershell
.\.venv\Scripts\python.exe .\run_235b_eval_section.py 2 --isolated
```

Optional `-ForceStopOllamaApp` on `stop_normal_model_lanes.ps1` (or on `run_235b_isolated_section.ps1`, which forwards the switch) stops the Windows Ollama tray when it keeps respawning `:11434`. It is **off by default** because it can affect unrelated Ollama use.

## App

```powershell
cp .env.example .env
# edit AI_* URLs and model names
uvicorn app.main:app --reload
```

## Manual smoke test

```powershell
curl http://127.0.0.1:11434/v1/models
curl http://127.0.0.1:11435/v1/models
curl http://127.0.0.1:11434/api/tags
curl http://127.0.0.1:11435/api/tags
```

Tiny completion (low temperature, few tokens):

```powershell
curl http://127.0.0.1:11434/api/generate -d '{"model":"qwen3:14b","prompt":"Say OK","stream":false,"options":{"temperature":0,"num_predict":8}}'
```

## VRAM notes

- **24B Q4_K_M** at **4096 ctx** is the target full-GPU daily lane on 16GB VRAM.
- **30B Q4_K_S** is sized for backend work; default `num_gpu=0` avoids fighting the frontend model for VRAM.
- Raising context above **8192** on either lane increases KV-cache pressure quickly.
- Use `AI_GPU_LAYERS=auto` or an explicit integer for partial offload experiments.
