# HAL Model Warmup Automation

Keeps HAL's local Ollama models loaded in memory **always** — at logon, on a
short recurring interval, and independent of whether the NewRidgeFinancial 2.0
program is open or closed. Models are pinned with `keep_alive = -1`, so Ollama
holds them resident with no time-based eviction.

This stays inside HAL's read-only boundary: it only loads local models into
memory. It never writes to SoftDent, QuickBooks, payers, or any external service.

## What stays resident

The always-on default is the dual GPU lane layout for 16 GB VRAM:

- `hal-chat:8b` (DeepSeek-R1 8B — staff chat)
- `hal-helper:14b` (Queen3 14B — helper / triage)

Install or refresh both tags:

```powershell
powershell -ExecutionPolicy Bypass -File .\NewRidgeFinancial2\model-automation\Install-HAL-GPU-Dual-Lanes.ps1
```

Reasoning uses `mistral-small3.1:24b-fast` on demand (not dual-resident with 8B+14B):

```powershell
powershell -ExecutionPolicy Bypass -File .\NewRidgeFinancial2\model-automation\Install-HAL-Mistral-24B-Fast.ps1
```

Speed-first single-lane layout (8B only pinned — more VRAM headroom):

```powershell
powershell -ExecutionPolicy Bypass -File .\NewRidgeFinancial2\model-automation\Install-HAL-GPU-Chat-Lane.ps1 -UnpinHelper
```

Then set `fastModel.enabled` to `false` in `site/data/hal-models.json`.

The model names are read live from `..\site\data\hal-models.json`, so they stay
in sync with the program config.

### GPU reality (16 GB)

All configured models **cannot** co-reside on a 16 GB GPU at once. The default
pins only `hal-chat:8b` + `hal-helper:14b` (~14 GB weights with capped context).
The 24B reasoning lane loads on demand and may evict one of the GPU lanes
briefly while active.

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
