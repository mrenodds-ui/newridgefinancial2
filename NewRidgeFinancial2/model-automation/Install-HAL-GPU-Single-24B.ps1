<#
.SYNOPSIS
  Build and pin a single HAL local 24B model on the R9700 32 GB GPU.

.DESCRIPTION
  Creates hal-local:24b from mistral-small3.1:24b (Q4_K_M), unpins 8B/30B/coder
  residents, and pins only the 24B tag with keep_alive = -1.
  Does NOT delete 8B/30B/coder model files.
#>
[CmdletBinding()]
param(
    [string]$OllamaHost = "http://127.0.0.1:11434",
    [string]$LocalTag = "hal-local:24b",
    [string]$BaseTag = "mistral-small3.1:24b",
    [string]$OllamaExe = "C:\Users\mreno\AppData\Local\Programs\Ollama\ollama.exe"
)

$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$warmScript = Join-Path $scriptRoot "Keep-HAL-Models-Warm.ps1"
$modelfile = Join-Path $scriptRoot "Modelfile.hal-local-24b"

$ollama = if (Test-Path $OllamaExe) { $OllamaExe } else { "ollama" }

$evict = @(
    "hal-chat:8b",
    "hal-escalate:30b",
    "hal-helper:14b",
    "qwen2.5-coder:32b",
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
    Write-Host "Pulling $Tag ..." -ForegroundColor Cyan
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

$show = & $ollama show $BaseTag 2>&1 | Out-String
if ($show -notmatch "Q4_K_M") {
    throw "Refusing to install: $BaseTag must report quantization Q4_K_M (got unexpected show output)."
}
if ($show -notmatch "24\.0B|24B|parameters\s+24") {
    Write-Host "Warning: could not confirm 24B parameter line in ollama show; continuing with verified tag name." -ForegroundColor DarkYellow
}

Ensure-BaseModel $BaseTag

Write-Host "Creating $LocalTag from $modelfile ..." -ForegroundColor Cyan
& $ollama create $LocalTag -f $modelfile
if ($LASTEXITCODE -ne 0) { throw "ollama create $LocalTag failed with exit code $LASTEXITCODE" }

Write-Host "Evicting prior dual-pin / on-demand residents (files kept on disk) ..." -ForegroundColor Yellow
foreach ($m in $evict) { Unpin-Model -Model $m }

Write-Host "Pinning single GPU-resident model: $LocalTag ..." -ForegroundColor Green
& $warmScript -Models @($LocalTag)
if ($LASTEXITCODE -ne 0) { throw "Keep-HAL-Models-Warm failed with exit code $LASTEXITCODE" }

Write-Host "`nLoaded models:" -ForegroundColor Green
& $ollama ps

Write-Host "`nHAL single-24B layout (R9700 32 GB):" -ForegroundColor Yellow
Write-Host "  Active (GPU pinned): $LocalTag (FROM $BaseTag Q4_K_M, num_ctx 8192)"
Write-Host "  Not auto-routed:     hal-chat:8b, hal-escalate:30b, qwen2.5-coder:32b (files retained)"
Write-Host "  MAX_LOADED_MODELS:   1"
Write-Host "Update complete. Restart the desktop app if it is already open." -ForegroundColor Green
