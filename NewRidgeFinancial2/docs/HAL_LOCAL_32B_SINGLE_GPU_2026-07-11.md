# HAL Local Single 32B on R9700 (2026-07-11)

## Exact model and quantization

| Item | Value |
|------|--------|
| HAL tag | `hal-local:32b` |
| Base | `qwen3:32b` |
| Quantization | **Q4_K_M** (Ollama default for tag) |
| Context | **8192** (conservative initial) |
| Keep-alive | `-1` (warmup pin) |
| Max loaded | **1** |
| Parallel requests | **1** |
| GPU | AMD Radeon AI PRO R9700 32 GB (HIP/ROCm; `OLLAMA_IGPU_ENABLE=0`) |
| Listener | `OLLAMA_HOST=127.0.0.1:11434` |

## Why 32B instead of 24B

- Prior pin `hal-local:24b` (`mistral-small3.1:24b` Q4_K_M) was stable (~15 GB) but left headroom unused.
- **Qwen3 32B Q4_K_M** (~19 GB) fits the R9700 with ≥5 GB margin at 8K and is the stronger general local driver for HAL diagnostics / accounting / code-review depth.
- Still **one** resident model — no dual-load thrashing.

## Hard 32B-only (2026-07-13)

Office program must not load or call any other AI model. See:

- `docs/HAL_APPLIED_32B_ONLY_2026-07-13.md`
- `model-automation\Enforce-HAL-32B-Only.ps1`

```powershell
powershell -ExecutionPolicy Bypass -File .\NewRidgeFinancial2\model-automation\Enforce-HAL-32B-Only.ps1
```

## Apply

```powershell
powershell -ExecutionPolicy Bypass -File .\NewRidgeFinancial2\model-automation\Apply-HAL-GPU-Performance.ps1
# Prefer loopback-only serve:
powershell -ExecutionPolicy Bypass -File .\NewRidgeFinancial2\model-automation\Start-HAL-Ollama-Local.ps1
```

## Rollback to 24B

```powershell
powershell -ExecutionPolicy Bypass -File .\NewRidgeFinancial2\model-automation\Install-HAL-GPU-Single-24B.ps1
git checkout -- NewRidgeFinancial2/site/data/hal-models.json NewRidgeFinancial2/nr2_hal_gateway.py NewRidgeFinancial2/integration_health.py
```

## Validate

```powershell
python .\NewRidgeFinancial2\scripts\validate_hal_local_32b.py
ollama ps   # expect only hal-local:32b, 100% GPU
```
