# HAL Model Warmup Automation

Keeps HAL's local Ollama models loaded in memory **always** — at logon, on a
short recurring interval, and independent of whether the NewRidgeFinancial 2.0
program is open or closed. Models are pinned with `keep_alive = -1`, so Ollama
holds them resident with no time-based eviction.

This stays inside HAL's read-only boundary: it only loads local models into
memory. It never writes to SoftDent, QuickBooks, payers, or any external service.

## What stays resident

The always-on default is the shared 24B model the program's active chat and
helper lanes use:

- `mistral-small3.1:24b-fast` (text-only Q4_K_S — chat / general / helper)

To build or refresh the fast quant:

```powershell
powershell -ExecutionPolicy Bypass -File .\Install-HAL-Mistral-24B-Fast.ps1
```

The legacy vision-inclusive `mistral-small3.1:24b` remains in inventory but is not the default lane.

The model names are read live from `..\site\data\hal-models.json`, so they stay
in sync with the program config.

### GPU reality (16 GB)

All configured models **cannot** co-reside on a 16 GB GPU at once (the set
includes 24B, 30B, 32B, 120B, and 235B models). Pinning every model just causes
constant load/evict thrashing. The larger reasoning/escalation lanes are loaded
on demand and pinned while loaded; use the switches below if you want to force
them warm anyway.

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

- `-IncludeReasoningLanes` — also pin the reasoning and escalation lanes.
  Since the reasoning lane already shares `mistral-small3.1:24b`, this mainly
  adds `qwen3:30b` (escalation). It will not co-reside with the shared 24B
  chat/helper model on 16 GB; expect on-demand swapping.
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
