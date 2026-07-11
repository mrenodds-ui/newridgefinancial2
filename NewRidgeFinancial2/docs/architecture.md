# NR2 Architecture (pointer)

Canonical overview lives at the **repo root**:

- [`ARCHITECTURE.md`](../../ARCHITECTURE.md) — structure, data flow, security, **local AI (single 24B)**
- [`HAL_LOCAL_24B_SINGLE_GPU_2026-07-11.md`](./HAL_LOCAL_24B_SINGLE_GPU_2026-07-11.md) — model, VRAM, routing, tests, rollback, future external GPU
- [`../model-automation/README.md`](../model-automation/README.md) — Ollama pin / warmup ops
- [`../../docs/local_quantized_ai_setup.md`](../../docs/local_quantized_ai_setup.md) — quantized AI workstation notes

## Local AI snapshot (2026-07-11)

| | |
|--|--|
| Active | `hal-local:24b` (Q4_K_M) on R9700 only |
| Policy | One loaded model; loopback Ollama; OpenAI/cloud off by default |
| Lanes | Orchestrator lane ids kept; all map to the 24B tag |
| Next hardware | External ~12 GB GPU → optional separate 8B (not configured yet) |
