<#
.SYNOPSIS
  Build and pin HAL single GPU lane: hal-chat:8b only on 16 GB VRAM (speed-first layout).

.DESCRIPTION
  Pulls deepseek-r1:8b, creates the capped-context HAL chat tag, unpins hal-helper:14b if
  loaded, and pins only hal-chat:8b resident. Use mistral-small3.1:24b-fast on demand for
  reasoning and insurance narrative review.
#>
[CmdletBinding()]
param(
    [string]$OllamaHost = "http://127.0.0.1:11434",
    [string]$ChatTag = "hal-chat:8b",
    [string]$HelperTag = "hal-helper:14b",
    [string]$ReasoningTag = "mistral-small3.1:24b-fast",
    [switch]$UnpinHelper,
    [string]$OllamaExe = "C:\Users\mreno\AppData\Local\Programs\Ollama\ollama.exe"
)

$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$warmScript = Join-Path $scriptRoot "Keep-HAL-Models-Warm.ps1"

$ollama = if (Test-Path $OllamaExe) { $OllamaExe } else { "ollama" }

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

function New-HalTag {
    param(
        [string]$Tag,
        [string]$Modelfile
    )
    if (-not (Test-Path $Modelfile)) {
        throw "Modelfile not found: $Modelfile"
    }
    Write-Host "Creating $Tag from $Modelfile ..." -ForegroundColor Cyan
    & $ollama create $Tag -f $Modelfile
    if ($LASTEXITCODE -ne 0) { throw "ollama create $Tag failed with exit code $LASTEXITCODE" }
}

function Unpin-Model {
    param([Parameter(Mandatory = $true)][string]$Model)

    $body = @{
        model      = $Model
        keep_alive = 0
    } | ConvertTo-Json -Compress

    try {
        Invoke-RestMethod -Uri "$OllamaHost/api/generate" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 120 | Out-Null
        Write-Host "Unpinned (keep_alive=0): $Model" -ForegroundColor DarkGray
    } catch {
        Write-Host "Helper not loaded or already evicted: $Model" -ForegroundColor DarkGray
    }
}

Ensure-BaseModel "deepseek-r1:8b"
New-HalTag -Tag $ChatTag -Modelfile (Join-Path $scriptRoot "Modelfile.hal-chat-8b")

if ($UnpinHelper) {
    Write-Host "Evicting pinned helper model to free VRAM ..." -ForegroundColor Yellow
    Unpin-Model -Model $HelperTag
}

Write-Host "Pinning GPU resident chat model ..." -ForegroundColor Green
& $warmScript -Models @($ChatTag)
if ($LASTEXITCODE -ne 0) { throw "Keep-HAL-Models-Warm failed with exit code $LASTEXITCODE" }

Write-Host "`nLoaded models:" -ForegroundColor Green
& $ollama ps

Write-Host "`nHAL GPU layout (speed-first):" -ForegroundColor Yellow
Write-Host "  Chat (GPU pinned):  $ChatTag (deepseek-r1:8b Q4, num_ctx 3072)"
Write-Host "  Helper (on demand): $HelperTag (not pinned; load manually when needed)"
Write-Host "  Reasoning (demand): $ReasoningTag (plans, accounting, narratives)"
Write-Host "Update complete. Restart the desktop app if it is already open." -ForegroundColor Green
