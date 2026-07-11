# HAL Local Single 24B on R9700 (2026-07-11)

## Exact model and quantization

| Item | Value |
|------|--------|
| HAL tag | `hal-local:24b` |
| Base | `mistral-small3.1:24b` (verified via `ollama show`) |
| Quantization | **Q4_K_M** |
| Context | **8192** (conservative initial) |
| Keep-alive | `-1` (warmup pin) |
| Max loaded | **1** |
| Parallel requests | **1** |
| GPU | AMD Radeon AI PRO R9700 32 GB (HIP/ROCm; `OLLAMA_IGPU_ENABLE=0`) |
| Listener | `OLLAMA_HOST=127.0.0.1:11434` |

## Why 24B instead of 8B or 30B

- **8B** is fast but weaker for accounting / diagnostic / code-review depth on a 32 GB card that can hold a mid-size model alone.
- **30B** (prior dual-pin with 8B) forced `OLLAMA_MAX_LOADED_MODELS=2` and ~23 GB resident; adding coder on demand caused thrashing.
- **24B Q4_K_M** (~15 GB weights) fits entirely on the internal 32 GB GPU with **≥5–6 GB VRAM headroom** at 8K context, without needing an external GPU.

Q5_K_M was not selected: Q4_K_M already meets the stability/headroom preference.

## Expected VRAM budget

| Component | Estimate |
|-----------|----------|
| Weights (Q4_K_M) | ~15 GB |
| KV / runtime @ 8K | ~1–3 GB |
| **Total resident** | **~15–18 GB** |
| **Free on 32 GB** | **~14–17 GB** (safety margin ≥5 GB) |

## Routing policy (unchanged category scope)

- Lanes already approved for local inference (`chat8b`, `reason21b`, `escalate30b`, `coder32b`) all resolve to **`hal-local:24b`**.
- Lane **ids** are preserved; model tags changed only.
- **OpenAI / cloudReasoning remains disabled** (`enabled: false`) — not flipped on.
- PHI, clinical, financial, and raw-source routing permissions are **unchanged**.
- No new categories were granted local inference.
- Prior `hal-chat:8b`, `hal-escalate:30b`, and `qwen2.5-coder:32b` files are **retained on disk** but not auto-routed.

## Apply

```powershell
powershell -ExecutionPolicy Bypass -File .\NewRidgeFinancial2\model-automation\Apply-HAL-GPU-Performance.ps1
# Prefer loopback-only serve (do not rely on Ollama tray app):
powershell -ExecutionPolicy Bypass -File .\NewRidgeFinancial2\model-automation\Start-HAL-Ollama-Local.ps1
```

## Test results (2026-07-11)

| Check | Result |
|-------|--------|
| GPU detect | AMD Radeon AI PRO R9700 · ROCm gfx1201 · HIP index **0** · Intel iGPU dropped |
| `ollama ps` | `hal-local:24b` only · **15 GB** · **100% GPU** · ctx **8192** · Forever |
| `/api/ps` | `size` = `size_vram` = 15 935 964 446 · **CPU offload 0%** · Q4_K_M |
| VRAM | used **14.84 GiB** / 32 · avail **17.16 GiB** (≥5 GiB margin) |
| Listener | **127.0.0.1:11434 only** (via `Start-HAL-Ollama-Local.ps1`; tray app can rebind 0.0.0.0 — avoid it) |
| Prompt suite | simple / accounting / diagnostic / summarization / code-review — **all pass** |
| Median tok/s | **~7.8** (simple spike ~15) |
| First-token | ~0.18–1.2 s (warm) |
| System RAM | ~127 GB total · ~55 GB free during test (not model-backed) |
| Cloud | `cloudReasoning.enabled=false` unchanged |
| Stability 30m | **PASS** — 31 samples, 0 failures, 0 crashes/timeouts (`stability-30m-20260711.json`) |

Artifacts: `docs/hal-local-24b-test-results/pass-20260711-142508.json`

## Rollback (one command)

```powershell
powershell -ExecutionPolicy Bypass -File .\NewRidgeFinancial2\model-automation\Rollback-HAL-Dual-8B-30B.ps1
```

Then restore config from git if needed:

```powershell
git checkout -- NewRidgeFinancial2/site/data/hal-models.json NewRidgeFinancial2/nr2_hal_gateway.py
```

Snapshot: `model-automation/rollback-snapshots/pre-single-24b-env.json`

## Limitations

- Coder quality may be lower than dedicated `qwen2.5-coder:32b` while that second model is intentionally not loaded.
- Vision weights may ship with the base 24B tag; Modelfile does not enable speculative/experimental options.
- 8K context only until measured headroom supports raising `num_ctx`.
- Success is **not** “model created” — residency, performance, stability, and safety gates must pass.

## Future: external 12 GB GPU

Plan (not configured): attach an external 12 GB AMD/NVIDIA GPU and run a **separate 8B** staff-chat model there while keeping **24B on the internal R9700**. That requires a second Ollama/runtime visibility policy and must not re-enable concurrent dual-load on the 32 GB card alone.
