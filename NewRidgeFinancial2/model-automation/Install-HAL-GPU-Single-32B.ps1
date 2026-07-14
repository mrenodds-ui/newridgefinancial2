<#
.SYNOPSIS
  Build and pin a single HAL local 32B model on the R9700 32 GB GPU.

.DESCRIPTION
  Creates hal-local:32b from qwen3:32b (Q4_K_M), unpins prior 24B/8B/30B/coder
  residents, and pins only the 32B tag with keep_alive = -1.
  Does NOT delete prior model files.
#>
[CmdletBinding()]
param(
    [string]$OllamaHost = "http://127.0.0.1:11434",
    [string]$LocalTag = "hal-local:32b",
    [string]$BaseTag = "qwen3:32b",
    [string]$OllamaExe = "C:\Users\mreno\AppData\Local\Programs\Ollama\ollama.exe"
)

$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$warmScript = Join-Path $scriptRoot "Keep-HAL-Models-Warm.ps1"
$modelfile = Join-Path $scriptRoot "Modelfile.hal-local-32b"

$ollama = if (Test-Path $OllamaExe) { $OllamaExe } else { "ollama" }

$evict = @(
    "hal-local:24b",
    "hal-chat:8b",
    "hal-escalate:30b",
    "hal-helper:14b",
    "qwen2.5-coder:32b",
    "qwen3-coder:30b",
    "qwen3:30b",
    "mistral-small3.1:24b-fast",
    "mistral-small3.1:24b"
)

function Ensure-BaseModel {
    param([string]$Tag)
    $listed = & $ollama list 2>$null | Select-String -Pattern "^\s*$([regex]::Escape($Tag))\s"
    if ($listed) {
        Write-Host "$Tag already installed - skipping pull." -ForegroundColor DarkGray
        return
    }
    Write-Host "Pulling $Tag (large download) ..." -ForegroundColor Cyan
    & $ollama pull $Tag
    if ($LASTEXITCODE -ne 0) { throw "ollama pull $Tag failed with exit code $LASTEXITCODE" }
}

function Unpin-Model {
    param([Parameter(Mandatory = $true)][string]$Model)
    $body = @{ model = $Model; keep_alive = 0 } | ConvertTo-Json -Compress
    try {
        Invoke-RestMethod -Uri "$OllamaHost/api/generate" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 120 | Out-Null
        Write-Host "Unpinned (keep_alive=0): $Model" -ForegroundColor DarkGray
    } catch {
        Write-Host "Model not loaded or already evicted: $Model" -ForegroundColor DarkGray
    }
}

Ensure-BaseModel $BaseTag

$show = & $ollama show $BaseTag 2>&1 | Out-String
if ($show -notmatch "Q4_K_M|Q4_K_S|q4_k_m") {
    Write-Host "Warning: could not confirm Q4_K_* in ollama show; continuing." -ForegroundColor DarkYellow
}
if ($show -notmatch "32\.0B|32B|parameters\s+32") {
    Write-Host "Warning: could not confirm 32B parameter line in ollama show; continuing with tag $BaseTag." -ForegroundColor DarkYellow
}

Write-Host "Creating $LocalTag from $modelfile ..." -ForegroundColor Cyan
& $ollama create $LocalTag -f $modelfile
if ($LASTEXITCODE -ne 0) { throw "ollama create $LocalTag failed with exit code $LASTEXITCODE" }

Write-Host "Evicting prior residents (files kept on disk) ..." -ForegroundColor Yellow
foreach ($m in $evict) { Unpin-Model -Model $m }

Write-Host "Pinning single GPU-resident model: $LocalTag ..." -ForegroundColor Green
& $warmScript -Models @($LocalTag)
if ($LASTEXITCODE -ne 0) { throw "Keep-HAL-Models-Warm failed with exit code $LASTEXITCODE" }

Write-Host "`nLoaded models:" -ForegroundColor Green
& $ollama ps

Write-Host "`nHAL single-32B layout (R9700 32 GB):" -ForegroundColor Yellow
Write-Host "  Active (GPU pinned): $LocalTag (FROM $BaseTag Q4_K_M, num_ctx 8192)"
Write-Host "  Not auto-routed:     hal-local:24b, 8B/30B/coder tags (files retained)"
Write-Host "  MAX_LOADED_MODELS:   1"
Write-Host "Update complete. Restart the desktop app if it is already open." -ForegroundColor Green
