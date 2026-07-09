# HAL Model Warmup Automation

Keeps HAL's local Ollama models loaded in memory **always** — at logon, on a
short recurring interval, and independent of whether the NewRidgeFinancial 2.0
program is open or closed. Models are pinned with `keep_alive = -1`, so Ollama
holds them resident with no time-based eviction.

This stays inside HAL's read-only boundary: it only loads local models into
memory. It never writes to SoftDent, QuickBooks, payers, or any external service.

## What stays resident

The always-on default for **32 GB VRAM** (R9700) is chat + escalation GPU-pinned:

- `hal-chat:8b` (DeepSeek-R1 8B — staff chat)
- `hal-escalate:30b` (Qwen3 30B — escalation / second opinion, ctx 4096)

Install or refresh both tags:

```powershell
powershell -ExecutionPolicy Bypass -File .\NewRidgeFinancial2\model-automation\Apply-HAL-GPU-Performance.ps1
```

Or install lanes only:

```powershell
powershell -ExecutionPolicy Bypass -File .\NewRidgeFinancial2\model-automation\Install-HAL-GPU-Chat-Escalate-Lanes.ps1
```

**16 GB VRAM** workstations: use `Install-HAL-GPU-Dual-Lanes.ps1` (8B+14B) or
`Install-HAL-GPU-Chat-Lane.ps1 -UnpinHelper` (8B only).

Reasoning and escalation both use **GPU-pinned `hal-escalate:30b`** on R9700 (no Mistral 24B load — avoids evicting pins):

```powershell
powershell -ExecutionPolicy Bypass -File .\NewRidgeFinancial2\model-automation\Apply-HAL-GPU-Performance.ps1
```

Optional legacy 24B (16 GB workstations only — will evict pins on 32 GB):

```powershell
powershell -ExecutionPolicy Bypass -File .\NewRidgeFinancial2\model-automation\Install-HAL-Mistral-24B-Fast.ps1
```

The warmer reads `gpuPinnedModels` from `..\site\data\hal-models.json`, so pinned
tags stay in sync with the program config.

### GPU reality (32 GB R9700)

`hal-chat:8b` + `hal-escalate:30b` co-reside on GPU (~23 GB weights, ctx 3072/4096). `reason21b` and `escalate30b` both use `hal-escalate:30b`. `hal-helper:14b` loads on demand.

On **16 GB** VRAM, all configured models cannot co-reside on GPU at once. Legacy dual-lane
pins `hal-chat:8b` + `hal-helper:14b` (~14 GB). The 24B reasoning lane loads on demand
and may evict one GPU lane briefly while active.

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
