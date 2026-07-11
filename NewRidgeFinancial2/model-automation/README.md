# HAL Model Warmup Automation

Keeps HAL's local Ollama model loaded in memory **always** — at logon, on a
short recurring interval, and independent of whether the NewRidgeFinancial 2.0
program is open or closed. Models are pinned with `keep_alive = -1`, so Ollama
holds them resident with no time-based eviction.

This stays inside HAL's read-only boundary: it only loads local models into
memory. It never writes to SoftDent, QuickBooks, payers, or any external service.

## What stays resident

The always-on default for **32 GB VRAM** (R9700) is the **single 24B** layout
(2026-07-11):

- `hal-local:24b` (FROM `mistral-small3.1:24b` **Q4_K_M**, `num_ctx` 8192) — GPU-pinned
- `OLLAMA_MAX_LOADED_MODELS=1` — no automatic concurrent 8B/30B/coder loads
- Prior `hal-chat:8b`, `hal-escalate:30b`, `qwen2.5-coder:32b` **retained on disk** only

Install or refresh:

```powershell
powershell -ExecutionPolicy Bypass -File .\NewRidgeFinancial2\model-automation\Apply-HAL-GPU-Performance.ps1
```

Rollback to dual 8B+30B:

```powershell
powershell -ExecutionPolicy Bypass -File .\NewRidgeFinancial2\model-automation\Rollback-HAL-Dual-8B-30B.ps1
```

See `docs/HAL_LOCAL_24B_SINGLE_GPU_2026-07-11.md` for VRAM budget, routing policy, and validation.

**16 GB VRAM** workstations: use `Install-HAL-GPU-Dual-Lanes.ps1` (8B+14B) or
`Install-HAL-GPU-Chat-Lane.ps1 -UnpinHelper` (8B only).

```powershell
powershell -ExecutionPolicy Bypass -File .\NewRidgeFinancial2\model-automation\Apply-HAL-GPU-Performance.ps1
```

Optional legacy text-only 24B-fast (not the active single-24B pin):

```powershell
powershell -ExecutionPolicy Bypass -File .\NewRidgeFinancial2\model-automation\Install-HAL-Mistral-24B-Fast.ps1
```

The warmer reads `gpuPinnedModels` from `..\site\data\hal-models.json`, so pinned
tags stay in sync with the program config.

### GPU reality (32 GB R9700)

**Single 24B (2026-07-11):** one Q4_K_M 24B resident (~15–18 GB @ 8K). No dual pin.
Future: external 12 GB GPU may host a separate 8B without reloading two models on the internal card.
Never pin `qwen3:235b` or `gpt-oss:120b` on 32 GB.

On **16 GB** VRAM, all configured models cannot co-reside on GPU at once. Legacy dual-lane
pins `hal-chat:8b` + `hal-helper:14b` (~14 GB).

## Run once

```powershell
powershell -ExecutionPolicy Bypass -File .\NewRidgeFinancial2\model-automation\Keep-HAL-Models-Warm.ps1
```

## Watch continuously (foreground)

```powershell
powershell -ExecutionPolicy Bypass -File .\NewRidgeFinancial2\model-automation\Keep-HAL-Models-Warm.ps1 -Watch
```

## Register automation (recommended)

```powershell
powershell -ExecutionPolicy Bypass -File .\NewRidgeFinancial2\model-automation\Register-HAL-Model-Automation.ps1
```

This installs two things, no Administrator required:

- Scheduled task **`New Ridge HAL Model Warmup`** — runs every 3 minutes in your
  session, re-warming the models so they recover automatically after any
  eviction, Ollama restart, or reboot.
- A logon launcher in your **Startup folder** — warms the models the moment you
  log on.

The warmer also starts `ollama serve` if the API is not already reachable.

### Options

- `-IncludeReasoningLanes` — also pin `mistral-small3.1:24b-fast` and `qwen3:30b`.
  These will not co-reside with both GPU lanes on 16 GB; expect on-demand swapping.
- `-AllConfigured` — attempt to pin every model in the config (not advisable on
  16 GB VRAM; provided for larger GPUs).
- `-SystemBoot` — register a pre-logon boot task that runs as SYSTEM at machine
  startup. **Requires an elevated (Administrator) PowerShell.**

For the system boot task, you can also run:

```powershell
.\NewRidgeFinancial2\model-automation\Install-HAL-Model-SystemBoot-Task.cmd
```

This opens an Administrator PowerShell prompt and registers
`New Ridge HAL Model Warmup (System Boot)`.

## Verify

```powershell
schtasks /Query /TN "New Ridge HAL Model Warmup" /FO LIST
Invoke-RestMethod -Uri http://127.0.0.1:11434/api/ps | Select-Object -ExpandProperty models
```

A resident model shows an `expires_at` far in the future (year 2318) instead of
a few minutes out.

## Remove

```powershell
schtasks /Delete /TN "New Ridge HAL Model Warmup" /F
Remove-Item "$([Environment]::GetFolderPath('Startup'))\NewRidge-HAL-Model-Warmup.cmd"
# If you registered the boot task (elevated):
schtasks /Delete /TN "New Ridge HAL Model Warmup (System Boot)" /F
```
