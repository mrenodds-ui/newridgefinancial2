# Local Quantized AI (AMD Radeon RX 9060 XT 16GB)

This repo routes **frontend-facing** HAL interactions through a **24B** model and **backend/HAL server** tasks through a **30B** model. The browser never loads models directly; React calls backend HAL APIs, which call local model runtimes.

## Runtime selection

| Check | Result on this workstation |
| --- | --- |
| ROCm (`rocminfo`, `rocm-smi`) | Not installed / not on PATH (Windows) |
| Vulkan (`vulkaninfo`) | Available |
| Preferred stack | **Ollama with Vulkan** (already integrated) |
| Fallback | **llama.cpp** server with Vulkan (`AI_RUNTIME=llama_cpp`) |

ROCm is not assumed on Windows. Do not add CUDA-only tooling.

## Architecture

```text
Frontend UI -> POST /api/hal9000, /api/hal9000/document-rag/ask -> backend HAL
  -> AI_FRONTEND_BASE_URL (:11434) -> mistral-small3.1:24b (Q4_K_M, ctx 4096)

Backend HAL server tasks (journal draft parser, coder profile, second-opinion lane)
  -> AI_BACKEND_BASE_URL (:11435) -> qwen3:30b (Q4_K_S, ctx 4096, CPU/RAM by default)

Optional LiteLLM proxy (:4000)
  -> hal-chat-balanced / hal-vision -> frontend Ollama
  -> hal-coding / hal-second-opinion / hal-analysis -> backend Ollama
```

Configuration is centralized in `app/ai_local_config.py` and `evals/local_model_profiles.json`.

## Environment

Copy `.env.example` to `.env` and adjust:

```dotenv
AI_RUNTIME=ollama
AI_GPU_BACKEND=vulkan
AI_FRONTEND_BASE_URL=http://127.0.0.1:11434
AI_BACKEND_BASE_URL=http://127.0.0.1:11435
AI_FRONTEND_MODEL=mistral-small3.1:24b
AI_BACKEND_MODEL=qwen3:30b
AI_FRONTEND_QUANT=Q4_K_M
AI_BACKEND_QUANT=Q4_K_S
AI_CONTEXT_SIZE=4096
```

Model weights, `.gguf` files, and caches belong under `.local_models/` or `models/` (gitignored).

## Quantize (llama.cpp path)

Requires `llama-quantize` on PATH. Source can be HuggingFace directory or an existing `.gguf`.

```bash
./scripts/quantize_frontend_24b.sh /path/to/mistral-small-24b Q4_K_M
./scripts/quantize_backend_30b.sh /path/to/qwen3-30b Q4_K_S
```

Fallback quants are attempted automatically if the primary quant fails.

## Run model servers

### Ollama (recommended)

Terminal 1 — frontend 24B:

```powershell
$env:AI_PORT = '11434'
.\scripts\run_frontend_model.ps1
# or: ollama pull mistral-small3.1:24b with default Ollama on :11434
```

Terminal 2 — backend 30B on a second port:

```powershell
$env:AI_PORT = '11435'
.\scripts\run_backend_model.ps1
# or: $env:OLLAMA_HOST='127.0.0.1:11435'; ollama serve
```

### llama.cpp (Vulkan fallback)

```bash
AI_MODEL_PATH=.local_models/frontend/frontend-24b.Q4_K_M.gguf \
AI_PORT=11434 AI_RUNTIME=llama_cpp AI_GPU_BACKEND=vulkan \
./scripts/run_frontend_model.sh

AI_MODEL_PATH=.local_models/backend/backend-30b.Q4_K_S.gguf \
AI_PORT=11435 AI_RUNTIME=llama_cpp AI_GPU_LAYERS=0 \
./scripts/run_backend_model.sh
```

## App

```powershell
cp .env.example .env
# edit AI_* URLs and model names
uvicorn app.main:app --reload
```

## Manual smoke test

```powershell
curl http://127.0.0.1:11434/api/tags
curl http://127.0.0.1:11435/api/tags
```

Tiny completion (low temperature, few tokens):

```powershell
curl http://127.0.0.1:11434/api/generate -d '{"model":"mistral-small3.1:24b","prompt":"Say OK","stream":false,"options":{"temperature":0,"num_predict":8}}'
```

## VRAM notes

- **24B Q4_K_M** at **4096 ctx** is the target full-GPU daily lane on 16GB VRAM.
- **30B Q4_K_S** is sized for backend work; default `num_gpu=0` avoids fighting the frontend model for VRAM.
- Raising context above **8192** on either lane increases KV-cache pressure quickly.
- Use `AI_GPU_LAYERS=auto` or an explicit integer for partial offload experiments.
