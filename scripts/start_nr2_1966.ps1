<#
.SYNOPSIS
  Start NewRidgeFinancial 2.0 on port 1966.
#>
[CmdletBinding()]
param(
    [switch]$NoBrowser,
    [switch]$Restart
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
$Port = 1966
$HostAddr = '127.0.0.1'
$AppUrl = "http://${HostAddr}:$Port/"
$SiteDir = Join-Path $Root 'NewRidgeFinancial2\site'

function Test-HttpOk([string]$Url) {
    try {
        $resp = Invoke-WebRequest -Uri $Url -TimeoutSec 3 -UseBasicParsing
        return $resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500
    } catch { return $false }
}

function Get-ListenerPid([int]$Port) {
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($conn) { return [int]$conn.OwningProcess }
    return $null
}

function Resolve-Python {
    $candidates = @(
        (Join-Path $Root '.venv\Scripts\python.exe'),
        (Join-Path $Root '.venv-py313\Scripts\python.exe')
    )
    foreach ($c in $candidates) { if (Test-Path $c) { return $c } }
    return 'python'
}

if (-not (Test-Path (Join-Path $SiteDir 'index.html'))) {
    throw "NewRidgeFinancial 2.0 site not found at $SiteDir"
}

Write-Host 'NewRidgeFinancial 2.0 on :1966' -ForegroundColor Green

if ((Test-HttpOk $AppUrl) -and -not $Restart) {
    Write-Host "Already running at $AppUrl"
} else {
    $pid = Get-ListenerPid $Port
    if ($pid) {
        Write-Host "Stopping existing listener on :$Port (PID $pid)..."
        Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
    }

    $python = Resolve-Python
    $serveScript = Join-Path $Root 'NewRidgeFinancial2\serve.py'
    $cmd = "Set-Location `"$Root`"; & `"$python`" `"$serveScript`""
    Start-Process powershell -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-NoExit', '-Command', $cmd -WindowStyle Minimized

    $ready = $false
    for ($i = 1; $i -le 20; $i++) {
        Start-Sleep -Seconds 1
        if (Test-HttpOk $AppUrl) { $ready = $true; break }
    }
    if (-not $ready) { throw "Server did not start on $AppUrl" }
    Write-Host "Running at $AppUrl" -ForegroundColor Green
}

if (-not $NoBrowser) { Start-Process $AppUrl }
