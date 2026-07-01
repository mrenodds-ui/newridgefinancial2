<#
.SYNOPSIS
  Launch NewRidgeFinancial 2.0 as a single-window desktop program on loopback port 8765.
#>
[CmdletBinding()]
param(
    [switch]$NoBrowser,
    [switch]$Restart,
    [switch]$SkipModelWarmup,
    [switch]$SkipValidation
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
$AppDir = Join-Path $Root 'NewRidgeFinancial2'
$SiteDir = Join-Path $AppDir 'site'
$DesktopScript = Join-Path $AppDir 'desktop_app.py'
$ModelWarmupScript = Join-Path $AppDir 'model-automation\Keep-HAL-Models-Warm.ps1'
$DefaultPort = 8765

function Import-DotEnvFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return }
    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith('#')) { return }
        $idx = $line.IndexOf('=')
        if ($idx -lt 1) { return }
        $name = $line.Substring(0, $idx).Trim()
        $value = $line.Substring($idx + 1).Trim()
        if ($name) { Set-Item -Path "Env:$name" -Value $value }
    }
}

Import-DotEnvFile (Join-Path $Root '.env')
Import-DotEnvFile (Join-Path $AppDir '.env')

if (-not $env:NR2_HTTP_PORT) {
    $env:NR2_HTTP_PORT = [string]$DefaultPort
}
$nr2Port = [int]$env:NR2_HTTP_PORT

function Resolve-Python {
    $candidates = @(
        (Join-Path $Root '.venv\Scripts\pythonw.exe'),
        (Join-Path $Root '.venv-py313\Scripts\pythonw.exe'),
        (Join-Path $Root '.venv\Scripts\python.exe'),
        (Join-Path $Root '.venv-py313\Scripts\python.exe')
    )
    foreach ($c in $candidates) { if (Test-Path $c) { return $c } }
    $pythonw = Get-Command 'pythonw' -ErrorAction SilentlyContinue
    if ($pythonw) { return $pythonw.Source }
    return 'python'
}

function Stop-PortListener {
    param([int]$Port)
    Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
        Write-Host "Stopping listener on port $Port (PID $($_.OwningProcess))..." -ForegroundColor Yellow
        Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
    }
}

function Start-ModelWarmup {
    param(
        [string]$ScriptPath,
        [string]$StdoutPath,
        [string]$StderrPath
    )

    if ($SkipModelWarmup) {
        Write-Host 'HAL model warmup skipped by -SkipModelWarmup.' -ForegroundColor Yellow
        return
    }
    if (-not (Test-Path $ScriptPath)) {
        Write-Host "HAL model warmup script not found: $ScriptPath" -ForegroundColor Yellow
        return
    }

    try {
        Start-Process `
            -FilePath 'powershell.exe' `
            -ArgumentList @('-NoProfile', '-WindowStyle', 'Hidden', '-ExecutionPolicy', 'Bypass', '-File', $ScriptPath) `
            -WindowStyle Hidden `
            -RedirectStandardOutput $StdoutPath `
            -RedirectStandardError $StderrPath | Out-Null
        Write-Host 'HAL model warmup started (loads the active model into GPU via Ollama).' -ForegroundColor Green
    } catch {
        Write-Host "HAL model warmup could not be started: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

if (-not (Test-Path (Join-Path $SiteDir 'index.html'))) {
    throw "NewRidgeFinancial 2.0 site not found at $SiteDir"
}

Write-Host 'Start Program — NewRidgeFinancial 2.0 Desktop' -ForegroundColor Green
Write-Host "Loopback UI: http://127.0.0.1:$nr2Port/" -ForegroundColor Cyan

if (-not $SkipValidation) {
    $validatorScript = Join-Path $Root 'scripts\Invoke-NR2Validators.ps1'
    if (Test-Path $validatorScript) {
        & $validatorScript -Nr2Dir $AppDir
    }
} else {
    Write-Host 'Skipping NR2 validators (-SkipValidation).' -ForegroundColor Yellow
}

$manifestPath = Join-Path $AppDir 'nr2-build.json'
$schemaVersion = 'unknown'
if (Test-Path $manifestPath) {
    try {
        $manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
        if ($manifest.schemaVersion) { $schemaVersion = [string]$manifest.schemaVersion }
    } catch {}
}

$python = Resolve-Python
if (-not (Get-Command $python -ErrorAction SilentlyContinue)) {
    throw "Python is required to run NewRidgeFinancial 2.0 desktop app."
}

$logDir = Join-Path $Root '.tmp'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stdoutLog = Join-Path $logDir 'nr2-desktop.out.log'
$stderrLog = Join-Path $logDir 'nr2-desktop.err.log'
$warmupStdoutLog = Join-Path $logDir 'nr2-model-warmup.out.log'
$warmupStderrLog = Join-Path $logDir 'nr2-model-warmup.err.log'
$dataDir = Join-Path $Root 'app_data\nr2'
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
$pidFile = Join-Path $dataDir 'nr2-desktop.pid'

function Stop-ExistingNR2Desktop {
    param([string]$PidPath)
    if (-not (Test-Path $PidPath)) { return }
    try {
        $existingPid = [int](Get-Content $PidPath -Raw)
        if (Get-Process -Id $existingPid -ErrorAction SilentlyContinue) {
            Write-Host "Stopping previous NewRidgeFinancial 2.0 desktop app (PID $existingPid)..." -ForegroundColor Yellow
            Stop-Process -Id $existingPid -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 1
        }
    } catch {
        Write-Host "Could not stop previous desktop app: $($_.Exception.Message)" -ForegroundColor Yellow
    }
    Remove-Item $PidPath -Force -ErrorAction SilentlyContinue
}

Stop-ExistingNR2Desktop -PidPath $pidFile
Stop-PortListener -Port $nr2Port

Start-ModelWarmup -ScriptPath $ModelWarmupScript -StdoutPath $warmupStdoutLog -StderrPath $warmupStderrLog

$windowStyle = 'Hidden'
if ($python -match 'python\.exe$') { $windowStyle = 'Normal' }

$process = Start-Process -FilePath $python -ArgumentList @($DesktopScript) -WorkingDirectory $AppDir -WindowStyle $windowStyle -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog -PassThru
Set-Content -Path $pidFile -Value $process.Id
Write-Host "Start Program: desktop app launched (schema $schemaVersion, http://127.0.0.1:$nr2Port/)." -ForegroundColor Green
