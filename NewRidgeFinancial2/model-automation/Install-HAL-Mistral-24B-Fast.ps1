<#
.SYNOPSIS
  Build HAL's fast text-only quantized Mistral 24B for max GPU performance on 16 GB VRAM.

.DESCRIPTION
  Pulls mrfakename text-only Q4_K_S (~13 GB, no vision/mmproj overhead), creates
  mistral-small3.1:24b-fast, pins it resident, and prints a quick benchmark.
#>
[CmdletBinding()]
param(
    [string]$OllamaHost = "http://127.0.0.1:11434",
    [string]$ModelTag = "mistral-small3.1:24b-fast",
    [string]$OllamaExe = "C:\Users\mreno\AppData\Local\Programs\Ollama\ollama.exe"
)

$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$modelfile = Join-Path $scriptRoot "Modelfile.mistral-24b-fast"

if (-not (Test-Path $modelfile)) {
    throw "Modelfile not found: $modelfile"
}

$ollama = if (Test-Path $OllamaExe) { $OllamaExe } else { "ollama" }

Write-Host "Pulling text-only Q4_K_S GGUF and creating $ModelTag ..." -ForegroundColor Cyan
& $ollama create $ModelTag -f $modelfile
if ($LASTEXITCODE -ne 0) { throw "ollama create failed with exit code $LASTEXITCODE" }

Write-Host "Pinning $ModelTag resident (keep_alive=-1) ..." -ForegroundColor Cyan
$body = @{ model = $ModelTag; keep_alive = -1 } | ConvertTo-Json -Compress
Invoke-RestMethod -Uri "$OllamaHost/api/generate" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 900 | Out-Null

Write-Host "`nLoaded models:" -ForegroundColor Green
& $ollama ps

Write-Host "`nQuick benchmark (128 token cap) ..." -ForegroundColor Cyan
$benchBody = @{
    model  = $ModelTag
    prompt = "In three bullets, what should a dental office manager review first each morning?"
    stream = $false
    options = @{ num_predict = 128 }
} | ConvertTo-Json -Depth 4
$r = Invoke-RestMethod -Uri "$OllamaHost/api/generate" -Method Post -Body $benchBody -ContentType "application/json" -TimeoutSec 300
$tps = [math]::Round($r.eval_count / ($r.eval_duration / 1e9), 1)
$sizeGiB = [math]::Round(($r.model -as [string]).Length, 0)
Write-Host ("  Tokens/sec: {0}" -f $tps) -ForegroundColor Green
Write-Host ("  VRAM check: run ollama ps and confirm 100% GPU with smaller SIZE than 15 GB") -ForegroundColor Green
Write-Host ("Update hal-models.json lanes to use {0} then restart the desktop app." -f $ModelTag) -ForegroundColor Yellow
