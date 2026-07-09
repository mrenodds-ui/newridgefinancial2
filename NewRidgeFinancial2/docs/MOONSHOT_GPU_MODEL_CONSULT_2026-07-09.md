# Moonshot GPU Model Consult

**Date:** 2026-07-09  
**Model:** kimi-k2.5 via OPENROUTER_API_KEY/process @ https://api.moonshot.ai/v1/chat/completions  
**GPU:** AMD Radeon AI PRO R9700 · 32 GB VRAM · ROCm  
**Status:** OPERATOR VALIDATED — hybrid applied 2026-07-09  
**Applied layout:** GPU pin `hal-chat:8b` + `hal-escalate:30b`; on-demand `qwen2.5-coder:32b` for agent/programming (`preferCoderForAgentLoop`)  

---

# Verdict
Your R9700 32 GB configuration can sustain dual-resident GPU pins without thrashing, but the **second pin** should differ based on whether you prioritize staff chat speed (keep Qwen3-30B) or agent programming depth (swap to Qwen2.5-Coder-32B). DeepSeek-R1 8B is optimal for the chat lane but carries ROCm compatibility risk on gfx1201—validate before promoting to production.

**Operator choice (hybrid):** Keep Best Experience pins for staff speed; route Greatest Program (coder-32B) on demand for agent loops only.

## 1. Recommended Always-On GPU Pin Layout (what stays resident)

**Best Experience Layout (Current—Validated)**
- `hal-chat:8b` (DeepSeek-R1 8B) — GPU 0, ~5.5 GB weights
- `hal-escalate:30b` (Qwen3 30B) — GPU 0, ~18–19 GB weights  
- *Headroom: ~6–8 GB for KV cache and working buffers*

**Greatest Program Layout (Proposed—Validate First)**
- `hal-chat:8b` (DeepSeek-R1 8B) — GPU 0, ~5.5 GB weights  
- `qwen2.5-coder:32b` (Qwen2.5-Coder 32B) — GPU 0, ~19–20 GB weights  
- *Headroom: ~5–7 GB; tighter fit but superior tool-use/agent-loop accuracy*

*Constraint:* `OLLAMA_MAX_LOADED_MODELS=2` enforces exactly two resident models. Any third model (helper, deep research) forces an unload of one pin.

## 2. Role Map (chat / helper / reasoning / escalation / coder / deep)

| Lane | Best Experience Model | Greatest Program Model | Trigger |
|------|----------------------|------------------------|---------|
| **chat** | `hal-chat:8b` | `hal-chat:8b` | General staff questions, SoftDent lookups, QuickBooks read-only queries |
| **escalation** | `hal-escalate:30b` | `qwen2.5-coder:32b` | Insurance denials, complex accounting logic, multi-step reasoning |
| **reasoning** | `hal-escalate:30b` | `qwen2.5-coder:32b` | Agent loop tool synthesis, `agentProgramming` profile tasks |
| **coder** | `hal-escalate:30b` (general) | `qwen2.5-coder:32b` | `apply_program_patch`, `run_hal_validation`, code review |
| **helper** | *On-demand* `hal-helper:14b` | *On-demand* `qwen3:14b` | Fast fallback if chat model evicted; not GPU-pinned |
| **deep** | *On-demand* `mistral-small3.1:24b-fast` | *On-demand* `mistral-small3.1:24b-fast` | Heavy clinical narrative drafting (swaps out the 30B/32B pin temporarily) |

## 3. Quantization & Context Budget (Q4/Q5/Q8, num_ctx, keep_alive)

**Quantization Strategy**
- **Q4_K_M** for all resident models (default Ollama pull). Do not use Q8 on 32B+ models; it pushes VRAM >32 GB when combined with 8B chat.
- **Q4_0** acceptable for `hal-chat:8b` if VRAM headroom needed, but K_M preferred for accuracy.

**Context Allocation**
```
hal-chat:8b:      num_ctx=3072,  keep_alive=-1  (resident)
hal-escalate:30b: num_ctx=4096,  keep_alive=-1  (resident—Experience layout)
qwen2.5-coder:32b:num_ctx=4096,  keep_alive=-1  (resident—Program layout)
```
- **P0:** Do not exceed `num_ctx=6144` on the 30B/32B model while `hal-chat:8b` is pinned; risk of OOM during peak agent loops.
- **P1:** If running deep research (`mistral-small3.1:24b`), drop its context to `num_ctx=2048` to enable temporary dual-load without eviction, or accept unload of the chat model.

## 4. What To Drop Or Keep On-Demand Only

**Keep On-Demand (Never Pin)**
- `qwen3:235b`, `gpt-oss:120b` — Exceeds 32 GB VRAM alone; drop from inventory.
- `deepseek-r1:14b` — Load only when `hal-escalate:30b` insufficient for reasoning; swaps out the 30B slot.
- `mistral-small3.1:24b` (non-fast) — Redundant with 30B pin; use only for specific clinical benchmarks.
- `hal-helper:14b` — Legacy lane; superseded by 8B chat for speed and 30B for depth.
- `qwen3-coder:30b` — Duplicate capability with `qwen2.5-coder:32b`; choose one coder model only.

**Drop Entirely (External Recommendation)**
- `llama3.3:latest` — Generalist model; inferior to Qwen3-30B on insurance/financial reasoning per your codebase routing logic.

## 5. Best Experience Config (speed + quality for staff HAL chat)

**Resident Pair**
```json
"gpuPinnedModels": ["hal-chat:8b", "hal-escalate:30b"]
```

**Parameters**
- `hal-chat:8b`: `temperature=0.2`, `top_p=0.9`, `num_predict=1536`, `repeat_penalty=1.05`
- `hal-escalate:30b`: `temperature=0.2`, `top_p=0.92`, `num_predict=1280`, `repeat_penalty=1.08`

**Rationale**
- DeepSeek-R1 8B provides lowest-latency token generation for routine staff chat (~40–60 t/s on R9700).
- Qwen3 30B maintains high accuracy on dental insurance escalations without the tool-use overhead of Coder models.

## 6. Greatest Program Config (max capability without thrashing VRAM)

**Resident Pair**
```json
"gpuPinnedModels": ["hal-chat:8b", "qwen2.5-coder:32b"]
```

**Parameters**
- `hal-chat:8b`: Unchanged (fast chat front-end).
- `qwen2.5-coder:32b`: `temperature=0.25`, `num_ctx=4096`, `num_predict=1536`  
  - *Note:* Increase `num_predict` to allow longer code patches in single generation.

**Rationale**
- Qwen2.5-Coder-32B outperforms Qwen3-30B on `agentToolLoop`, `apply_program_patch`, and multi-file source edits (Cursor-style gather).
- Accepts slightly higher VRAM pressure (~1–2 GB) for reduced fallback to cloud or on-demand models during autonomous ops.

**Safety Valve**
If VRAM thrashing detected (Ollama logs show `offloading to CPU` or model eviction), immediately revert to **Best Experience** layout.

## 7. Concrete Ollama Tags & Modelfile Changes

**Pull Commands (Validate before pinning)**
```powershell
# Experience layout (current)
ollama pull deepseek-r1:8b
ollama pull qwen3:30b

# Program layout (proposed)
ollama pull qwen2.5-coder:32b
```

**Modelfile Updates**

*For `hal-chat:8b` (unchanged except context cap)*
```dockerfile
FROM deepseek-r1:8b
PARAMETER temperature 0.2
PARAMETER num_ctx 3072
PARAMETER num_predict 1536
SYSTEM """You are HAL... [existing system prompt]"""
```

*For `hal-escalate:30b` (Experience)*
```dockerfile
FROM qwen3:30b
PARAMETER temperature 0.2
PARAMETER num_ctx 4096
PARAMETER repeat_penalty 1.08
```

*For `qwen2.5-coder:32b` (Program—new Modelfile)*
```dockerfile
# NewRidgeFinancial2/model-automation/Modelfile.hal-coder-32b
FROM qwen2.5-coder:32b
PARAMETER temperature 0.25
PARAMETER top_p 0.9
PARAMETER num_ctx 4096
PARAMETER num_predict 1536
PARAMETER repeat_penalty 1.05
SYSTEM """You are HAL escalation for NewRidgeFinancial 2.0 — agent programming and complex reasoning.
Prefer tool use and code synthesis for accounting/insurance automation.
Answer clearly from context. Never fabricate import data.
Structure: direct answer first, verified basis second, safe next staff action third.
You are read-only: no submit, email, fax, upload, post, delete, or external delivery."""
```

**JSON Config Update (`hal-models.json`)**
```json
"escalationModel": {
  "model": "qwen2.5-coder:32b",  // Change from hal-escalate:30b for Program config
  "options": {"num_ctx": 4096}
},
"reasoningModel": {
  "model": "qwen2.5-coder:32b"   // Share same instance
}
```

## 8. Risks On AMD ROCm / R9700

**P0 — Critical**
- **gfx1201 Support:** Ollama 0.31.1 ships with ROCm 6.1+ support, but gfx1201 (Radeon AI PRO R9700) is bleeding-edge. DeepSeek-R1 8B may encounter **graph execution failures** or **infinite hangs** on long contexts (>2048 tokens) due to flash-attention kernel mismatches.
- **DeepSeek-R1 Specific:** R1 models use custom MLA attention; ROCm path less tested than CUDA. Monitor `ollama serve` logs for `hipError` or `GEMM` failures.

**P1 — Performance**
- **VRAM Fragmentation:** 32B + 8B at Q4 approaches the 32 GB limit. Windows WDDM overhead may reduce available VRAM by 5–10%. If `hipOutOfMemory` errors appear, reduce `num_ctx` on the 32B model to 3072.
- **Context Switching Latency:** Unloading `qwen2.5-coder:32b` to load `mistral-small3.1:24b` (deep research) takes 8–12 seconds on R9700—acceptable for escalation lane but not for chat.

**P2 — Compatibility**
- **Mistral Small 3.1:** Requires Ollama 0.31.0+; verify `mistral-small3.1:24b-fast` runs without `invalid architecture` errors on gfx1201 before deploying.

## Prioritized Apply Order (steps operator can validate before changing code)

**P0 — Validation (Do Not Skip)**
1. **Verify ROCm Stability:** Run `ollama run deepseek-r1:8b` and submit a 2000-token context query. Check Windows Event Viewer for AMD driver crashes or Ollama stderr for `hipError`.
2. **Baseline VRAM:** With current pins loaded, run `ollama ps` and confirm `hal-chat:8b` + `hal-escalate:30b` show `100% GPU` and no CPU offload.
3. **Test Candidate Model:** Execute `ollama pull qwen2.5-coder:32b` and `ollama run qwen2.5-coder:32b`. Verify it loads without evicting existing models (temporarily stop NewRidge program to test).

**P1 — Staged Deployment**
4. **Create Modelfile:** Save `Modelfile.hal-coder-32b` (section 7) to `D:\LocalAI\ActiveModels\`.
5. **Build Custom Tag:** `ollama create hal-coder:32b -f Modelfile.hal-coder-32b`
6. **JSON Backup:** Copy `hal-models.json` to `hal-models.json.bak` before editing.
7. **Config Swap:** Update `gpuPinnedModels` and `escalationModel` entries to reference `hal-coder:32b` (or `qwen2.5-coder:32b` directly).

**P2 — Monitoring**
8. **Warmup Test:** Run `Keep-HAL-Models-Warm.ps1 -Watch` and verify both models show `expires_at: 2318...` (resident).
9. **Agent Loop Stress:** Trigger a `spawn_investigation` + `apply_program_patch` sequence in HAL. Monitor VRAM usage in Task Manager; should stay below 31 GB.
10. **Rollback Ready:** If thrashing detected, restore `hal-models.json.bak` and restart Ollama service to revert to Experience layout.

**Operator Checkpoint:** Confirm P0 validation complete before proceeding to P1. Do not modify `hal-models.json` until candidate model runs error-free on gfx1201.