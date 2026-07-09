<#
.SYNOPSIS
  Build and pin HAL dual GPU lanes: hal-chat:8b + hal-escalate:30b on 32 GB VRAM (R9700 layout).

.DESCRIPTION
  Pulls deepseek-r1:8b and qwen3:30b, creates capped-context HAL tags, unpins
  hal-helper:14b and raw qwen3:30b if loaded, and pins chat + escalation with keep_alive = -1.
#>
[CmdletBinding()]
param(
    [string]$OllamaHost = "http://127.0.0.1:11434",
    [string]$ChatTag = "hal-chat:8b",
    [string]$EscalationTag = "hal-escalate:30b",
    [string]$HelperTag = "hal-helper:14b",
    [string]$RawEscalationTag = "qwen3:30b",
    [string]$ReasoningTag = "mistral-small3.1:24b-fast",
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
        Write-Host "Model not loaded or already evicted: $Model" -ForegroundColor DarkGray
    }
}

Ensure-BaseModel "deepseek-r1:8b"
Ensure-BaseModel "qwen3:30b"
New-HalTag -Tag $ChatTag -Modelfile (Join-Path $scriptRoot "Modelfile.hal-chat-8b")
New-HalTag -Tag $EscalationTag -Modelfile (Join-Path $scriptRoot "Modelfile.hal-escalate-30b")

Write-Host "Evicting non-pin models to free VRAM for 8B+30B layout ..." -ForegroundColor Yellow
Unpin-Model -Model $HelperTag
Unpin-Model -Model $RawEscalationTag

Write-Host "Pinning GPU resident chat + escalation models (capped context) ..." -ForegroundColor Green
& $warmScript -Models @($ChatTag, $EscalationTag)
if ($LASTEXITCODE -ne 0) { throw "Keep-HAL-Models-Warm failed with exit code $LASTEXITCODE" }

Write-Host "`nLoaded models:" -ForegroundColor Green
& $ollama ps

Write-Host "`nHAL GPU layout (8B + 30B dual pin, performance-tuned):" -ForegroundColor Yellow
Write-Host "  Chat (GPU pinned):       $ChatTag (num_ctx 3072)"
Write-Host "  Escalation (GPU pinned): $EscalationTag (num_ctx 4096, think=false)"
Write-Host "  Helper (on demand):      $HelperTag"
Write-Host "  Reasoning (shared pin):  $EscalationTag via reason21b/reason24b gateway lanes"
Write-Host "Update complete. Restart the desktop app if it is already open." -ForegroundColor Green
