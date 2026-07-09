# Local LLM Benchmark (Ollama / vLLM)

Production-ready Python toolkit for **routing**, **chat**, and **benchmarking** local models on a 32 GB GPU workstation.

Targets:
- **Fast lane:** Llama 3 8B at **FP16** (16-bit)
- **Heavy lane:** **30B-class** model at **4-bit** quantization (`qwen3:30b` Q4_K_M)

Tested layout on AMD Radeon AI PRO R9700 (32 GB VRAM): both models can be loaded on GPU, but for benchmarking run them one at a time unless you intentionally co-pin them.

---

## 1. Prerequisites

- Windows 10/11 or Linux
- Python 3.10+
- [Ollama](https://ollama.com/download) **recommended on Windows + AMD**
- Optional: [vLLM](https://docs.vllm.ai/) on Linux/WSL with NVIDIA GPU

---

## 2. Python environment

```powershell
cd local-llm-benchmark
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

---

## 3. Ollama setup (recommended for this workstation)

### 3.1 Install and start Ollama

```powershell
# After installing Ollama from https://ollama.com/download
ollama serve
```

Default OpenAI-compatible endpoint: `http://127.0.0.1:11434/v1`

### 3.2 Pull / create the 8B FP16 model

Ollama's stock `llama3:8b` tag is quantized. For **full 16-bit (FP16)** weights, create a custom tag from an F16 GGUF:

```powershell
# Option A — create local FP16 tag from Modelfile (downloads F16 GGUF on first create)
ollama create llama3:8b-instruct-fp16 -f ollama/Modelfile.llama3-8b-fp16

# Option B — if you already have Meta's model via Ollama library, inspect quant first
ollama show llama3:8b
```

Expected VRAM when loaded: **~16 GB** at FP16 for 8B parameters.

### 3.3 Pull the 30B 4-bit model

```powershell
# Default Ollama pull serves Q4_K_M (~18 GB on disk / GPU)
ollama pull qwen3:30b

# Verify quantization
ollama show qwen3:30b | findstr /I "quantization parameter"
```

Alternative 30B-class tags: `qwen2.5:32b`, `llama3.3:70b` (70B will **not** fully fit 32 GB at 4-bit — stick to 30B class).

### 3.4 Optional — pin models across reboots

```powershell
# Pin 8B only (fast chat always hot)
$body = '{"model":"llama3:8b-instruct-fp16","keep_alive":-1}' 
Invoke-RestMethod -Uri http://127.0.0.1:11434/api/generate -Method Post -Body $body -ContentType application/json

# Pin 30B escalation lane (evicts other models if VRAM is tight)
$body = '{"model":"qwen3:30b","keep_alive":-1}'
Invoke-RestMethod -Uri http://127.0.0.1:11434/api/generate -Method Post -Body $body -ContentType application/json
```

---

## 4. vLLM setup (optional — Linux / WSL / NVIDIA)

vLLM does **not** target AMD Windows today. Use this path on NVIDIA Linux hosts.

```bash
pip install vllm

# Terminal 1 — 8B FP16/BF16
vllm serve meta-llama/Meta-Llama-3-8B-Instruct \
  --dtype float16 \
  --max-model-len 8192 \
  --port 8000

# Terminal 2 — 30B 4-bit (AWQ/GPTQ checkpoint)
# Example only; pick a 4-bit checkpoint that fits your GPU.
vllm serve Qwen/Qwen2.5-32B-Instruct-AWQ \
  --quantization awq \
  --max-model-len 8192 \
  --port 8001
```

Update `.env`:

```dotenv
LLM_BACKEND=vllm
LLM_BASE_URL=http://127.0.0.1:8000/v1
LLM_MODEL_FAST=meta-llama/Meta-Llama-3-8B-Instruct
LLM_MODEL_HEAVY=Qwen/Qwen2.5-32B-Instruct-AWQ
```

---

## 5. Verify server health

```powershell
python run.py health
```

Expected:

```text
ONLINE backend=ollama url=http://127.0.0.1:11434/api/version
version: 0.30.x
models:
  - llama3:8b-instruct-fp16
  - qwen3:30b
```

---

## 6. Run routed chat

```powershell
# Simple task -> 8B
python run.py chat "Summarize why local inference is useful for a dental back-office app."

# Complex task -> 30B
python run.py chat "Implement a Python function that reconciles deposit totals against a QuickBooks CSV export."
```

Inspect routing only:

```powershell
python run.py route "Classify these support tickets into billing vs clinical."
python run.py route "Debug this SQL query that double-counts adjustments."
```

---

## 7. Benchmark

Single prompt (auto-routed):

```powershell
python run.py bench "Summarize the benefits of on-prem LLM inference."
```

Full suite (8B, 30B, and routed runs):

```powershell
python run.py bench --suite --json
```

Metrics reported:
| Metric | Meaning |
|--------|---------|
| **TTFT (ms)** | Time to first token (latency) |
| **Gen (ms)** | Generation time after first token |
| **Total (ms)** | End-to-end request time |
| **Tok/s** | Output tokens per second during generation |

---

## 8. Routing rules

| Complexity | Examples | Model |
|------------|----------|-------|
| **Simple** | summarize, classify, extract, sentiment, short Q&A | `llama3:8b-instruct-fp16` |
| **Complex** | code, debug, algorithms, logic, architecture, long technical prompts | `qwen3:30b` |

Override in code via `route_prompt(..., force=TaskComplexity.COMPLEX)` or CLI `run.py chat --model qwen3:30b`.

---

## 9. Project layout

```text
local-llm-benchmark/
  run.py                      # CLI entry point
  config.yaml                 # defaults + routing keywords
  requirements.txt
  .env.example
  ollama/Modelfile.llama3-8b-fp16
  local_llm_benchmark/
    config.py                 # settings loader
    server.py                 # health checks / model presence
    router.py                 # simple vs complex routing
    client.py                 # OpenAI client + benchmark engine
```

---

## 10. Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Server is not reachable` | Start `ollama serve` or your vLLM process |
| `required model(s) are missing` | Run the pull/create commands in section 3 |
| Very slow first request | Model cold-start; rerun after warmup or pin with `keep_alive` |
| ROCm / GPU errors | Restart Ollama; ensure only intended models are pinned |
| FP16 8B + 30B OOM together | Benchmark one model at a time, or pin only the pair you need (~23 GB) |

---

## 11. Use as a library

```python
from dotenv import load_dotenv
from local_llm_benchmark.config import load_settings
from local_llm_benchmark.client import LocalLLMClient
from local_llm_benchmark.server import ensure_server_ready

load_dotenv()
settings = load_settings()
ensure_server_ready(settings)

client = LocalLLMClient(settings)
result = client.routed_benchmark("Write a Python merge sort and explain its complexity.")
print(result.ttft_ms, result.tokens_per_second, result.model)
```
