<#
.SYNOPSIS
  Launch NR2 Office Workstation (Send Message + Ask HAL) as its own desktop program.
#>
[CmdletBinding()]
param(
    [switch]$SkipModelWarmup,
    [switch]$SkipValidation
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
$AppDir = Join-Path $Root 'NewRidgeFinancial2'
$SiteDir = Join-Path $AppDir 'site'
$WorkstationScript = Join-Path $AppDir 'workstation_app.py'
$ModelWarmupScript = Join-Path $AppDir 'model-automation\Keep-HAL-Models-Warm.ps1'
$DefaultPort = 8766

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

if (-not $env:NR2_WORKSTATION_FAST_HAL) { $env:NR2_WORKSTATION_FAST_HAL = '1' }

$env:NR2_WORKSTATION_PORT = [string]$DefaultPort
$nr2Port = [int]$env:NR2_WORKSTATION_PORT

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
    if ($SkipModelWarmup) { return }
    if (-not (Test-Path $ScriptPath)) { return }
    try {
        Start-Process `
            -FilePath 'powershell.exe' `
            -ArgumentList @('-NoProfile', '-WindowStyle', 'Hidden', '-ExecutionPolicy', 'Bypass', '-File', $ScriptPath) `
            -WindowStyle Hidden `
            -RedirectStandardOutput $StdoutPath `
            -RedirectStandardError $StderrPath | Out-Null
        Write-Host 'HAL model warmup started for Ask HAL.' -ForegroundColor Green
    } catch {
        Write-Host "HAL model warmup could not be started: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

if (-not (Test-Path (Join-Path $SiteDir 'workstation\index.html'))) {
    throw "Workstation entry not found at $(Join-Path $SiteDir 'workstation\index.html')"
}

Write-Host 'Start Workstation - NR2 Office Workstation' -ForegroundColor Green
Write-Host 'Separate desktop program for Send Message and Ask HAL (not the financial app).' -ForegroundColor Cyan

if (-not $SkipValidation) {
    $validatorScript = Join-Path $Root 'scripts\Invoke-NR2Validators.ps1'
    if (Test-Path $validatorScript) {
        & $validatorScript -Nr2Dir $AppDir
    }
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
    throw 'Python is required to run NR2 Office Workstation.'
}

$logDir = Join-Path $Root '.tmp'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stdoutLog = Join-Path $logDir 'nr2-workstation.out.log'
$stderrLog = Join-Path $logDir 'nr2-workstation.err.log'
$warmupStdoutLog = Join-Path $logDir 'nr2-workstation-warmup.out.log'
$warmupStderrLog = Join-Path $logDir 'nr2-workstation-warmup.err.log'
$dataDir = Join-Path $Root 'app_data\nr2'
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
$pidFile = Join-Path $dataDir 'nr2-workstation.pid'

function Stop-ExistingWorkstation {
    param([string]$PidPath)
    if (-not (Test-Path $PidPath)) { return }
    try {
        $existingPid = [int](Get-Content $PidPath -Raw)
        if (Get-Process -Id $existingPid -ErrorAction SilentlyContinue) {
            Write-Host "Stopping previous NR2 Office Workstation (PID $existingPid)..." -ForegroundColor Yellow
            Stop-Process -Id $existingPid -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 1
        }
    } catch {}
    Remove-Item $PidPath -Force -ErrorAction SilentlyContinue
}

Stop-ExistingWorkstation -PidPath $pidFile
Stop-PortListener -Port $nr2Port

Start-ModelWarmup -ScriptPath $ModelWarmupScript -StdoutPath $warmupStdoutLog -StderrPath $warmupStderrLog

$windowStyle = 'Hidden'
if ($python -match 'python\.exe$') { $windowStyle = 'Normal' }

$process = Start-Process -FilePath $python -ArgumentList @($WorkstationScript) -WorkingDirectory $AppDir -WindowStyle $windowStyle -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog -PassThru
Set-Content -Path $pidFile -Value $process.Id
Write-Host "Start Workstation: desktop app launched (schema $schemaVersion, port $nr2Port)." -ForegroundColor Green
